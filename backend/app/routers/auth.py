import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.schemas import LoginIn, TokenOut, TrocarSenhaIn, UsuarioOut
from app.security import criar_token, get_current_user, hash_senha, verificar_senha

router = APIRouter()

LIMITE_TENTATIVAS = 10
JANELA_SEGUNDOS = 300
_tentativas_por_ip: dict[str, deque[float]] = defaultdict(deque)
_trava = threading.Lock()


def _registrar_tentativa(ip: str) -> None:
    agora = time.monotonic()
    with _trava:
        tentativas = _tentativas_por_ip[ip]
        while tentativas and agora - tentativas[0] > JANELA_SEGUNDOS:
            tentativas.popleft()
        if len(tentativas) >= LIMITE_TENTATIVAS:
            raise HTTPException(
                status_code=429,
                detail="Muitas tentativas de login. Aguarde alguns minutos e tente de novo.",
            )
        tentativas.append(agora)


@router.post("/auth/login", response_model=TokenOut)
def login(dados: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    ip = request.client.host if request.client else "desconhecido"
    _registrar_tentativa(ip)
    usuario = db.scalar(select(Usuario).where(Usuario.email == dados.email.lower()))
    if usuario is None or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    return TokenOut(
        access_token=criar_token(usuario.id),
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.get("/auth/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_user)) -> UsuarioOut:
    return UsuarioOut.model_validate(usuario)


@router.post("/auth/trocar-senha", status_code=204, response_class=Response)
def trocar_senha(
    dados: TrocarSenhaIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not verificar_senha(dados.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    usuario.senha_hash = hash_senha(dados.nova_senha)
    db.commit()
    return Response(status_code=204)
