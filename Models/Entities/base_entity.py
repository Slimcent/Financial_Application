import uuid
from datetime import datetime
from typing import Any, Final

from sqlalchemy import DDL, MetaData, Table, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Mapper, mapped_column

from Models.Entities.column_types import GUID, UTC_NOW_SERVER_DEFAULT, UtcDateTime, utc_now

# Constraint / index names generated for every table (MySQL identifiers are limited to 64 characters).
NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}

# Relationship loading for the async ORM: nothing is lazy-loaded implicitly. Related objects must be loaded
# explicitly in the query (joinedload / selectinload). A many-to-one whose target is already in the session
# is still returned without SQL; anything that would need SQL raises at once instead of failing later with
# MissingGreenlet.
LAZY: Final = "raise_on_sql"

# Raw SQL updates do not go through the ORM's onupdate, so on MySQL/MariaDB a trigger keeps UpdatedAt in UTC.
UPDATED_AT_TRIGGER_DIALECTS: Final = ("mysql", "mariadb")


def updated_at_trigger_name(table_name: str) -> str:
    return f"trg_{table_name}_UpdatedAt"


def updated_at_trigger_sql(table_name: str) -> str:
    """MySQL trigger: an UPDATE that does not change UpdatedAt itself gets the current UTC time.

    ORM updates always write a new UpdatedAt (onupdate), which the trigger keeps as it is.
    """
    return (
        f"CREATE TRIGGER `{updated_at_trigger_name(table_name)}` BEFORE UPDATE ON `{table_name}` "
        "FOR EACH ROW SET NEW.`UpdatedAt` = "
        "IF(NEW.`UpdatedAt` <=> OLD.`UpdatedAt`, UTC_TIMESTAMP(6), NEW.`UpdatedAt`)"
    )


class Base(DeclarativeBase):
    """Declarative base for every entity. Its metadata is the one used by Alembic."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Columns annotated with these Python types get the shared column types by default.
    type_annotation_map = {
        uuid.UUID: GUID,
        datetime: UtcDateTime(),
    }


class BaseEntity(Base):
    """Abstract base shared by all entities.

    It is not mapped to a table and has no primary key: its columns are copied into each
    entity's table, and every entity declares its own primary key.

    CreatedAt / UpdatedAt are UTC:
    - ORM inserts: both get the same instant (before_insert below); ORM updates: UpdatedAt via onupdate.
      The values are set by the application, so they are known right after a flush without reloading.
    - Raw SQL inserts: database default UTC_TIMESTAMP(6); raw SQL updates: the UpdatedAt trigger.
    CreatedBy / UpdatedBy are optional and are not filled in automatically.
    """

    __abstract__ = True

    CreatedAt: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now,
                                                server_default=UTC_NOW_SERVER_DEFAULT)
    UpdatedAt: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, onupdate=utc_now,
                                                server_default=UTC_NOW_SERVER_DEFAULT)
    CreatedBy: Mapped[uuid.UUID | None] = mapped_column(GUID)
    UpdatedBy: Mapped[uuid.UUID | None] = mapped_column(GUID)

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        table = cls.__dict__.get("__table__")
        if isinstance(table, Table) and "UpdatedAt" in table.c:
            for dialect_name in UPDATED_AT_TRIGGER_DIALECTS:
                event.listen(table, "after_create",
                             DDL(updated_at_trigger_sql(table.name)).execute_if(dialect=dialect_name))

    def _apply_insert_timestamps(self, now: datetime) -> None:
        """Give a new row one creation instant; values that were set explicitly are kept."""
        if self.CreatedAt is None:
            self.CreatedAt = now
        if self.UpdatedAt is None:
            self.UpdatedAt = self.CreatedAt


@event.listens_for(BaseEntity, "before_insert", propagate=True)
def _set_insert_timestamps(mapper: Mapper[Any], connection: Any, target: BaseEntity) -> None:
    target._apply_insert_timestamps(utc_now())
