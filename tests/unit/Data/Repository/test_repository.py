"""Repository (Data/Implementations/repository.py): every operation, run through a unit of work on SQLite.

The `bank` fixture (tests/unit/Data/conftest.py) commits the rows each test starts from:

    account      owner  type     balance   transactions
    2600000001   Ada    Savings  100.00    1
    2600000002   Ada    Current   50.00
    2600000003   Ben    Savings  200.00    1
    2600000004   Cy     Savings    0.00
    2600000005   Dee    Current   75.00    (Dee is staff; Ada, Ben and Cy are customers)

`persisted` reads what is committed, through a connection of its own.
"""
import uuid
from datetime import timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import event, inspect, or_, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError, MultipleResultsFound
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.orm import joinedload, selectinload

from Data.Implementations.unit_of_work import UnitOfWork
from Models.Dtos.Response.paged_response import PagedResponse
from Models.Entities import Account, AccountType, Role, User

# SQLAlchemy warnings point at ORM misuse (e.g. an object that will not be saved), so they fail the tests; only
# SQLite's note that it stores DECIMAL as a floating point number is expected.
pytestmark = [pytest.mark.asyncio,
              pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning"),
              pytest.mark.filterwarnings("ignore:Dialect sqlite\\+aiosqlite does \\*not\\* support Decimal")]

ALL_ACCOUNTS = ["2600000001", "2600000002", "2600000003", "2600000004", "2600000005"]
MISSING_GUID = uuid.UUID(int=7)


def _numbers(accounts):
    return [account.AccountNumber for account in accounts]


async def _balances(persisted):
    """{account number: balance} of every committed account."""
    return {account.AccountNumber: account.Balance for account in await persisted.all(select(Account))}


def _tracked_keys(entity, model):
    """Identity keys of the `model` rows the entity's session tracks."""
    return [key for key in inspect(entity).session.identity_map.keys() if key[0] is model]


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------

class TestQuery:
    async def test_repository_works_on_its_entity_type(self, unit_of_work):
        assert unit_of_work.accounts.model is Account

    async def test_query_builds_a_select_of_the_entity_without_running_it(self, unit_of_work):
        statement = unit_of_work.accounts.query()

        assert [description["entity"] for description in statement.column_descriptions] == [Account]
        assert statement.whereclause is None


# ---------------------------------------------------------------------------
# get_by_id_async
# ---------------------------------------------------------------------------

class TestGetById:
    async def test_returns_the_entity_with_the_primary_key(self, unit_of_work, bank):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))

        assert (account.AccountNumber, account.Balance) == ("2600000001", Decimal("100.00"))

    async def test_integer_primary_key_of_a_lookup_entity(self, unit_of_work, bank):
        account_type = await unit_of_work.account_types.get_by_id_async(bank.account_type_ids["Current"])

        assert account_type.Type == "Current"

    @pytest.mark.parametrize("repository, missing_id", [("accounts", MISSING_GUID), ("account_types", 999_999)],
                             ids=["guid-key", "integer-key"])
    async def test_missing_record_is_none(self, unit_of_work, repository, missing_id):
        assert await getattr(unit_of_work, repository).get_by_id_async(missing_id) is None

    async def test_returns_the_instance_the_unit_of_work_already_tracks(self, unit_of_work, bank):
        account_id = bank.account_id("2600000001")

        first = await unit_of_work.accounts.get_by_id_async(account_id)

        assert await unit_of_work.accounts.get_by_id_async(account_id) is first
        assert inspect(first).persistent


# ---------------------------------------------------------------------------
# Includes (related objects loaded with the result)
# ---------------------------------------------------------------------------

class TestIncludes:
    @pytest.mark.parametrize("includes", [
        pytest.param(["user.customer"], id="path-string"),
        pytest.param([(Account.user, User.customer)], id="attribute-path"),
        pytest.param([joinedload(Account.user).joinedload(User.customer)], id="loader-option"),
        pytest.param("user.customer", id="single-include-without-list"),
    ])
    async def test_include_loads_the_related_objects(self, unit_of_work, bank, includes):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"), includes=includes)

        assert account.user.customer.Address == "Ada Street"

    async def test_relationship_that_is_not_included_is_not_loaded(self, unit_of_work, bank):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))

        with pytest.raises(InvalidRequestError, match="raise_on_sql"):
            account.user

    async def test_several_includes_and_collections(self, unit_of_work, bank):
        user = await unit_of_work.users.get_by_id_async(bank.user_ids["Ada"],
                                                        includes=["accounts.account_type", "customer", "Role"])

        assert sorted((account.AccountNumber, account.account_type.Type) for account in user.accounts) == \
               [("2600000001", "Savings"), ("2600000002", "Current")]
        assert (user.customer.Address, user.Role.Name) == ("Ada Street", "Customer")

    async def test_include_applies_to_every_entity_of_a_range(self, unit_of_work):
        users = await unit_of_work.users.get_range_async(includes=[User.accounts], order_by=[User.FirstName])

        assert {user.FirstName: len(user.accounts) for user in users} == {"Ada": 2, "Ben": 1, "Cy": 1, "Dee": 1}

    async def test_include_with_a_single_result_query(self, unit_of_work):
        account = await unit_of_work.accounts.get_single_async(Account.AccountNumber == "2600000003",
                                                               includes=[selectinload(Account.transactions)])

        assert [transaction.Amount for transaction in account.transactions] == [Decimal("200.00")]

    @pytest.mark.parametrize("includes, error", [
        pytest.param(["owner"], ValueError, id="unknown-relationship"),
        pytest.param(["user.wallet"], ValueError, id="unknown-nested-relationship"),
        pytest.param([User.accounts], ValueError, id="relationship-of-another-entity"),
        pytest.param([Account.Balance], ValueError, id="column-not-relationship"),
        pytest.param([(Account.user, Account.account_type)], ValueError, id="path-that-does-not-connect"),
        pytest.param([42], TypeError, id="not-an-include"),
    ])
    async def test_invalid_include_is_rejected(self, unit_of_work, bank, includes, error):
        with pytest.raises(error):
            await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"), includes=includes)


# ---------------------------------------------------------------------------
# get_single_async
# ---------------------------------------------------------------------------

