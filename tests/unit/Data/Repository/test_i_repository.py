"""The repository contract (Data/Interfaces/i_repository.py) and how Repository implements it.

Naming convention: only methods ending in `_async` are awaited. Add / update / delete / save exist in a staging form
(no suffix) and a persisting form (`_async`); queries always need the database, so they only exist as `_async`.
"""
import inspect

import pytest

from Data.Implementations.repository import Repository
from Data.Interfaces.i_repository import IRepository

STAGING_OPERATIONS = ["add_single", "add_range", "update_single", "update_range", "delete_single", "delete_range",
                      "delete_by_id", "save"]
QUERIES = ["get_by_id_async", "get_single_async", "get_range_async", "count_async", "sum_async", "exists_async"]
PUBLIC_METHODS = sorted(name for name, member in vars(IRepository).items()
                        if inspect.isfunction(member) and not name.startswith("_"))


def test_repository_implements_the_whole_contract():
    assert issubclass(Repository, IRepository)
    assert not Repository.__abstractmethods__


def test_contract_declares_staging_persisting_and_query_operations_only():
    expected = {*STAGING_OPERATIONS, *(f"{name}_async" for name in STAGING_OPERATIONS), *QUERIES, "query"}

    assert set(PUBLIC_METHODS) == expected


@pytest.mark.parametrize("name", PUBLIC_METHODS)
def test_only_async_suffixed_methods_are_awaited(name):
    expected = name.endswith("_async")

    assert inspect.iscoroutinefunction(getattr(IRepository, name)) is expected
    assert inspect.iscoroutinefunction(getattr(Repository, name)) is expected


@pytest.mark.parametrize("name", STAGING_OPERATIONS)
def test_staging_operation_has_a_persisting_async_variant(name):
    assert callable(getattr(IRepository, f"{name}_async"))


@pytest.mark.parametrize("name", QUERIES)
def test_query_has_no_staging_variant(name):
    assert not hasattr(IRepository, name.removesuffix("_async"))


def test_model_is_a_read_only_property():
    assert isinstance(inspect.getattr_static(Repository, "model"), property)
    assert inspect.getattr_static(Repository, "model").fset is None
