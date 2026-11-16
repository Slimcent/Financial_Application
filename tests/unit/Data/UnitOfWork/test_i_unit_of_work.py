"""The unit of work contract (Data/Interfaces/i_unit_of_work.py), SaveChangesResult, and how UnitOfWork implements
it."""
import dataclasses
import inspect
import typing

import pytest

import Models.Entities
from Data.Implementations.unit_of_work import UnitOfWork
from Data.Interfaces.i_unit_of_work import IUnitOfWork, SaveChangesResult
from Models.Entities import Base, BaseEntity

PUBLIC_METHODS = sorted(name for name, member in vars(IUnitOfWork).items()
                        if inspect.isfunction(member) and not name.startswith("_"))
REPOSITORY_PROPERTIES = sorted(name for name, member in vars(IUnitOfWork).items()
                               if isinstance(member, property) and name != "is_active")
ENTITIES = {getattr(Models.Entities, name) for name in Models.Entities.__all__} - {Base, BaseEntity}


def test_unit_of_work_implements_the_whole_contract():
    assert issubclass(UnitOfWork, IUnitOfWork)
    assert not UnitOfWork.__abstractmethods__


def test_contract_declares_repository_access_saving_and_rolling_back():
    assert PUBLIC_METHODS == ["get_repository", "rollback_async", "save_changes_async"]


@pytest.mark.parametrize("name", PUBLIC_METHODS)
def test_only_async_suffixed_methods_are_awaited(name):
    expected = name.endswith("_async")

    assert inspect.iscoroutinefunction(getattr(IUnitOfWork, name)) is expected
    assert inspect.iscoroutinefunction(getattr(UnitOfWork, name)) is expected


def test_unit_of_work_is_used_with_async_with():
    assert inspect.iscoroutinefunction(UnitOfWork.__aenter__)
    assert inspect.iscoroutinefunction(UnitOfWork.__aexit__)


def test_there_is_a_repository_property_for_every_entity():
    models = [typing.get_args(typing.get_type_hints(getattr(IUnitOfWork, name).fget)["return"])[0]
              for name in REPOSITORY_PROPERTIES]

    assert sorted(model.__name__ for model in models) == sorted(entity.__name__ for entity in ENTITIES)


@pytest.mark.parametrize("batch_size", [0, -1])
def test_batch_size_must_be_positive(batch_size):
    with pytest.raises(ValueError, match="batch_size"):
        UnitOfWork(lambda: None, batch_size=batch_size)


# ---------------------------------------------------------------------------
# SaveChangesResult
# ---------------------------------------------------------------------------

def test_save_changes_result_defaults_to_nothing_written():
    result = SaveChangesResult()

    assert (result.added, result.updated, result.deleted, result.not_found, result.total) == (0, 0, 0, (), 0)


@pytest.mark.parametrize("added, updated, deleted, total", [(1, 0, 0, 1), (2, 3, 4, 9), (0, 0, 5, 5)])
def test_save_changes_result_total_counts_every_row_written(added, updated, deleted, total):
    assert SaveChangesResult(added=added, updated=updated, deleted=deleted).total == total


def test_save_changes_result_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        SaveChangesResult().added = 1  # type: ignore[misc]
