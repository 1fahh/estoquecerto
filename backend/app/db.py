import os
import re
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

PADRAO_SCHEMA = re.compile(r"[a-z_][a-z0-9_]{0,62}")


def criar_engine(url: str, **opcoes) -> Engine:
    engine = create_engine(url, **opcoes)
    schema = os.environ.get("DB_SCHEMA", "").strip()
    if not schema:
        return engine
    if not PADRAO_SCHEMA.fullmatch(schema):
        raise ValueError(f"DB_SCHEMA inválido: {schema!r}")

    @event.listens_for(engine, "connect")
    def _ao_conectar(dbapi_conexao, _registro) -> None:
        dbapi_conexao.autocommit = True
        with dbapi_conexao.cursor() as cursor:
            cursor.execute(f"SET search_path TO {schema}")
        dbapi_conexao.autocommit = False

    return engine


engine = criar_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