class TestGetSingle:
    async def test_returns_the_one_entity_matching_the_filter(self, unit_of_work):
        account = await unit_of_work.accounts.get_single_async(Account.AccountNumber == "2600000003")

        assert account.Balance == Decimal("200.00")

    async def test_criteria_are_combined(self, unit_of_work, bank):
        account = await unit_of_work.accounts.get_single_async(
            Account.UserId == bank.user_ids["Ada"], Account.AccountTypeId == bank.account_type_ids["Current"])

        assert account.AccountNumber == "2600000002"

    async def test_statement_with_a_filter(self, unit_of_work):
        statement = unit_of_work.accounts.query().join(Account.user).where(User.Email == "example4@example.com")

        assert (await unit_of_work.accounts.get_single_async(statement)).AccountNumber == "2600000005"

    async def test_missing_record_is_none(self, unit_of_work):
        assert await unit_of_work.accounts.get_single_async(Account.AccountNumber == "2699999999") is None

    async def test_more_than_one_match_is_an_error(self, unit_of_work, bank):
        with pytest.raises(MultipleResultsFound):
            await unit_of_work.accounts.get_single_async(Account.UserId == bank.user_ids["Ada"])

    @pytest.mark.parametrize("build_filter", [
        pytest.param(lambda repository: (), id="no-criteria"),
        pytest.param(lambda repository: (repository.query(),), id="statement-without-where"),
    ])
    async def test_filter_is_required(self, unit_of_work, build_filter):
        with pytest.raises(ValueError, match="filter"):
            await unit_of_work.accounts.get_single_async(*build_filter(unit_of_work.accounts))

    @pytest.mark.parametrize("build_filter", [
        pytest.param(lambda repository: (True,), id="python-bool"),
        pytest.param(lambda repository: ("AccountNumber = '2600000001'",), id="sql-string"),
        pytest.param(lambda repository: (repository.query().where(Account.Balance > 0), Account.Balance > 1),
                     id="statement-and-criteria"),
        pytest.param(lambda repository: (select(User).where(User.FirstName == "Ada"),),
                     id="statement-of-another-entity"),
    ])
    async def test_invalid_filter_is_rejected(self, unit_of_work, build_filter):
        with pytest.raises(TypeError):
            await unit_of_work.accounts.get_single_async(*build_filter(unit_of_work.accounts))


# ---------------------------------------------------------------------------
# get_range_async: filtering, ordering, skip / take, statements
# ---------------------------------------------------------------------------

class TestGetRange:
    @pytest.mark.parametrize("criteria, expected", [
        pytest.param((), ALL_ACCOUNTS, id="no-criteria"),
        pytest.param((Account.Balance > Decimal("60"),), ["2600000001", "2600000003", "2600000005"],
                     id="comparison"),
        pytest.param((Account.AccountNumber.in_(["2600000002", "2600000004"]),), ["2600000002", "2600000004"],
                     id="in"),
        pytest.param((Account.Balance >= Decimal("50"), Account.Balance <= Decimal("100")),
                     ["2600000001", "2600000002", "2600000005"], id="several-criteria-and-ed"),
        pytest.param((or_(Account.Balance == 0, Account.Balance == 200),), ["2600000003", "2600000004"], id="or"),
        pytest.param((Account.AccountNumber.like("%5"),), ["2600000005"], id="like"),
        pytest.param((Account.user.has(User.FirstName == "Ada"),), ["2600000001", "2600000002"],
                     id="related-object-has"),
        pytest.param((Account.transactions.any(),), ["2600000001", "2600000003"], id="related-collection-any"),
        pytest.param((Account.Balance < 0,), [], id="no-match"),
    ])
    async def test_filtering(self, unit_of_work, criteria, expected):
        accounts = await unit_of_work.accounts.get_range_async(*criteria)

        assert sorted(_numbers(accounts)) == expected

    @pytest.mark.parametrize("order_by, expected", [
        pytest.param([Account.Balance], ["2600000004", "2600000002", "2600000005", "2600000001", "2600000003"],
                     id="ascending"),
        pytest.param([Account.Balance.desc()], ["2600000003", "2600000001", "2600000005", "2600000002", "2600000004"],
                     id="descending"),
        pytest.param([Account.AccountTypeId, Account.Balance.desc()],
                     ["2600000003", "2600000001", "2600000004", "2600000005", "2600000002"], id="several-terms"),
        pytest.param(Account.AccountNumber.desc(), list(reversed(ALL_ACCOUNTS)), id="single-term-without-list"),
    ])
    async def test_ordering(self, unit_of_work, order_by, expected):
        assert _numbers(await unit_of_work.accounts.get_range_async(order_by=order_by)) == expected

    @pytest.mark.parametrize("skip, take, expected", [
        pytest.param(None, 2, ["2600000001", "2600000002"], id="take"),
        pytest.param(3, None, ["2600000004", "2600000005"], id="skip"),
        pytest.param(1, 2, ["2600000002", "2600000003"], id="skip-and-take"),
        pytest.param(None, 0, [], id="take-none"),
        pytest.param(10, None, [], id="skip-past-the-end"),
    ])
    async def test_skip_and_take(self, unit_of_work, skip, take, expected):
        accounts = await unit_of_work.accounts.get_range_async(order_by=[Account.AccountNumber], skip=skip, take=take)

        assert _numbers(accounts) == expected

    @pytest.mark.parametrize("arguments", [{"skip": -1}, {"take": -1}], ids=["negative-skip", "negative-take"])
    async def test_negative_skip_or_take_is_rejected(self, unit_of_work, arguments):
        with pytest.raises(ValueError):
            await unit_of_work.accounts.get_range_async(**arguments)

    async def test_statement_with_joins_ordering_and_take(self, unit_of_work):
        statement = unit_of_work.accounts.query().join(Account.user).where(User.LastName != "Okafor")

        accounts = await unit_of_work.accounts.get_range_async(statement, order_by=[Account.Balance.desc()], take=2)

        assert _numbers(accounts) == ["2600000001", "2600000005"]

    async def test_returns_the_instances_the_unit_of_work_tracks(self, unit_of_work, bank):
        tracked = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000002"))

        accounts = await unit_of_work.accounts.get_range_async(Account.UserId == bank.user_ids["Ada"])

        assert any(account is tracked for account in accounts)


# ---------------------------------------------------------------------------
# get_range_async: paging
# ---------------------------------------------------------------------------

class TestPaging:
    @pytest.mark.parametrize("page, expected", [
        (1, ["2600000001", "2600000002"]),
        (2, ["2600000003", "2600000004"]),
        (3, ["2600000005"]),
        (4, []),
    ])
    async def test_page_holds_its_rows_and_the_total_count(self, unit_of_work, page, expected):
        result = await unit_of_work.accounts.get_range_async(page=page, page_size=2, order_by=[Account.AccountNumber])

        assert isinstance(result, PagedResponse)
        assert (result.total_count, result.page, result.page_size, _numbers(result.items)) == (5, page, 2, expected)

    async def test_total_count_counts_the_matching_rows_only(self, unit_of_work):
        result = await unit_of_work.accounts.get_range_async(Account.Balance > Decimal("60"), page=2, page_size=2,
                                                             order_by=[Account.AccountNumber])

        assert (result.total_count, _numbers(result.items)) == (3, ["2600000005"])

    async def test_pages_are_stable_when_sort_values_repeat(self, unit_of_work):
        pages = [await unit_of_work.accounts.get_range_async(page=page, page_size=2, order_by=[Account.AccountTypeId])
                 for page in (1, 2, 3)]

        assert sorted(number for page in pages for number in _numbers(page.items)) == ALL_ACCOUNTS

    async def test_statement_can_be_paged(self, unit_of_work):
        statement = unit_of_work.accounts.query().join(Account.user).where(User.FirstName == "Ada")

        result = await unit_of_work.accounts.get_range_async(statement, page=1, page_size=1, includes=["user"])

        assert (result.total_count, len(result.items), result.items[0].user.FirstName) == (2, 1, "Ada")

    @pytest.mark.parametrize("arguments", [
        pytest.param({"page": 1}, id="page-without-size"),
        pytest.param({"page_size": 5}, id="size-without-page"),
        pytest.param({"page": 0, "page_size": 5}, id="page-zero"),
        pytest.param({"page": 1, "page_size": 0}, id="size-zero"),
        pytest.param({"page": 1, "page_size": 5, "skip": 1}, id="with-skip"),
        pytest.param({"page": 1, "page_size": 5, "take": 1}, id="with-take"),
        pytest.param({"page": 1, "page_size": 5, "for_update": True}, id="with-row-locks"),
    ])
    async def test_invalid_paging_is_rejected(self, unit_of_work, arguments):
        with pytest.raises(ValueError):
            await unit_of_work.accounts.get_range_async(**arguments)


