from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Movimentacao, Produto, Usuario
from app.schemas import AjusteIn, EntradaIn, MovLista, MovOut, RegistroOut, SaidaIn, UltimaEntradaOut
from app.security import get_current_user
from app.services import estoque

router = APIRouter(prefix="/movimentacoes", tags=["Movimentações"])
FUSO_NEGOCIO = ZoneInfo("America/Sao_Paulo")


class MaisUsadoOut(BaseModel):
    produto_id: int
    nome: str
    unidade: str
    saidas_30d: int


def _registro(resultado: dict) -> RegistroOut:
    movimento: Movimentacao = resultado["movimentacao"]
    return RegistroOut(
        movimentacao=_movimento_out(movimento, resultado["saldo_atual"]),
        saldo_anterior=resultado["saldo_anterior"],
        saldo_atual=resultado["saldo_atual"],
        limite=resultado["limite"],
        alerta=resultado["alerta"],
    )


def _movimento_out(movimento: Movimentacao, saldo_apos: Decimal) -> MovOut:
    return MovOut(
        id=movimento.id,
        produto_id=movimento.produto_id,
        produto_nome=movimento.produto.nome,
        unidade=movimento.produto.unidade,
        tipo=movimento.tipo,
        quantidade=movimento.quantidade,
        data_hora=movimento.data_hora,
        motivo=movimento.motivo,
        custo_unitario=movimento.custo_unitario,
        fornecedor=movimento.fornecedor,
        usuario_nome=movimento.usuario.nome,
        saldo_apos=saldo_apos,
    )


@router.post("/entrada", status_code=201, response_model=RegistroOut)
def registrar_entrada(
    dados: EntradaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
) -> RegistroOut:
    resultado = estoque.registrar_movimentacao(db, usuario, "entrada", dados.model_dump())
    return _registro(resultado)


@router.post("/saida", status_code=201, response_model=RegistroOut)
def registrar_saida(
    dados: SaidaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
) -> RegistroOut:
    resultado = estoque.registrar_movimentacao(db, usuario, "saida", dados.model_dump())
    return _registro(resultado)


@router.post("/ajuste", status_code=201, response_model=RegistroOut)
def registrar_ajuste(
    dados: AjusteIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
) -> RegistroOut:
    resultado = estoque.registrar_movimentacao(db, usuario, "ajuste", dados.model_dump())
    return _registro(resultado)


def _limites_do_dia(dia: date, fim: bool = False) -> datetime:
    if fim:
        dia = dia + timedelta(days=1)
    return datetime.combine(dia, time.min, tzinfo=FUSO_NEGOCIO).astimezone(timezone.utc)


@router.get("", response_model=MovLista)
def listar_movimentacoes(
    produto_id: int | None = None,
    tipo: Literal["entrada", "saida", "ajuste"] | None = None,
    de: date | None = None,
    ate: date | None = None,
    limite: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> MovLista:
    sinal = case((Movimentacao.tipo == "saida", -Movimentacao.quantidade), else_=Movimentacao.quantidade)
    janela = select(
        Movimentacao.id,
        Movimentacao.produto_id,
        Movimentacao.tipo,
        Movimentacao.quantidade,
        Movimentacao.data_hora,
        Movimentacao.motivo,
        Movimentacao.custo_unitario,
        Movimentacao.fornecedor,
        Movimentacao.usuario_id,
        func.sum(sinal)
        .over(
            partition_by=Movimentacao.produto_id,
            order_by=(Movimentacao.data_hora, Movimentacao.id),
        )
        .label("saldo_apos"),
    )
    if produto_id is not None:
        janela = janela.where(Movimentacao.produto_id == produto_id)
    historico = janela.subquery("historico")

    filtros = []
    if tipo is not None:
        filtros.append(historico.c.tipo == tipo)
    if de is not None:
        filtros.append(historico.c.data_hora >= _limites_do_dia(de))
    if ate is not None:
        filtros.append(historico.c.data_hora < _limites_do_dia(ate, fim=True))

    consulta = (
        select(historico, Produto.nome.label("produto_nome"), Produto.unidade, Usuario.nome.label("usuario_nome"))
        .join(Produto, Produto.id == historico.c.produto_id)
        .join(Usuario, Usuario.id == historico.c.usuario_id)
        .where(*filtros)
    )
    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    linhas = db.execute(
        consulta.order_by(desc(historico.c.data_hora), desc(historico.c.id)).limit(limite).offset(offset)
    ).all()
    itens = [
        MovOut(
            id=linha.id,
            produto_id=linha.produto_id,
            produto_nome=linha.produto_nome,
            unidade=linha.unidade,
            tipo=linha.tipo,
            quantidade=linha.quantidade,
            data_hora=linha.data_hora,
            motivo=linha.motivo,
            custo_unitario=linha.custo_unitario,
            fornecedor=linha.fornecedor,
            usuario_nome=linha.usuario_nome,
            saldo_apos=linha.saldo_apos,
        )
        for linha in linhas
    ]
    return MovLista(itens=itens, total=total)


@router.get("/ultima-entrada/{produto_id}", response_model=UltimaEntradaOut)
def ultima_entrada(
    produto_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> UltimaEntradaOut:
    entrada = db.scalar(
        select(Movimentacao)
        .where(Movimentacao.produto_id == produto_id, Movimentacao.tipo == "entrada")
        .order_by(desc(Movimentacao.data_hora), desc(Movimentacao.id))
        .limit(1)
    )
    if entrada is None:
        raise HTTPException(status_code=404, detail="Nenhuma entrada registrada para este produto.")
    return UltimaEntradaOut(
        quantidade=entrada.quantidade,
        custo_unitario=entrada.custo_unitario,
        fornecedor=entrada.fornecedor,
        data_hora=entrada.data_hora,
    )


@router.get("/mais-usados", response_model=list[MaisUsadoOut])
def mais_usados(
    limite: int = Query(6, ge=1, le=50),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> list[MaisUsadoOut]:
    desde = datetime.now(timezone.utc) - timedelta(days=30)
    linhas = db.execute(
        select(
            Produto.id,
            Produto.nome,
            Produto.unidade,
            func.count(Movimentacao.id).label("saidas"),
        )
        .join(Movimentacao, Movimentacao.produto_id == Produto.id)
        .where(
            Produto.ativo.is_(True),
            Movimentacao.tipo == "saida",
            Movimentacao.data_hora >= desde,
        )
        .group_by(Produto.id)
        .order_by(desc("saidas"), Produto.nome)
        .limit(limite)
    ).all()
    return [
        MaisUsadoOut(produto_id=linha.id, nome=linha.nome, unidade=linha.unidade, saidas_30d=linha.saidas)
        for linha in linhas
    ]
