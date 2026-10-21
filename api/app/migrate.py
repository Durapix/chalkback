"""Bring the database schema up to date at startup (Alembic)."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

log = logging.getLogger(__name__)

API_DIR = Path(__file__).resolve().parent.parent
BASELINE = "0001"


def alembic_config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    return config


def upgrade_db(engine: Engine) -> None:
    """Run pending migrations. Databases created before migrations existed (by create_all,
    with exactly the baseline schema) are stamped as the baseline first."""
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables and "users" in tables:
            log.info("Existing database without migration history: stamping baseline")
            command.stamp(config, BASELINE)
        command.upgrade(config, "head")