# ---------------------------------------------------------------------------
# count_async / sum_async / exists_async
# ---------------------------------------------------------------------------

class TestAggregates:
    @pytest.mark.parametrize("criteria, expected", [
        pytest.param((), 5, id="every-row"),
        pytest.param((Account.Balance > Decimal("60"),), 3, id="matching-rows"),
        pytest.param((Account.Balance < 0,), 0, id="no-match"),
    ])
    async def test_count(self, unit_of_work, criteria, expected):
        assert await unit_of_work.accounts.count_async(*criteria) == expected

    async def test_count_of_a_statement(self, unit_of_work):
        statement = unit_of_work.accounts.query().join(Account.user).where(User.FirstName == "Ada")

        assert await unit_of_work.accounts.count_async(statement) == 2

    @pytest.mark.parametrize("owner, expected", [(None, "425.00"), ("Ada", "150.00"), ("Cy", "0.00")],
                             ids=["every-row", "matching-rows", "zero-balance"])
    async def test_sum_of_a_money_column_is_a_decimal(self, unit_of_work, bank, owner, expected):
        criteria = () if owner is None else (Account.UserId == bank.user_ids[owner],)

        total = await unit_of_work.accounts.sum_async(Account.Balance, *criteria)

        assert isinstance(total, Decimal)
        assert total == Decimal(expected)

    async def test_sum_with_no_matching_row_is_zero(self, unit_of_work):
        assert await unit_of_work.accounts.sum_async(Account.Balance, Account.Balance < 0) == 0

    async def test_sum_of_an_expression(self, unit_of_work):
        assert await unit_of_work.accounts.sum_async(Account.Balance * 2) == Decimal("850.00")

    async def test_sum_of_a_statement(self, unit_of_work):
        statement = unit_of_work.accounts.query().join(Account.user).where(User.FirstName == "Ada")

        total = await unit_of_work.accounts.sum_async(Account.Balance, statement)

        assert isinstance(total, Decimal)
        assert total == Decimal("150.00")

    async def test_sum_of_a_statement_ignores_its_ordering_and_limit(self, unit_of_work):
        statement = unit_of_work.accounts.query().order_by(Account.Balance).limit(1)

        assert await unit_of_work.accounts.sum_async(Account.Balance, statement) == Decimal("425.00")

    async def test_sum_of_a_statement_with_no_matching_row_is_zero(self, unit_of_work):
        statement = unit_of_work.accounts.query().join(Account.user).where(User.FirstName == "Zed")

        assert await unit_of_work.accounts.sum_async(Account.Balance, statement) == 0

    async def test_sum_of_a_statement_of_another_entity_is_rejected(self, unit_of_work):
        with pytest.raises(TypeError):
            await unit_of_work.accounts.sum_async(Account.Balance, unit_of_work.users.query())

    @pytest.mark.parametrize("criteria, expected", [
        pytest.param((Account.AccountNumber == "2600000001",), True, id="match"),
        pytest.param((Account.AccountNumber == "2699999999",), False, id="missing-record"),
        pytest.param((), True, id="any-row"),
    ])
    async def test_exists(self, unit_of_work, criteria, expected):
        assert await unit_of_work.accounts.exists_async(*criteria) is expected

    async def test_exists_of_a_statement(self, unit_of_work):
        statement = unit_of_work.accounts.query().join(Account.user).where(User.FirstName == "Zed")

        assert await unit_of_work.accounts.exists_async(statement) is False

    @pytest.mark.parametrize("operation", [
        pytest.param(lambda accounts: accounts.count_async(True), id="count"),
        pytest.param(lambda accounts: accounts.sum_async(Account.Balance, True), id="sum"),
        pytest.param(lambda accounts: accounts.exists_async(True), id="exists"),
    ])
    async def test_criteria_must_be_sql_expressions(self, unit_of_work, operation):
        with pytest.raises(TypeError):
            await operation(unit_of_work.accounts)


# ---------------------------------------------------------------------------
# Row locking (for_update)
# ---------------------------------------------------------------------------

class TestRowLocking:
    async def test_locking_read_returns_the_matching_rows(self, unit_of_work, bank):
        accounts = await unit_of_work.accounts.get_range_async(Account.UserId == bank.user_ids["Ada"],
                                                               order_by=[Account.Id], for_update=True)

        assert _numbers(accounts) == ["2600000001", "2600000002"]

    async def test_locking_read_of_a_single_row_with_includes(self, unit_of_work):
        account = await unit_of_work.accounts.get_single_async(Account.AccountNumber == "2600000003",
                                                               includes=["user"], for_update=True)

        assert (account.Balance, account.user.FirstName) == (Decimal("200.00"), "Ben")

    async def test_plain_read_keeps_the_values_a_tracked_entity_was_loaded_with(self, unit_of_work, bank,
                                                                               session_factory):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id)
        await _change_balance_elsewhere(session_factory, account_id, "999.00")

        await unit_of_work.accounts.get_by_id_async(account_id)

        assert account.Balance == Decimal("100.00")

    async def test_locking_read_refreshes_a_tracked_entity_and_keeps_its_staged_changes_and_relationships(
            self, unit_of_work, bank, session_factory, persisted):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id, includes=["user"])
        unit_of_work.accounts.update_single(account, {"AccountNumber": "2699999999"})
        await _change_balance_elsewhere(session_factory, account_id, "999.00")

        locked = await unit_of_work.accounts.get_by_id_async(account_id, for_update=True)

        assert locked is account
        assert (account.Balance, account.AccountNumber) == (Decimal("999.00"), "2699999999")
        assert account.user.FirstName == "Ada"
        await unit_of_work.save_changes_async()
        stored = await persisted.get(Account, account_id)
        assert (stored.Balance, stored.AccountNumber) == (Decimal("999.00"), "2699999999")


async def _change_balance_elsewhere(session_factory, account_id, balance):
    """Another connection changes and commits an account's balance."""
    async with session_factory() as other_session:
        account = await other_session.get(Account, account_id)
        account.Balance = Decimal(balance)
        await other_session.commit()


# ---------------------------------------------------------------------------
# add_single / add_range (staged) and add_single_async / add_range_async (persisted)
# ---------------------------------------------------------------------------

