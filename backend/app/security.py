from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Usuario

ALGORITMO_JWT = "HS256"
LIMITE_ID_INT4 = 2147483647
_bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def definir_senha(usuario: Usuario, senha: str) -> None:
    usuario.senha_hash = hash_senha(senha)
    usuario.token_versao = (usuario.token_versao or 0) + 1


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("ascii"))
    except ValueError:
        return False


def criar_token(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "ver": usuario.token_versao,
        "iat": agora,
        "exp": agora + timedelta(days=get_settings().jwt_expire_days),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITMO_JWT)


DIAS_DISPOSITIVO = 180
TIPO_DISPOSITIVO = "dispositivo"


def criar_token_dispositivo(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "tipo": TIPO_DISPOSITIVO,
        "ver": usuario.token_versao,
        "iat": agora,
        "exp": agora + timedelta(days=DIAS_DISPOSITIVO),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITMO_JWT)


def dispositivo_confiavel(token: str | None, usuario: Usuario | None) -> bool:
    """Aparelho onde a usuária já entrou; deixa de valer quando a senha muda."""
    if not token or usuario is None:
        return False
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITMO_JWT])
        return (
            payload.get("tipo") == TIPO_DISPOSITIVO
            and int(payload["sub"]) == usuario.id
            and int(payload["ver"]) == usuario.token_versao
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return False


def _sessao_invalida() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Sessão inválida ou expirada. Entre novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    if credenciais is None:
        raise _sessao_invalida()
    try:
        payload = jwt.decode(credenciais.credentials, get_settings().jwt_secret, algorithms=[ALGORITMO_JWT])
        if payload.get("tipo") is not None:
            raise _sessao_invalida()
        usuario_id = int(payload["sub"])
        versao = int(payload["ver"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise _sessao_invalida()
    if not 1 <= usuario_id <= LIMITE_ID_INT4:
        # Id fora de int4 não existe no banco; recusar antes evita estourar a consulta.
        raise _sessao_invalida()
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or usuario.token_versao != versao:
        raise _sessao_invalida()
    return usuario
