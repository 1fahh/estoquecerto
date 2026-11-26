import logging
import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import DataError, SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import Usuario
from app.routers import alertas, auth, categorias, configuracoes, movimentacoes, produtos, relatorios
from app.security import hash_senha

logging.basicConfig(level=logging.INFO)


def criar_admin_inicial() -> None:
    settings = get_settings()
    if not (settings.admin_email and settings.admin_password):
        return
    with SessionLocal() as db:
        if db.scalar(select(func.count(Usuario.id))):
            return
        if len(settings.admin_password) < 8:
            raise RuntimeError("ADMIN_PASSWORD precisa ter pelo menos 8 caracteres.")
        db.add(
            Usuario(
                nome=settings.admin_nome,
                email=settings.admin_email.strip().lower(),
                senha_hash=hash_senha(settings.admin_password),
            )
        )
        db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    criar_admin_inicial()
    yield


app = FastAPI(
    title="EstoqueCerto",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


def _sem_nao_finitos(valor: Any) -> Any:
    # A resposta 422 ecoa o valor recebido, e ele precisa ser serializável: JSON aceita NaN e
    # Infinity (o JSON final não aceita) e surrogates (não codificam em UTF-8).
    if isinstance(valor, float) and not math.isfinite(valor):
        return str(valor)
    if isinstance(valor, str):
        return valor.encode("utf-8", "backslashreplace").decode("utf-8")
    if isinstance(valor, dict):
        return {chave: _sem_nao_finitos(item) for chave, item in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_sem_nao_finitos(item) for item in valor]
    return valor


@app.exception_handler(RequestValidationError)
async def erro_de_validacao(_request: Request, erro: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(_sem_nao_finitos(erro.errors()))},
    )


CODIGOS_FORA_DA_FAIXA = {"22003", "22008"}  # numeric_value_out_of_range, datetime_field_overflow


@app.exception_handler(DataError)
async def valor_fora_da_faixa(_request: Request, erro: DataError) -> JSONResponse:
    # Ids, offsets e datas que o banco não aceita (ex.: inteiro fora de int4) viram 422, não 500.
    # Outros erros de dados continuam sendo erro interno, não "valor fora da faixa".
    if getattr(erro.orig, "sqlstate", None) not in CODIGOS_FORA_DA_FAIXA:
        raise erro
    return JSONResponse(status_code=422, content={"detail": "Valor fora da faixa aceita pelo sistema."})


@app.middleware("http")
async def cabecalhos_de_seguranca(request: Request, call_next) -> Response:
    resposta = await call_next(request)
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resposta


@app.get("/api/health", tags=["Saúde"])
def health():
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse({"status": "erro", "banco": "erro"}, status_code=503)
    return {"status": "ok", "banco": "ok"}


app.include_router(auth.router, prefix="/api", tags=["Autenticação"])
app.include_router(categorias.router, prefix="/api", tags=["Categorias"])
app.include_router(produtos.router, prefix="/api", tags=["Produtos"])
app.include_router(movimentacoes.router, prefix="/api", tags=["Movimentações"])
app.include_router(alertas.router, prefix="/api", tags=["Alertas"])
app.include_router(relatorios.router, prefix="/api", tags=["Relatórios"])
app.include_router(configuracoes.router, prefix="/api", tags=["Configurações"])


_static = get_settings().static_path
if _static.is_dir() and (_static / "index.html").is_file():
    _raiz_static = _static.resolve()

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str) -> FileResponse:
        if caminho == "api" or caminho.startswith("api/"):
            raise HTTPException(status_code=404, detail="Rota não encontrada.")
        if "\x00" in caminho:
            # resolve() não aceita byte nulo no caminho (ValueError), então recusa antes.
            raise HTTPException(status_code=404, detail="Rota não encontrada.")
        arquivo = (_raiz_static / caminho).resolve()
        if caminho and arquivo.is_file() and arquivo.is_relative_to(_raiz_static):
            return FileResponse(arquivo)
        return FileResponse(_raiz_static / "index.html")