class TestAdd:
    async def test_add_single_stages_the_entity_until_the_unit_of_work_saves(self, unit_of_work, persisted, new_role):
        role = new_role()

        assert unit_of_work.roles.add_single(role) is role
        assert role.Id is None
        assert await persisted.count(Role, Role.Name == role.Name) == 0

        await unit_of_work.save_changes_async()

        assert isinstance(role.Id, int)
        assert await persisted.count(Role, Role.Name == role.Name) == 1

    async def test_add_range_stages_every_entity(self, unit_of_work, persisted, new_role):
        roles = [new_role(), new_role()]

        assert unit_of_work.roles.add_range(iter(roles)) == roles
        assert await persisted.count(Role) == 2
        await unit_of_work.save_changes_async()

        assert await persisted.count(Role) == 4

    async def test_saved_entity_gets_its_generated_key_and_defaults(self, unit_of_work, new_account):
        account = unit_of_work.accounts.add_single(new_account(balance=None))

        await unit_of_work.save_changes_async()

        assert isinstance(account.Id, uuid.UUID)
        assert account.Balance == Decimal("0.00")
        assert account.CreatedAt.tzinfo is timezone.utc
        assert account.UpdatedAt == account.CreatedAt

    async def test_related_new_objects_are_saved_with_a_staged_entity(self, unit_of_work, bank, persisted):
        user = User(LastName="Quinn", FirstName="Eve", Email="example@example.com", RoleId=bank.role_ids["Customer"],
                    Password="hash")
        user.accounts.append(Account(AccountTypeId=bank.account_type_ids["Savings"], AccountNumber="2711111111"))

        unit_of_work.users.add_single(user)
        await unit_of_work.save_changes_async()

        stored = await persisted.get(Account, user.accounts[0].Id)
        assert stored.UserId == user.Id

    async def test_add_single_async_inserts_at_once_with_key_and_defaults(self, unit_of_work, persisted, new_account):
        account = new_account(balance=None)

        assert await unit_of_work.accounts.add_single_async(account) is account

        assert isinstance(account.Id, uuid.UUID)
        assert account.Balance == Decimal("0.00")
        stored = await persisted.get(Account, account.Id)
        assert (stored.AccountNumber, stored.Balance) == (account.AccountNumber, Decimal("0.00"))

    async def test_entity_added_at_once_is_saved_but_not_tracked(self, unit_of_work, new_account):
        account = await unit_of_work.accounts.add_single_async(new_account())

        assert inspect(account).detached
        assert inspect(account).key is not None

    async def test_staged_entity_added_at_once_becomes_tracked_and_is_not_inserted_again(self, unit_of_work,
                                                                                        persisted, new_role):
        role = unit_of_work.roles.add_single(new_role())

        await unit_of_work.roles.add_single_async(role)

        assert inspect(role).persistent
        result = await unit_of_work.save_changes_async()
        assert result.added == 0
        assert await persisted.count(Role, Role.Name == role.Name) == 1

    async def test_add_range_async_inserts_every_entity(self, unit_of_work, persisted, new_role):
        roles = await unit_of_work.roles.add_range_async([new_role(), new_role(), new_role()])

        assert all(isinstance(role.Id, int) for role in roles)
        assert await persisted.count(Role) == 5

    async def test_add_range_async_is_all_or_nothing(self, unit_of_work, persisted, new_role):
        roles = [new_role(), new_role(name="Customer")]  # the second name is taken

        with pytest.raises(IntegrityError):
            await unit_of_work.roles.add_range_async(roles)

        assert await persisted.count(Role, Role.Name == roles[0].Name) == 0

    async def test_many_to_one_object_is_written_as_its_foreign_key(self, unit_of_work, bank, persisted):
        owner = await unit_of_work.users.get_by_id_async(bank.user_ids["Cy"])
        account = Account(user=owner, AccountTypeId=bank.account_type_ids["Current"], AccountNumber="2711111111")

        await unit_of_work.accounts.add_single_async(account)

        assert (await persisted.get(Account, account.Id)).UserId == bank.user_ids["Cy"]

    async def test_add_single_async_refuses_related_objects_it_would_not_save(self, unit_of_work, bank, persisted):
        user = User(LastName="Quinn", FirstName="Eve", Email="example@example.com", RoleId=bank.role_ids["Customer"],
                    Password="hash")
        user.accounts.append(Account(AccountTypeId=bank.account_type_ids["Savings"], AccountNumber="2711111111"))

        with pytest.raises(ValueError, match="accounts"):
            await unit_of_work.users.add_single_async(user)

        assert await persisted.count(User, User.Email == "example@example.com") == 0

    @pytest.mark.parametrize("operation", [
        pytest.param(lambda accounts, account: accounts.add_single(account), id="add_single"),
        pytest.param(lambda accounts, account: accounts.add_single_async(account), id="add_single_async"),
    ])
    async def test_saved_entity_cannot_be_added(self, unit_of_work, bank, operation, result_of):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))

        with pytest.raises(ValueError, match="already been saved"):
            await result_of(operation(unit_of_work.accounts, account))

    @pytest.mark.parametrize("operation", [
        pytest.param(lambda accounts: accounts.add_single(Role(Name="Teller")), id="add_single"),
        pytest.param(lambda accounts: accounts.add_range([Role(Name="Teller")]), id="add_range"),
        pytest.param(lambda accounts: accounts.add_single_async(Role(Name="Teller")), id="add_single_async"),
    ])
    async def test_entity_of_another_type_is_rejected(self, unit_of_work, operation, result_of):
        with pytest.raises(TypeError):
            await result_of(operation(unit_of_work.accounts))


# ---------------------------------------------------------------------------
# update_single / update_range (staged) and update_single_async / update_range_async (persisted)
# ---------------------------------------------------------------------------

