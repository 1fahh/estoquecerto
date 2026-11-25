import os
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
RAIZ_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(RAIZ_DIR / ".env")

SENHA_TESTE = "senha-de-teste-123"
TABELAS_LIMPAS = "movimentacoes, alertas, produtos, categorias, usuarios"


def _url_base() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ["DATABASE_URL"]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    partes = urlsplit(url)
    # O pooler do Neon recusa o parâmetro de conexão search_path; o endpoint direto aceita.
    if partes.hostname and "-pooler" in partes.hostname:
        netloc = partes.netloc.replace("-pooler", "", 1)
        url = urlunsplit(partes._replace(netloc=netloc))
    return url


SCHEMA_TESTE = f"test_{uuid.uuid4().hex[:12]}"
_URL_ADMIN = _url_base()
_URL_SCHEMA = (
    _URL_ADMIN + ("&" if "?" in _URL_ADMIN else "?") + "options=" + quote(f"-csearch_path={SCHEMA_TESTE}")
)
os.environ["DATABASE_URL"] = _URL_SCHEMA
os.environ["DB_SCHEMA"] = SCHEMA_TESTE
os.environ.setdefault("JWT_SECRET", "segredo-de-teste")

from app.db import engine as engine_app  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Usuario  # noqa: E402
from app.routers import auth as rota_auth  # noqa: E402
from app.security import criar_token, hash_senha  # noqa: E402


@pytest.fixture(scope="session")
def engine_admin() -> Iterator[Engine]:
    engine = create_engine(_URL_SCHEMA, pool_pre_ping=True)
    with engine.begin() as conexao:
        conexao.execute(text(f"CREATE SCHEMA {SCHEMA_TESTE}"))
    try:
        configuracao = Config(str(BACKEND_DIR / "alembic.ini"))
        configuracao.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cwd_anterior = os.getcwd()
        os.chdir(BACKEND_DIR)
        try:
            command.upgrade(configuracao, "head")
        finally:
            os.chdir(cwd_anterior)
        yield engine
    finally:
        engine_app.dispose()
        with engine.begin() as conexao:
            conexao.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA_TESTE} CASCADE"))
        engine.dispose()


@pytest.fixture(autouse=True)
def limpar_banco(engine_admin: Engine) -> Iterator[None]:
    rota_auth._tentativas_por_ip.clear()
    with engine_admin.begin() as conexao:
        schema_atual = conexao.execute(text("SELECT current_schema()")).scalar()
        if schema_atual != SCHEMA_TESTE:
            raise RuntimeError(f"Limpeza abortada: a sessão está no schema {schema_atual!r}, não no de teste.")
        conexao.execute(text(f"TRUNCATE {TABELAS_LIMPAS} RESTART IDENTITY CASCADE"))
        conexao.execute(
            text(
                "INSERT INTO configuracoes (id, periodo_parado_dias, percentual_alerta_padrao) "
                "VALUES (1, 30, 20) ON CONFLICT (id) DO UPDATE SET "
                "periodo_parado_dias = 30, percentual_alerta_padrao = 20"
            )
        )
    yield


@pytest.fixture
def usuario() -> Usuario:
    with Session(engine_app) as sessao:
        criado = Usuario(nome="Usuária de Teste", email="teste@estoquecerto.local", senha_hash=hash_senha(SENHA_TESTE))
        sessao.add(criado)
        sessao.commit()
        sessao.refresh(criado)
        return criado


@pytest.fixture
def anonimo() -> TestClient:
    return TestClient(app)


@pytest.fixture
def cliente(usuario: Usuario) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {criar_token(usuario.id)}"})


@pytest.fixture
def criar_produto(cliente: TestClient) -> Callable[..., dict]:
    def criar(nome: str = "Filtro de óleo", **campos) -> dict:
        resposta = cliente.post("/api/produtos", json={"nome": nome, "unidade": "un", **campos})
        assert resposta.status_code == 201, resposta.text
        return resposta.json()

    return criar


@pytest.fixture
def movimentar(cliente: TestClient) -> Callable[..., dict]:
    def movimentar(tipo: str, **dados) -> dict:
        resposta = cliente.post(f"/api/movimentacoes/{tipo}", json=dados)
        assert resposta.status_code == 201, resposta.text
        return resposta.json()

    return movimentar


@pytest.fixture
def sql() -> Callable[..., list | None]:
    def executar(comando: str, parametros: dict | None = None) -> list | None:
        with engine_app.begin() as conexao:
            resultado = conexao.execute(text(comando), parametros or {})
            return resultado.fetchall() if resultado.returns_rows else None

    return executar
