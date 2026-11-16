# 002 — Generic Repository and Unit of Work

## Summary

Added a generic repository and a unit of work in `Data`, built on SQLAlchemy 2.x `AsyncSession`. They are intended to become the single way the application reads and writes the database. Existing services do not use them yet.

## Added

- `Data/Interfaces/i_repository.py` — `IRepository[TEntity]`, the repository contract.
- `Data/Implementations/repository.py` — `Repository`, the implementation.
- `Data/Interfaces/i_unit_of_work.py` — `IUnitofWork` and `SaveChangesResult`.
- `Data/Implementations/unit_of_work.py` — `UnitofWork`, the implementation.
- `pytest-asyncio` in `requirements.txt`; `asyncio_default_fixture_loop_scope = function` in `pytest.ini`.

## Operations

| Group | Staged (not persisted) | Persisted at once |
| --- | --- | --- |
| Add | `add_single`, `add_range` | `add_single_async`, `add_range_async` |
| Update | `update_single`, `update_range` | `update_single_async`, `update_range_async` |
| Delete | `delete_single`, `delete_range`, `delete_by_id` | `delete_single_async`, `delete_range_async`, `delete_by_id_async` |
| Save (add or update) | `save` | `save_async` |
| Query | — | `get_by_id_async`, `get_single_async`, `get_range_async`, `count_async`, `sum_async`, `exists_async` |

- Only methods ending in `_async` are awaited.
- Staged operations are persisted together by `IUnitofWork.save_changes_async()`.
- Queries support filters, includes (related objects), ordering, skip / take, paging and row locking (`for_update`).

## Fixes Found by Testing

- Copying collection changes from a detached entity to the entity the unit of work tracks could leave new related objects unsaved. Fixed in `Repository`.

## Testing

- Added 309 unit tests in `tests/unit/Data/Repository` and `tests/unit/Data/UnitOfWork`, run on SQLite in memory (`aiosqlite`).
- Covered every repository operation, filtering, ordering, paging, includes, entity tracking, missing records, batches, session handling, disposal, saving and rolling back.
- Verified all 1,626 unit tests locally with SQLAlchemy 2.1 and 2.0.

## Open Points

- `aiosqlite` is needed by the new tests but is not yet listed in `requirements.txt`.
- Services still use the previous data access code and have not been moved to the repository.
- A staged delete of a row removed by another connection only produces a SQLAlchemy warning when saving.