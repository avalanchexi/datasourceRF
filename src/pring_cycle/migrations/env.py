from __future__ import annotations

from alembic import context
from sqlalchemy.engine import Connection


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if not isinstance(connection, Connection):
        raise RuntimeError("migration_connection_required")
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