class TestUpdate:
    async def test_update_single_applies_values_at_once_and_persists_them_when_saved(self, unit_of_work, bank,
                                                                                     persisted):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id)

        assert unit_of_work.accounts.update_single(account, {"Balance": Decimal("123.45")}) is account
        assert account.Balance == Decimal("123.45")
        assert (await persisted.get(Account, account_id)).Balance == Decimal("100.00")

        await unit_of_work.save_changes_async()

        assert (await persisted.get(Account, account_id)).Balance == Decimal("123.45")

    async def test_changes_made_on_a_tracked_entity_are_saved(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id)
        account.Balance = Decimal("1.50")

        unit_of_work.accounts.update_single(account)
        await unit_of_work.save_changes_async()

        assert (await persisted.get(Account, account_id)).Balance == Decimal("1.50")

    async def test_updated_at_is_refreshed_when_saved(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000001")
        loaded_at = (await persisted.get(Account, account_id)).UpdatedAt
        account = await unit_of_work.accounts.get_by_id_async(account_id)

        unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
        await unit_of_work.save_changes_async()

        assert (await persisted.get(Account, account_id)).UpdatedAt > loaded_at

    async def test_detached_entity_is_attached_and_its_changes_saved(self, unit_of_work, bank, session_factory,
                                                                     persisted):
        account_id = bank.account_id("2600000001")
        async with session_factory() as other_session:
            detached = await other_session.get(Account, account_id)
        detached.Balance = Decimal("7.00")

        tracked = unit_of_work.accounts.update_single(detached)
        await unit_of_work.save_changes_async()

        assert tracked is detached
        assert (await persisted.get(Account, account_id)).Balance == Decimal("7.00")

    async def test_changes_of_a_detached_copy_go_to_the_entity_the_unit_of_work_tracks(
            self, unit_of_work, bank, session_factory, persisted):
        account_id = bank.account_id("2600000001")
        tracked = await unit_of_work.accounts.get_by_id_async(account_id, includes=["user"])
        async with session_factory() as other_session:
            detached = await other_session.get(Account, account_id, options=[joinedload(Account.user)])
        detached.Balance = Decimal("7.00")

        result = unit_of_work.accounts.update_single(detached)
        await unit_of_work.save_changes_async()

        assert result is tracked
        assert tracked.Balance == Decimal("7.00")
        assert (await persisted.get(Account, account_id)).Balance == Decimal("7.00")

    async def test_detached_entity_referencing_a_copy_of_a_tracked_row_is_attached_to_the_tracked_row(
            self, unit_of_work, bank, session_factory, persisted):
        owner = await unit_of_work.users.get_by_id_async(bank.user_ids["Ada"])
        async with session_factory() as other_session:
            detached = await other_session.get(Account, bank.account_id("2600000001"),
                                               options=[joinedload(Account.user)])
        detached.Balance = Decimal("6.00")

        unit_of_work.accounts.update_single(detached)
        await unit_of_work.save_changes_async()

        assert detached.user is owner
        assert (await persisted.get(Account, detached.Id)).Balance == Decimal("6.00")

    async def test_relationship_value_is_saved_as_its_foreign_key(self, unit_of_work, bank, persisted):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000004"))
        new_owner = await unit_of_work.users.get_by_id_async(bank.user_ids["Ben"])

        unit_of_work.accounts.update_single(account, {"user": new_owner,
                                                      "AccountTypeId": bank.account_type_ids["Retirement"]})
        await unit_of_work.save_changes_async()

        assert (await persisted.get(Account, account.Id)).UserId == bank.user_ids["Ben"]

    async def test_related_detached_copy_of_a_tracked_row_is_replaced_by_the_tracked_entity(
            self, unit_of_work, bank, session_factory, persisted):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000004"))
        new_owner = await unit_of_work.users.get_by_id_async(bank.user_ids["Ben"])
        async with session_factory() as other_session:
            owner_copy = await other_session.get(User, bank.user_ids["Ben"])

        unit_of_work.accounts.update_single(account, {"user": owner_copy,
                                                      "AccountTypeId": bank.account_type_ids["Retirement"]})
        await unit_of_work.save_changes_async()

        assert account.user is new_owner
        assert (await persisted.get(Account, account.Id)).UserId == bank.user_ids["Ben"]

    async def test_new_entity_referencing_a_detached_copy_of_a_tracked_row_is_saved(self, unit_of_work, bank,
                                                                                    session_factory, persisted):
        owner = await unit_of_work.users.get_by_id_async(bank.user_ids["Ada"])
        async with session_factory() as other_session:
            owner_copy = await other_session.get(User, bank.user_ids["Ada"])
        account = Account(user=owner_copy, AccountTypeId=bank.account_type_ids["Retirement"],
                          AccountNumber="2711111111")

        unit_of_work.accounts.add_single(account)
        await unit_of_work.save_changes_async()

        assert account.user is owner
        assert (await persisted.get(Account, account.Id)).UserId == bank.user_ids["Ada"]

    @pytest.mark.parametrize("collection_loaded", [True, False], ids=["loaded", "not-loaded"])
    async def test_collection_changes_of_a_detached_copy_go_to_the_tracked_collection(
            self, unit_of_work, bank, session_factory, persisted, collection_loaded):
        tracked = await unit_of_work.users.get_by_id_async(bank.user_ids["Cy"],
                                                           includes=["accounts"] if collection_loaded else ())
        async with session_factory() as other_session:
            detached = await other_session.get(User, bank.user_ids["Cy"], options=[selectinload(User.accounts)])
        detached.accounts.append(Account(AccountTypeId=bank.account_type_ids["Current"], AccountNumber="2711111111"))

        if not collection_loaded:
            with pytest.raises(ValueError, match="includes"):
                unit_of_work.users.update_single(detached)
            return

        assert unit_of_work.users.update_single(detached) is tracked
        await unit_of_work.save_changes_async()
        assert sorted(account.AccountNumber for account in tracked.accounts) == ["2600000004", "2711111111"]
        assert await persisted.count(Account, Account.UserId == bank.user_ids["Cy"]) == 2

    async def test_staged_update_of_a_row_deleted_meanwhile_fails_the_save(self, unit_of_work, bank,
                                                                          session_factory, persisted, new_role):
        account_id = bank.account_id("2600000004")
        account = await unit_of_work.accounts.get_by_id_async(account_id)
        unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
        role = unit_of_work.roles.add_single(new_role())
        async with session_factory() as other_session:
            await other_session.delete(await other_session.get(Account, account_id))
            await other_session.commit()

        with pytest.raises(StaleDataError):
            await unit_of_work.save_changes_async()

        assert await persisted.count(Role, Role.Name == role.Name) == 0

    async def test_staged_new_entity_is_inserted_with_the_updated_values(self, unit_of_work, persisted, new_account):
        account = unit_of_work.accounts.add_single(new_account())

        unit_of_work.accounts.update_single(account, {"Balance": Decimal("5.00")})
        await unit_of_work.save_changes_async()

        assert (await persisted.get(Account, account.Id)).Balance == Decimal("5.00")

    @pytest.mark.parametrize("values, error", [
        pytest.param({"Id": uuid.UUID(int=1)}, ValueError, id="primary-key"),
        pytest.param({"Nickname": "savings"}, AttributeError, id="unknown-attribute"),
    ])
    async def test_invalid_values_are_rejected(self, unit_of_work, bank, values, error):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))

        with pytest.raises(error):
            unit_of_work.accounts.update_single(account, values)

    @pytest.mark.parametrize("operation", [
        pytest.param(lambda accounts, account: accounts.update_single(account), id="update_single"),
        pytest.param(lambda accounts, account: accounts.update_single_async(account), id="update_single_async"),
    ])
    async def test_entity_that_was_never_saved_is_rejected(self, unit_of_work, new_account, operation, result_of):
        with pytest.raises(ValueError, match="not been saved"):
            await result_of(operation(unit_of_work.accounts, new_account()))

    async def test_update_single_async_writes_at_once(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id)

        result = await unit_of_work.accounts.update_single_async(account, {"Balance": Decimal("42.00")})

        assert result is account
        assert account.Balance == Decimal("42.00")
        assert (await persisted.get(Account, account_id)).Balance == Decimal("42.00")

    async def test_update_single_async_writes_the_changes_made_on_the_entity(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id)
        account.Balance = Decimal("8.00")

        await unit_of_work.accounts.update_single_async(account)

        assert (await persisted.get(Account, account_id)).Balance == Decimal("8.00")
        assert (await unit_of_work.save_changes_async()).updated == 0  # nothing left staged for it

    async def test_sql_expression_value_shows_the_stored_result(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id)

        await unit_of_work.accounts.update_single_async(account, {"Balance": Account.Balance + 25})

        assert account.Balance == Decimal("125.00")
        assert (await persisted.get(Account, account_id)).Balance == Decimal("125.00")

    async def test_detached_entity_is_written_through_its_foreign_keys(self, unit_of_work, bank, session_factory,
                                                                      persisted):
        account_id = bank.account_id("2600000004")
        async with session_factory() as other_session:
            detached = await other_session.get(Account, account_id)
            new_owner = await other_session.get(User, bank.user_ids["Ben"])
        detached.user = new_owner
        detached.AccountTypeId = bank.account_type_ids["Retirement"]

        await unit_of_work.accounts.update_single_async(detached)

        stored = await persisted.get(Account, account_id)
        assert (stored.UserId, stored.AccountTypeId) == (bank.user_ids["Ben"], bank.account_type_ids["Retirement"])

    async def test_update_single_async_of_a_row_deleted_meanwhile_is_an_error(self, unit_of_work, bank,
                                                                             session_factory):
        account_id = bank.account_id("2600000004")
        account = await unit_of_work.accounts.get_by_id_async(account_id)
        async with session_factory() as other_session:
            await other_session.delete(await other_session.get(Account, account_id))
            await other_session.commit()

        with pytest.raises(ValueError, match="no longer exists"):
            await unit_of_work.accounts.update_single_async(account, {"Balance": Decimal("1.00")})

    async def test_update_single_async_refuses_collection_changes_of_an_untracked_entity(
            self, unit_of_work, bank, session_factory, persisted):
        async with session_factory() as other_session:
            user = await other_session.get(User, bank.user_ids["Cy"], options=[selectinload(User.accounts)])
        user.accounts.append(Account(AccountTypeId=bank.account_type_ids["Current"], AccountNumber="2711111111"))

        with pytest.raises(ValueError, match="other rows"):
            await unit_of_work.users.update_single_async(user, {"LastName": "Changed"})

        assert (await persisted.get(User, bank.user_ids["Cy"])).LastName == "Young"

    async def test_update_range_of_entities_stages_each(self, unit_of_work, bank, persisted):
        accounts = await unit_of_work.accounts.get_range_async(Account.UserId == bank.user_ids["Ada"])

        assert unit_of_work.accounts.update_range(accounts, values={"Balance": Decimal("9.00")}) == accounts
        assert await persisted.count(Account, Account.Balance == Decimal("9.00")) == 0
        await unit_of_work.save_changes_async()

        assert await persisted.count(Account, Account.Balance == Decimal("9.00")) == 2

    async def test_update_range_by_criteria_is_applied_through_the_orm_when_saved(self, unit_of_work, bank,
                                                                                  persisted):
        savings = Account.AccountTypeId == bank.account_type_ids["Savings"]
        loaded_at = (await persisted.get(Account, bank.account_id("2600000001"))).UpdatedAt
        tracked = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))

        assert unit_of_work.accounts.update_range(savings, values={"Balance": Account.Balance + 1}) is None
        assert (await _balances(persisted))["2600000001"] == Decimal("100.00")
        await unit_of_work.save_changes_async()

        assert await _balances(persisted) == {"2600000001": Decimal("101.00"), "2600000002": Decimal("50.00"),
                            "2600000003": Decimal("201.00"), "2600000004": Decimal("1.00"),
                            "2600000005": Decimal("75.00")}
        assert (await persisted.get(Account, bank.account_id("2600000001"))).UpdatedAt > loaded_at  # ORM onupdate
        assert tracked.Balance == Decimal("101.00")  # the tracked entity shows the stored value

    async def test_update_range_async_by_criteria_returns_the_row_count(self, unit_of_work, bank, persisted):
        count = await unit_of_work.accounts.update_range_async(Account.UserId == bank.user_ids["Ada"],
                                                               values={"Balance": Decimal("3.00")})

        assert count == 2
        assert await persisted.count(Account, Account.Balance == Decimal("3.00")) == 2

    async def test_update_range_async_of_entities_writes_each(self, unit_of_work, bank, persisted):
        accounts = await unit_of_work.accounts.get_range_async(Account.UserId == bank.user_ids["Ada"])

        result = await unit_of_work.accounts.update_range_async(accounts, values={"Balance": Decimal("4.00")})

        assert result == accounts
        assert [account.Balance for account in accounts] == [Decimal("4.00")] * 2
        assert await persisted.count(Account, Account.Balance == Decimal("4.00")) == 2

    @pytest.mark.parametrize("criteria, values, error", [
        pytest.param((), {"Balance": 0}, ValueError, id="no-criteria"),
        pytest.param((Account.Balance > 0,), None, ValueError, id="no-values"),
        pytest.param((Account.Balance > 0,), {"user": None}, AttributeError, id="relationship-value"),
        pytest.param((Account.Balance > 0,), {"Id": uuid.UUID(int=1)}, ValueError, id="primary-key"),
        pytest.param((True,), {"Balance": 0}, TypeError, id="python-bool-criterion"),
    ])
    @pytest.mark.parametrize("persist", [False, True], ids=["update_range", "update_range_async"])
    async def test_invalid_update_by_criteria_is_rejected(self, unit_of_work, criteria, values, error, persist):
        accounts = unit_of_work.accounts
        with pytest.raises(error):
            if persist:
                await accounts.update_range_async(*criteria, values=values)
            else:
                accounts.update_range(*criteria, values=values)


