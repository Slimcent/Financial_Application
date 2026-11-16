"""Seed data for the lookup tables: Roles, AccountTypes, TransactionTypes, TransactionModes, TransactionStatuses.

The services refer to these rows by the identifiers in Models/Constants/AppConstants.py, so the rows are inserted
with exactly those identifiers.

At start-up the application calls seed_lookups_on_first_run_async(): it checks that every lookup row the application
needs is there (one COUNT query per table) and writes only when rows are missing - on the first run against a new
database, and when a database misses some rows (e.g. a lookup value introduced later). Existing rows are never
changed.

Lookup data that contradicts AppConstants - a name the application needs held by a row with another identifier -
cannot be repaired automatically: seeding stops with a LookupSeedError that lists the rows to correct.

To check and complete the lookup data without starting the application::

    python -m Data.Seed.lookup_seed
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Infrastructure.Logging.logger import logger
from Models.Constants.AppConstants import AppConstants
from Models.Entities import AccountType, Role, TransactionMode, TransactionStatus, TransactionType


@dataclass(frozen=True)
class LookupSeed:
    """The rows of one lookup table: {identifier: name}, and the attribute that holds the name."""

    model: type[Any]
    name_attribute: str
    rows: dict[int, str]


LOOKUP_SEEDS: tuple[LookupSeed, ...] = (
    LookupSeed(Role, "Name", {
        AppConstants.CustomerRoleId: "Customer",
        AppConstants.StaffRoleId: "Staff",
    }),
    LookupSeed(AccountType, "Type", {
        AppConstants.SavingsAccountTypeId: "Savings",
        AppConstants.CurrentAccountTypeId: "Current",
    }),
    LookupSeed(TransactionType, "Name", {
        AppConstants.DepositTransactionTypeId: "Deposit",
        AppConstants.TransferTransactionTypeId: "Transfer",
        AppConstants.WithdrawalTransactionTypeId: "Withdrawal",
    }),
    LookupSeed(TransactionMode, "Name", {
        AppConstants.CreditTransactionModeId: "Credit",
        AppConstants.DebitTransactionModeId: "Debit",
    }),
    LookupSeed(TransactionStatus, "Name", {
        AppConstants.PendingTransactionStatusId: "Pending",
        AppConstants.CompletedTransactionStatusId: "Completed",
        AppConstants.FailedTransactionStatusId: "Failed",
    }),
)


class LookupSeedError(Exception):
    """The lookup data in the database contradicts AppConstants and has to be corrected by hand."""


async def missing_lookup_rows_async(unit_of_work: IUnitOfWork) -> dict[type[Any], dict[int, str]]:
    """The lookup rows the application needs that the database does not have: {entity: {identifier: name}}.

    One COUNT query per table; the rows of a table are read only when some of them are missing.
    """
    missing: dict[type[Any], dict[int, str]] = {}
    for seed in LOOKUP_SEEDS:
        repository = unit_of_work.get_repository(seed.model)
        identifier = getattr(seed.model, "Id")
        if await repository.count_async(identifier.in_(list(seed.rows))) == len(seed.rows):
            continue
        existing_ids = {row.Id for row in await repository.get_range_async(identifier.in_(list(seed.rows)))}
        missing[seed.model] = {row_id: name for row_id, name in seed.rows.items() if row_id not in existing_ids}
    return missing


async def is_database_seeded_async(unit_of_work: IUnitOfWork) -> bool:
    """Whether every lookup row the application needs is in the database."""
    return not await missing_lookup_rows_async(unit_of_work)


async def seed_lookups_on_first_run_async(unit_of_work: IUnitOfWork) -> int:
    """Add the lookup rows the database misses - all of them on the first run - and return how many were added;
    0, without writing, when every row is there already.

    ``unit_of_work`` must be active. Raises LookupSeedError if the lookup data contradicts AppConstants. If another
    instance of the application seeds the same database at the same moment, this instance's save fails on the
    unique keys; that is accepted only if every row the application needs is there afterwards.
    """
    if await is_database_seeded_async(unit_of_work):
        return 0

    try:
        added = await seed_lookups_async(unit_of_work)
    except IntegrityError as error:
        if await is_database_seeded_async(unit_of_work):
            logger.info("Lookup data was seeded by another instance of the application.")
            return 0
        raise LookupSeedError("The lookup rows could not be added and are still missing: "
                              f"{_describe(await missing_lookup_rows_async(unit_of_work))}") from error

    logger.info(f"Seeded {added} missing lookup row(s).")
    return added


async def seed_lookups_async(unit_of_work: IUnitOfWork) -> int:
    """Add the lookup rows that are missing and save them, in one transaction; returns the number of rows added.

    ``unit_of_work`` must be active. Existing rows are never changed (a row with the right identifier but another
    name is kept, with a warning). Raises LookupSeedError, before writing anything, if the name of a missing row is
    already used by a row with another identifier: the names are unique, so the row cannot be added and the
    database has to be corrected by hand.
    """
    missing = await missing_lookup_rows_async(unit_of_work)
    await _warn_about_renamed_rows(unit_of_work)

    contradictions = []
    for seed in LOOKUP_SEEDS:
        rows = missing.get(seed.model, {})
        if not rows:
            continue
        name_column = getattr(seed.model, seed.name_attribute)
        holders = await unit_of_work.get_repository(seed.model).get_range_async(name_column.in_(list(rows.values())))
        for holder in holders:
            expected_id = next(row_id for row_id, name in rows.items() if name == getattr(holder, seed.name_attribute))
            contradictions.append(f"{seed.model.__tablename__} '{getattr(holder, seed.name_attribute)}' has Id "
                                  f"{holder.Id}, AppConstants expects Id {expected_id}")
    if contradictions:
        raise LookupSeedError("The lookup data contradicts AppConstants: " + "; ".join(contradictions))

    staged = 0
    for seed in LOOKUP_SEEDS:
        rows = missing.get(seed.model, {})
        if rows:
            unit_of_work.get_repository(seed.model).add_range(
                [seed.model(Id=row_id, **{seed.name_attribute: name}) for row_id, name in rows.items()])
            staged += len(rows)

    if staged:
        await unit_of_work.save_changes_async()
    return staged


async def _warn_about_renamed_rows(unit_of_work: IUnitOfWork) -> None:
    for seed in LOOKUP_SEEDS:
        identifier = getattr(seed.model, "Id")
        rows = await unit_of_work.get_repository(seed.model).get_range_async(identifier.in_(list(seed.rows)))
        for row in rows:
            name = getattr(row, seed.name_attribute)
            if name != seed.rows[row.Id]:
                logger.warning(f"{seed.model.__tablename__} Id {row.Id} is named '{name}', "
                               f"AppConstants expects '{seed.rows[row.Id]}'; the row is kept as it is.")


def _describe(missing: dict[type[Any], dict[int, str]]) -> str:
    return "; ".join(f"{model.__tablename__} {row_id} '{name}'" for model, rows in missing.items()
                     for row_id, name in rows.items())


async def _main() -> None:
    from Data.Implementations.unit_of_work import UnitOfWork
    from Data.database_orm_async import Database

    database = Database()
    try:
        async with UnitOfWork(database.SessionLocal) as unit_of_work:
            added = await seed_lookups_async(unit_of_work)
        print(f"Lookup seeding finished: {added} row(s) added.")
    except LookupSeedError as error:
        print(f"Lookup seeding stopped: {error}")
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
