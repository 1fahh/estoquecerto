from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Configuracao, Usuario
from app.schemas import ConfigIn, ConfigOut
from app.security import get_current_user

router = APIRouter()


def obter_configuracao(db: Session) -> Configuracao:
    configuracao = db.get(Configuracao, 1)
    if configuracao is None:
        configuracao = Configuracao(id=1)
        db.add(configuracao)
        db.flush()
    return configuracao


@router.get("/configuracoes", response_model=ConfigOut)
def obter(db: Session = Depends(get_db), _usuario: Usuario = Depends(get_current_user)) -> ConfigOut:
    return ConfigOut.model_validate(obter_configuracao(db))


@router.put("/configuracoes", response_model=ConfigOut)
def atualizar(
    dados: ConfigIn,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
) -> ConfigOut:
    configuracao = obter_configuracao(db)
    configuracao.periodo_parado_dias = dados.periodo_parado_dias
    configuracao.percentual_alerta_padrao = dados.percentual_alerta_padrao
    db.commit()
    return ConfigOut.model_validate(configuracao)