# ---------------------------------------------------------------------------
# Bulk operations in batches
# ---------------------------------------------------------------------------

class TestBatches:
    @pytest_asyncio.fixture
    async def batched_unit_of_work(self, session_factory, bank):
        """A unit of work whose bulk operations load, write and delete two rows per batch."""
        async with UnitOfWork(session_factory, batch_size=2) as unit_of_work:
            yield unit_of_work

    async def test_every_matching_row_is_updated_once(self, batched_unit_of_work, persisted):
        # Rows that still match after their update (0 -> 100) must not be updated again in a later batch.
        count = await batched_unit_of_work.accounts.update_range_async(
            Account.Balance < Decimal("150"), values={"Balance": Account.Balance + 100})

        assert count == 4
        assert await _balances(persisted) == {"2600000001": Decimal("200.00"), "2600000002": Decimal("150.00"),
                            "2600000003": Decimal("200.00"), "2600000004": Decimal("100.00"),
                            "2600000005": Decimal("175.00")}

    async def test_staged_update_by_criteria_runs_in_batches(self, batched_unit_of_work, persisted):
        batched_unit_of_work.accounts.update_range(Account.Balance >= 0, values={"Balance": Account.Balance + 1})

        await batched_unit_of_work.save_changes_async()

        assert await _balances(persisted) == {"2600000001": Decimal("101.00"), "2600000002": Decimal("51.00"),
                                              "2600000003": Decimal("201.00"), "2600000004": Decimal("1.00"),
                                              "2600000005": Decimal("76.00")}

    async def test_rows_the_unit_of_work_did_not_track_are_released(self, batched_unit_of_work, bank):
        tracked = await batched_unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))

        count = await batched_unit_of_work.accounts.update_range_async(Account.Balance >= 0,
                                                                       values={"Balance": Account.Balance + 1})

        assert count == 5
        assert _tracked_keys(tracked, Account) == [inspect(tracked).key]
        assert tracked.Balance == Decimal("101.00")  # the tracked row was updated in place

    @pytest.mark.parametrize("staged", [False, True], ids=["delete_range_async", "delete_range"])
    async def test_every_matching_row_is_deleted(self, batched_unit_of_work, persisted, new_role, staged):
        await batched_unit_of_work.roles.add_range_async([new_role(f"Temp {number}") for number in range(5)])
        temporary = Role.Name.like("Temp %")

        if staged:
            batched_unit_of_work.roles.delete_range(temporary)
            await batched_unit_of_work.save_changes_async()
        else:
            assert await batched_unit_of_work.roles.delete_range_async(temporary) == 5

        assert await persisted.count(Role, temporary) == 0
        assert await persisted.count(Role) == 2

    async def test_many_entities_are_inserted_updated_and_deleted_in_batches(self, batched_unit_of_work, persisted,
                                                                             new_role):
        roles = await batched_unit_of_work.roles.add_range_async([new_role() for _ in range(5)])
        assert await persisted.count(Role) == 7

        for number, role in enumerate(roles):
            role.Name = f"Renamed {number}"
        await batched_unit_of_work.roles.update_range_async(roles)
        assert await persisted.count(Role, Role.Name.like("Renamed %")) == 5

        assert await batched_unit_of_work.roles.delete_range_async(roles) == 5
        assert await persisted.count(Role) == 2


