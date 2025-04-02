from alembic import context
from database_orm import Base, engine
import models.base_entity
import models.accounts
import models.user
import models.customer
import models.account_type
import models.transaction_status
import models.transaction_mode
import models.transaction_type
import models.transaction
import models.Roles
import models.Staff


# Get Alembic config
config = context.config

# Set database URL dynamically from ORM engine
config.set_main_option("sqlalchemy.url", str(engine.url))

# Metadata for Alembic migrations
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
