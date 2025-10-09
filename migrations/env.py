from __future__ import annotations

import logging
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from flask import current_app

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

def get_engine():
    try:
        return current_app.extensions["migrate"].db.get_engine()
    except TypeError:
        return current_app.extensions["migrate"].db.engine

def get_metadata():
    return current_app.extensions["migrate"].db.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = get_engine().url
    context.configure(url=str(url), target_metadata=get_metadata(), literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=get_metadata())

        with context.begin_transaction():
            context.run_migrations()

def run_migrations() -> None:
    config.set_main_option(
        "sqlalchemy.url",
        str(get_engine().url).replace("%", "%%"),
    )
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()

if Path("./migrations").exists():
    run_migrations()