# ---------------------------------------------------------------------------
# Bulk operations go through the ORM: mapper events fire for every row
# ---------------------------------------------------------------------------

class TestOrmEvents:
    @pytest.fixture
    def mapper_events(self):
        """Record the Account rows the ORM updates and deletes (before_update / before_delete mapper events)."""
        recorded = {"before_update": [], "before_delete": []}
        listeners = {name: (lambda mapper, connection, target, name=name: recorded[name].append(target.AccountNumber))
                     for name in recorded}
        for name, listener in listeners.items():
            event.listen(Account, name, listener)
        yield recorded
        for name, listener in listeners.items():
            event.remove(Account, name, listener)

    @pytest.mark.parametrize("staged", [False, True], ids=["update_range_async", "update_range"])
    async def test_update_by_criteria_fires_update_events_for_every_row(self, unit_of_work, mapper_events, staged):
        ada = Account.AccountNumber.in_(["2600000001", "2600000002"])

        if staged:
            unit_of_work.accounts.update_range(ada, values={"Balance": Decimal("1.00")})
            await unit_of_work.save_changes_async()
        else:
            await unit_of_work.accounts.update_range_async(ada, values={"Balance": Decimal("1.00")})

        assert sorted(mapper_events["before_update"]) == ["2600000001", "2600000002"]

    @pytest.mark.parametrize("staged", [False, True], ids=["delete_range_async", "delete_range"])
    async def test_delete_by_criteria_fires_delete_events_for_every_row(self, unit_of_work, mapper_events, staged):
        without_transactions = Account.AccountNumber.in_(["2600000002", "2600000004"])

        if staged:
            unit_of_work.accounts.delete_range(without_transactions)
            await unit_of_work.save_changes_async()
        else:
            await unit_of_work.accounts.delete_range_async(without_transactions)

        assert sorted(mapper_events["before_delete"]) == ["2600000002", "2600000004"]


# ---------------------------------------------------------------------------
# delete_single / delete_range / delete_by_id (staged) and their _async forms (persisted)
# ---------------------------------------------------------------------------

