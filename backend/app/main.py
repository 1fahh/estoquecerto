import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

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
        arquivo = (_raiz_static / caminho).resolve()
        if caminho and arquivo.is_file() and arquivo.is_relative_to(_raiz_static):
            return FileResponse(arquivo)
        return FileResponse(_raiz_static / "index.html")
