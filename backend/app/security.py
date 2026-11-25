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
_bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("ascii"))
    except ValueError:
        return False


def _segredo() -> str:
    segredo = get_settings().jwt_secret
    if not segredo:
        raise RuntimeError("JWT_SECRET não configurado.")
    return segredo


def criar_token(usuario_id: int) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "iat": agora,
        "exp": agora + timedelta(days=get_settings().jwt_expire_days),
    }
    return jwt.encode(payload, _segredo(), algorithm=ALGORITMO_JWT)


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
        payload = jwt.decode(credenciais.credentials, _segredo(), algorithms=[ALGORITMO_JWT])
        usuario_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _sessao_invalida()
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise _sessao_invalida()
    return usuario
