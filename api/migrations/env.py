"""Alembic environment: the app's own engine and models."""

from alembic import context

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.db import Base, engine


def render_item(type_, obj, autogen_context):
    # Our UTC-aware column type is a plain timezone-aware DateTime in the database.
    if type_ == "type" and type(obj).__name__ == "UTCDateTime":
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations() -> None:
    # The app passes its open connection (needed for in-memory SQLite in tests).
    connection = context.config.attributes.get("connection")
    if connection is None:
        with engine.connect() as connection:
            _run(connection)
            connection.commit()
    else:
        _run(connection)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=connection.dialect.name == "sqlite",  # SQLite cannot ALTER most things
        render_item=render_item,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations()
