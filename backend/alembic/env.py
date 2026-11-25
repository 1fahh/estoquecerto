import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, event, pool

from app import models  # noqa: F401  (registra os modelos no metadata)
from app.config import get_settings
from app.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
DB_SCHEMA = os.environ.get("DB_SCHEMA", "").strip()


def _validar_schema(nome: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", nome):
        raise ValueError(f"DB_SCHEMA inválido: {nome!r}")
    return nome


def _define_search_path(engine) -> None:
    if not DB_SCHEMA:
        return
    schema = _validar_schema(DB_SCHEMA)

    @event.listens_for(engine, "connect")
    def _ao_conectar(dbapi_conexao, _registro) -> None:
        dbapi_conexao.autocommit = True
        with dbapi_conexao.cursor() as cursor:
            cursor.execute(f"SET search_path TO {schema}")
        dbapi_conexao.autocommit = False


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    _define_search_path(engine)
    with engine.connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
