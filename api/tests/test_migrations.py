from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db import Base
from app.migrate import BASELINE, alembic_config, upgrade_db


def _revision(engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def test_migrations_build_exactly_the_models(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    upgrade_db(engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], "models changed without a migration: uv run alembic revision --autogenerate"
    assert _revision(engine) is not None


def test_databases_from_before_migrations_are_stamped_not_recreated(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    # The schema as create_all made it before Alembic: the baseline, without version table.
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, BASELINE)
        conn.exec_driver_sql("DROP TABLE alembic_version")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO users (email, name, password_hash, role, created_at, language, "
            "remind_by_email, remind_by_telegram) VALUES ('a@b.c', 'A', 'x', 'teacher', "
            "'2026-01-01 00:00:00', 'Serbian', 1, 0)"
        )
    upgrade_db(engine)
    assert "alembic_version" in inspect(engine).get_table_names()
    assert _revision(engine) is not None
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM users").scalar() == 1
    with engine.connect() as conn:
        columns = {c["name"] for c in inspect(conn).get_columns("users")}
    assert "telegram_link_code" in columns  # later migrations ran on top of the stamp
    upgrade_db(engine)  # idempotent
