import ipaddress
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.schemas import LoginIn, TokenOut, TrocarSenhaIn, UsuarioOut
from app.config import get_settings
from app.security import (
    DIAS_DISPOSITIVO,
    criar_token,
    criar_token_dispositivo,
    definir_senha,
    get_current_user,
    dispositivo_confiavel,
    verificar_senha,
)

router = APIRouter()

LIMITE_POR_IP = 10
LIMITE_POR_EMAIL = 30
JANELA_SEGUNDOS = 300
COOKIE_DISPOSITIVO = "ec_dispositivo"
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
    bruto = encaminhado.split(",")[-1].strip() if encaminhado.strip() else (
        request.client.host if request.client else "desconhecido"
    )
    try:
        endereco = ipaddress.ip_address(bruto)
    except ValueError:
        return bruto
    if endereco.version == 6:
        return str(ipaddress.ip_network(f"{endereco}/64", strict=False))
    return str(endereco)


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


def reservar_tentativa(chave_ip: str, chave_email: str, dispositivo_confiavel: bool = False) -> float:
    """Conta a tentativa já na checagem, para que tentativas simultâneas não furem o limite.

    Por IP: 10 falhas. Por conta: 30 falhas bloqueiam qualquer IP; só passa um aparelho
    onde a usuária já entrou antes (cookie assinado), para o ataque não trancar a dona.
    """
    with _trava:
        agora = time.monotonic()
        if _recentes(chave_ip, agora) >= LIMITE_POR_IP:
            raise _BLOQUEADO
        if _recentes(chave_email, agora) >= LIMITE_POR_EMAIL and not dispositivo_confiavel:
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


def _marcar_dispositivo(response: Response, usuario: Usuario) -> None:
    response.set_cookie(
        COOKIE_DISPOSITIVO,
        criar_token_dispositivo(usuario),
        max_age=DIAS_DISPOSITIVO * 86400,
        httponly=True,
        secure=get_settings().app_url.startswith("https://"),
        samesite="strict",
        path="/api/auth",
    )


@router.post("/auth/login", response_model=TokenOut)
def login(dados: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    email = dados.email.lower()
    chaves = (f"ip:{ip_do_cliente(request)}", f"email:{email}")
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    confiavel = dispositivo_confiavel(request.cookies.get(COOKIE_DISPOSITIVO), usuario)
    marca = reservar_tentativa(*chaves, dispositivo_confiavel=confiavel)
    if usuario is None or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    liberar_tentativa(marca, *chaves)
    _marcar_dispositivo(response, usuario)
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
    response: Response,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenOut:
    if not verificar_senha(dados.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    definir_senha(usuario, dados.nova_senha)
    db.commit()
    _marcar_dispositivo(response, usuario)
    return TokenOut(access_token=criar_token(usuario), usuario=UsuarioOut.model_validate(usuario))