class TestDelete:
    async def test_delete_single_stages_the_deletion(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000004")
        account = await unit_of_work.accounts.get_by_id_async(account_id)

        unit_of_work.accounts.delete_single(account)

        assert await persisted.get(Account, account_id) is not None
        await unit_of_work.save_changes_async()
        assert await persisted.get(Account, account_id) is None

    async def test_deleting_a_staged_new_entity_drops_it(self, unit_of_work, persisted, new_role):
        role = unit_of_work.roles.add_single(new_role())

        unit_of_work.roles.delete_single(role)
        result = await unit_of_work.save_changes_async()

        assert (result.added, await persisted.count(Role, Role.Name == role.Name)) == (0, 0)

    @pytest.mark.parametrize("operation", [
        pytest.param(lambda roles, role: roles.delete_single(role), id="delete_single"),
        pytest.param(lambda roles, role: roles.delete_single_async(role), id="delete_single_async"),
        pytest.param(lambda roles, role: roles.delete_range([role]), id="delete_range"),
    ])
    async def test_entity_that_was_never_saved_cannot_be_deleted(self, unit_of_work, new_role, operation, result_of):
        with pytest.raises(ValueError, match="never been saved"):
            await result_of(operation(unit_of_work.roles, new_role()))

    async def test_delete_single_async_deletes_at_once(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000004")
        account = await unit_of_work.accounts.get_by_id_async(account_id)

        await unit_of_work.accounts.delete_single_async(account)

        assert await persisted.get(Account, account_id) is None
        assert await unit_of_work.accounts.get_by_id_async(account_id) is None

    async def test_delete_by_id_is_staged_and_a_missing_record_is_reported(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000004")

        assert unit_of_work.accounts.delete_by_id(account_id) is None
        unit_of_work.accounts.delete_by_id(MISSING_GUID)
        assert await persisted.get(Account, account_id) is not None

        result = await unit_of_work.save_changes_async()

        assert await persisted.get(Account, account_id) is None
        assert (result.deleted, result.not_found) == (1, (("Account", MISSING_GUID),))

    @pytest.mark.parametrize("repository, find_id, expected", [
        pytest.param("accounts", lambda bank: bank.account_id("2600000004"), True, id="existing-guid-key"),
        pytest.param("accounts", lambda bank: MISSING_GUID, False, id="missing-guid-key"),
        pytest.param("account_types", lambda bank: bank.account_type_ids["Retirement"], True,
                     id="existing-integer-key"),
        pytest.param("account_types", lambda bank: 999_999, False, id="missing-integer-key"),
    ])
    async def test_delete_by_id_async_reports_whether_a_row_was_deleted(self, unit_of_work, bank, persisted,
                                                                       repository, find_id, expected):
        repository = getattr(unit_of_work, repository)

        assert await repository.delete_by_id_async(find_id(bank)) is expected
        assert await persisted.get(repository.model, find_id(bank)) is None

    async def test_delete_range_of_entities_returns_their_number(self, unit_of_work, bank, persisted):
        accounts = await unit_of_work.accounts.get_range_async(Account.AccountNumber.in_(["2600000004", "2600000002"]))

        assert unit_of_work.accounts.delete_range(accounts) == 2
        await unit_of_work.save_changes_async()

        assert await persisted.count(Account) == 3

    async def test_delete_range_by_criteria_is_staged_until_saved(self, unit_of_work, persisted):
        assert unit_of_work.accounts.delete_range(Account.Balance == 0) is None
        assert await persisted.count(Account) == 5

        await unit_of_work.save_changes_async()

        assert await persisted.count(Account, Account.Balance == 0) == 0

    async def test_delete_range_async_by_criteria_returns_the_row_count(self, unit_of_work, persisted):
        assert await unit_of_work.accounts.delete_range_async(Account.Balance == 0) == 1
        assert await persisted.count(Account) == 4

    async def test_delete_range_async_counts_only_rows_that_still_exist(self, unit_of_work, bank, session_factory):
        accounts = await unit_of_work.accounts.get_range_async(Account.AccountNumber.in_(["2600000004", "2600000002"]))
        async with session_factory() as other_session:
            await other_session.delete(await other_session.get(Account, bank.account_id("2600000004")))
            await other_session.commit()

        assert await unit_of_work.accounts.delete_range_async(accounts) == 1

    async def test_delete_refused_by_a_foreign_key_deletes_nothing(self, unit_of_work, bank, persisted):
        # Savings accounts 2600000001 and 2600000003 have transactions (ON DELETE RESTRICT).
        savings = Account.AccountTypeId == bank.account_type_ids["Savings"]

        with pytest.raises(IntegrityError):
            await unit_of_work.accounts.delete_range_async(savings)

        assert await persisted.count(Account, savings) == 3

    @pytest.mark.parametrize("persist", [False, True], ids=["delete_range", "delete_range_async"])
    async def test_delete_range_needs_entities_or_criteria(self, unit_of_work, persist, result_of):
        # Deleting every row needs an explicit criterion; nothing at all is refused.
        with pytest.raises(TypeError, match="iterable of entities, or SQL criteria"):
            await result_of(unit_of_work.accounts.delete_range_async() if persist
                            else unit_of_work.accounts.delete_range())

    @pytest.mark.parametrize("persist", [False, True], ids=["delete_range", "delete_range_async"])
    async def test_python_bool_is_not_a_criterion(self, unit_of_work, persist, result_of):
        with pytest.raises(TypeError):
            await result_of(unit_of_work.accounts.delete_range_async(True) if persist
                        else unit_of_work.accounts.delete_range(True))


# ---------------------------------------------------------------------------
# save (staged) and save_async (persisted): add or update
# ---------------------------------------------------------------------------

class TestSave:
    async def test_new_entity_without_a_key_is_added(self, unit_of_work, persisted, new_role):
        role = new_role()

        assert unit_of_work.roles.save(role) is role
        await unit_of_work.save_changes_async()

        assert await persisted.count(Role, Role.Name == role.Name) == 1

    async def test_loaded_entity_is_updated(self, unit_of_work, bank, persisted):
        account_type = await unit_of_work.account_types.get_by_id_async(bank.account_type_ids["Current"])
        account_type.Type = "Checking"

        assert unit_of_work.account_types.save(account_type) is account_type
        await unit_of_work.save_changes_async()

        assert (await persisted.get(AccountType, bank.account_type_ids["Current"])).Type == "Checking"

    async def test_new_entity_with_the_key_of_a_tracked_row_updates_that_row(self, unit_of_work, bank, persisted):
        tracked = await unit_of_work.account_types.get_by_id_async(bank.account_type_ids["Current"])

        result = unit_of_work.account_types.save(AccountType(Id=tracked.Id, Type="Checking"))
        await unit_of_work.save_changes_async()

        assert result is tracked
        assert tracked.Type == "Checking"
        assert (await persisted.get(AccountType, tracked.Id)).Type == "Checking"

    @pytest.mark.parametrize("find_id, expected_count", [
        pytest.param(lambda bank: bank.account_type_ids["Current"], 3, id="existing-row-is-updated"),
        pytest.param(lambda bank: 99, 4, id="missing-row-is-inserted"),
    ])
    @pytest.mark.parametrize("persist", [False, True], ids=["save", "save_async"])
    async def test_new_entity_with_a_key_is_updated_or_inserted_by_the_database(self, unit_of_work, bank, persisted,
                                                                               find_id, expected_count, persist):
        account_type_id = find_id(bank)
        entity = AccountType(Id=account_type_id, Type="Checking")

        if persist:
            await unit_of_work.account_types.save_async(entity)
        else:
            unit_of_work.account_types.save(entity)
            await unit_of_work.save_changes_async()

        assert (await persisted.get(AccountType, account_type_id)).Type == "Checking"
        assert await persisted.count(AccountType) == expected_count

    async def test_save_async_inserts_a_new_entity(self, unit_of_work, persisted, new_role):
        role = await unit_of_work.roles.save_async(new_role())

        assert (await persisted.get(Role, role.Id)).Name == role.Name

    async def test_save_async_updates_an_existing_entity(self, unit_of_work, bank, persisted):
        account_type = await unit_of_work.account_types.get_by_id_async(bank.account_type_ids["Current"])
        account_type.Type = "Checking"

        assert await unit_of_work.account_types.save_async(account_type) is account_type

        assert (await persisted.get(AccountType, account_type.Id)).Type == "Checking"

    async def test_staged_entity_is_saved_once(self, unit_of_work, persisted, new_role):
        role = new_role()

        unit_of_work.roles.save(role)
        unit_of_work.roles.save(role)
        await unit_of_work.save_changes_async()

        assert await persisted.count(Role, Role.Name == role.Name) == 1


# ---------------------------------------------------------------------------
# Staged changes and queries
# ---------------------------------------------------------------------------

class TestStagedChangesAndQueries:
    async def test_queries_do_not_see_staged_changes(self, unit_of_work, new_role):
        role = unit_of_work.roles.add_single(new_role())

        assert await unit_of_work.roles.count_async() == 2
        assert await unit_of_work.roles.exists_async(Role.Name == role.Name) is False

    async def test_queries_do_not_write_staged_updates(self, unit_of_work, bank):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))
        unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})

        assert await unit_of_work.accounts.count_async(Account.Balance == Decimal("1.00")) == 0
        assert await unit_of_work.accounts.sum_async(Account.Balance) == Decimal("425.00")

    async def test_query_returns_the_tracked_entity_with_its_staged_values(self, unit_of_work, bank):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))
        unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})

        again = await unit_of_work.accounts.get_single_async(Account.AccountNumber == "2600000001")

        assert again is account
        assert again.Balance == Decimal("1.00")

    async def test_queries_after_an_async_operation_see_what_it_committed(self, unit_of_work, new_role):
        role = await unit_of_work.roles.add_single_async(new_role())

        assert await unit_of_work.roles.exists_async(Role.Name == role.Name) is True
