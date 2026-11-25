import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.schemas import LoginIn, TokenOut, TrocarSenhaIn, UsuarioOut
from app.security import criar_token, definir_senha, get_current_user, verificar_senha

router = APIRouter()

LIMITE_POR_IP = 10
LIMITE_POR_EMAIL = 30
JANELA_SEGUNDOS = 300
_tentativas: dict[str, deque[float]] = defaultdict(deque)
_trava = threading.Lock()
_BLOQUEADO = HTTPException(
    status_code=429,
    detail="Muitas tentativas de login. Aguarde alguns minutos e tente de novo.",
)


def ip_do_cliente(request: Request) -> str:
    # O proxy do Render ACRESCENTA o IP real ao fim do X-Forwarded-For; o cliente só
    # consegue forjar os itens anteriores, por isso vale o último.
    encaminhado = request.headers.get("x-forwarded-for", "")
    if encaminhado.strip():
        return encaminhado.split(",")[-1].strip()
    return request.client.host if request.client else "desconhecido"


def _recentes(chave: str, agora: float) -> int:
    tentativas = _tentativas.get(chave)
    if tentativas is None:
        return 0
    while tentativas and agora - tentativas[0] > JANELA_SEGUNDOS:
        tentativas.popleft()
    if not tentativas:
        del _tentativas[chave]
        return 0
    return len(tentativas)


def reservar_tentativa(chave_ip: str, chave_email: str) -> float:
    """Conta a tentativa já na checagem (tentativas simultâneas não furam o limite).

    O limite forte é por IP. O do e-mail só barra IPs que já erraram, para que um
    atacante não consiga trancar a dona da conta.
    """
    with _trava:
        agora = time.monotonic()
        falhas_ip = _recentes(chave_ip, agora)
        if falhas_ip >= LIMITE_POR_IP:
            raise _BLOQUEADO
        if _recentes(chave_email, agora) >= LIMITE_POR_EMAIL and falhas_ip > 0:
            raise _BLOQUEADO
        _tentativas[chave_ip].append(agora)
        _tentativas[chave_email].append(agora)
        return agora


def liberar_tentativa(marca: float, *chaves: str) -> None:
    with _trava:
        for chave in chaves:
            tentativas = _tentativas.get(chave)
            if tentativas is None:
                continue
            try:
                tentativas.remove(marca)
            except ValueError:
                pass
            if not tentativas:
                del _tentativas[chave]


@router.post("/auth/login", response_model=TokenOut)
def login(dados: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    email = dados.email.lower()
    chaves = (f"ip:{ip_do_cliente(request)}", f"email:{email}")
    marca = reservar_tentativa(*chaves)
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    liberar_tentativa(marca, *chaves)
    return TokenOut(
        access_token=criar_token(usuario),
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.get("/auth/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_user)) -> UsuarioOut:
    return UsuarioOut.model_validate(usuario)


@router.post("/auth/trocar-senha", response_model=TokenOut)
def trocar_senha(
    dados: TrocarSenhaIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenOut:
    if not verificar_senha(dados.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    definir_senha(usuario, dados.nova_senha)
    db.commit()
    return TokenOut(access_token=criar_token(usuario), usuario=UsuarioOut.model_validate(usuario))
