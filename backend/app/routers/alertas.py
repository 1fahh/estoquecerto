from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alerta, Produto, Usuario
from app.schemas import AlertaOut
from app.security import get_current_user
from app.services import estoque

router = APIRouter(prefix="/alertas", tags=["Alertas"])


@router.get("", response_model=list[AlertaOut])
def listar_alertas(
    situacao: Literal["ativo", "encerrado", "todos"] = "ativo",
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> list[AlertaOut]:
    consulta = select(Alerta, Produto).join(Produto, Produto.id == Alerta.produto_id)
    if situacao != "todos":
        consulta = consulta.where(Alerta.situacao == situacao)
    linhas = db.execute(consulta.order_by(desc(Alerta.criado_em), desc(Alerta.id))).all()
    saldos = estoque.saldos_em_lote(db, {produto.id for _, produto in linhas})
    return [
        AlertaOut(
            id=alerta.id,
            produto_id=produto.id,
            produto_nome=produto.nome,
            unidade=produto.unidade,
            saldo_no_momento=alerta.saldo_no_momento,
            saldo_atual=saldos.get(produto.id, 0),
            limite=alerta.limite,
            criado_em=alerta.criado_em,
            encerrado_em=alerta.encerrado_em,
            situacao=alerta.situacao,
        )
        for alerta, produto in linhas
    ]
