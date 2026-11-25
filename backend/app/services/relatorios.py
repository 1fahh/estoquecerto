from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import case, desc, func, select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from app.models import Alerta, Categoria, Configuracao, Movimentacao, Produto, Usuario
from app.services import estoque

FUSO_NEGOCIO = ZoneInfo("America/Sao_Paulo")
PERIODO_PARADO_PADRAO = 30
LIMITE_ALERTAS_PAINEL = 5
DIAS_QUINZENA = 15
CENTAVOS = Decimal("0.01")

TipoMovimentacao = Literal["entrada", "saida", "ajuste"]


def agora() -> datetime:
    return datetime.now(timezone.utc)


def hoje() -> date:
    return datetime.now(FUSO_NEGOCIO).date()


def inicio_do_dia(dia: date) -> datetime:
    return datetime.combine(dia, time.min, tzinfo=FUSO_NEGOCIO).astimezone(timezone.utc)


def fim_do_dia(dia: date) -> datetime:
    return inicio_do_dia(dia + timedelta(days=1))


def periodo_parado(db: Session) -> int:
    configuracao = db.get(Configuracao, 1)
    return configuracao.periodo_parado_dias if configuracao else PERIODO_PARADO_PADRAO


def valor_em_estoque(saldo: Decimal, custo_unitario: Decimal | None) -> Decimal | None:
    if custo_unitario is None:
        return None
    return (saldo * custo_unitario).quantize(CENTAVOS)


def estoque_atual(db: Session) -> list[dict[str, Any]]:
    linhas = db.execute(
        select(Produto, Categoria.nome.label("categoria_nome"))
        .outerjoin(Categoria, Categoria.id == Produto.categoria_id)
        .where(Produto.ativo.is_(True))
        .order_by(Produto.nome, Produto.id)
    ).all()
    situacoes = estoque.situacoes_em_lote(db, [linha.Produto for linha in linhas])
    resultado = []
    for linha in linhas:
        produto = linha.Produto
        situacao = situacoes[produto.id]
        resultado.append(
            {
                "id": produto.id,
                "nome": produto.nome,
                "codigo": produto.codigo,
                "categoria_nome": linha.categoria_nome,
                "unidade": produto.unidade,
                "custo_unitario": produto.custo_unitario,
                "estoque_minimo": produto.estoque_minimo,
                "percentual_alerta": produto.percentual_alerta,
                "saldo": situacao.saldo,
                "limite": situacao.limite,
                "em_alerta": situacao.em_alerta,
                "quantidade_referencia": situacao.referencia,
                "ultima_movimentacao_em": situacao.ultima_movimentacao_em,
                "valor_estoque": valor_em_estoque(situacao.saldo, produto.custo_unitario),
            }
        )
    return resultado


def alertas_ativos(db: Session) -> list[dict[str, Any]]:
    linhas = db.execute(
        select(Alerta, Produto)
        .join(Produto, Produto.id == Alerta.produto_id)
        .where(Alerta.situacao == "ativo")
        .order_by(desc(Alerta.criado_em), desc(Alerta.id))
    ).all()
    saldos = estoque.saldos_em_lote(db, {produto.id for _, produto in linhas})
    return [
        {
            "id": alerta.id,
            "produto_id": produto.id,
            "produto_nome": produto.nome,
            "unidade": produto.unidade,
            "saldo_no_momento": alerta.saldo_no_momento,
            "saldo_atual": saldos.get(produto.id, Decimal(0)),
            "limite": alerta.limite,
            "criado_em": alerta.criado_em,
            "encerrado_em": alerta.encerrado_em,
            "situacao": alerta.situacao,
        }
        for alerta, produto in linhas
    ]


def parados(db: Session, dias: int) -> dict[str, Any]:
    momento = agora()
    corte = momento - timedelta(days=dias)
    produtos = db.scalars(select(Produto).where(Produto.ativo.is_(True))).all()
    ids = [produto.id for produto in produtos]
    saldos = estoque.saldos_em_lote(db, ids)
    ultimas_saidas = dict(
        db.execute(
            select(Movimentacao.produto_id, func.max(Movimentacao.data_hora))
            .where(Movimentacao.tipo == "saida", Movimentacao.produto_id.in_(ids))
            .group_by(Movimentacao.produto_id)
        ).all()
    ) if ids else {}
    primeiras_movimentacoes = dict(
        db.execute(
            select(Movimentacao.produto_id, func.min(Movimentacao.data_hora))
            .where(Movimentacao.produto_id.in_(ids))
            .group_by(Movimentacao.produto_id)
        ).all()
    ) if ids else {}

    itens = []
    for produto in produtos:
        saldo = saldos.get(produto.id, Decimal(0))
        if saldo <= 0:
            continue
        ultima_saida = ultimas_saidas.get(produto.id)
        referencia = ultima_saida or primeiras_movimentacoes[produto.id]
        if referencia >= corte:
            continue
        itens.append(
            {
                "produto_id": produto.id,
                "nome": produto.nome,
                "unidade": produto.unidade,
                "saldo": saldo,
                "custo_unitario": produto.custo_unitario,
                "valor": valor_em_estoque(saldo, produto.custo_unitario),
                "dias_parado": (momento - referencia).days,
                "ultima_saida_em": ultima_saida,
            }
        )
    itens.sort(key=lambda item: (-item["dias_parado"], item["nome"]))
    return {
        "dias": dias,
        "itens": itens,
        "total_valor": sum((item["valor"] for item in itens if item["valor"] is not None), Decimal(0)).quantize(CENTAVOS),
        "sem_custo_qtd": sum(1 for item in itens if item["valor"] is None),
    }


def painel(db: Session) -> dict[str, Any]:
    dia = hoje()
    alertas = alertas_ativos(db)
    relatorio_parados = parados(db, periodo_parado(db))
    return {
        "data": dia,
        "produtos_ativos": db.scalar(select(func.count(Produto.id)).where(Produto.ativo.is_(True))) or 0,
        "alertas_ativos": alertas[:LIMITE_ALERTAS_PAINEL],
        "total_alertas": len(alertas),
        "parados_qtd": len(relatorio_parados["itens"]),
        "parados_valor": relatorio_parados["total_valor"],
        "registros_hoje": db.scalar(
            select(func.count(Movimentacao.id)).where(
                Movimentacao.data_hora >= inicio_do_dia(dia),
                Movimentacao.data_hora < fim_do_dia(dia),
            )
        )
        or 0,
    }


def movimentacoes(
    db: Session,
    *,
    produto_id: int | None = None,
    tipo: TipoMovimentacao | None = None,
    de: date | None = None,
    ate: date | None = None,
) -> list[Row]:
    sinal = case((Movimentacao.tipo == "saida", -Movimentacao.quantidade), else_=Movimentacao.quantidade)
    historico_base = select(
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
        .over(partition_by=Movimentacao.produto_id, order_by=(Movimentacao.data_hora, Movimentacao.id))
        .label("saldo_apos"),
    )
    if produto_id is not None:
        historico_base = historico_base.where(Movimentacao.produto_id == produto_id)
    historico = historico_base.subquery("historico")

    filtros = []
    if tipo is not None:
        filtros.append(historico.c.tipo == tipo)
    if de is not None:
        filtros.append(historico.c.data_hora >= inicio_do_dia(de))
    if ate is not None:
        filtros.append(historico.c.data_hora < fim_do_dia(ate))

    consulta = (
        select(
            historico,
            Produto.nome.label("produto_nome"),
            Produto.unidade,
            Usuario.nome.label("usuario_nome"),
        )
        .join(Produto, Produto.id == historico.c.produto_id)
        .join(Usuario, Usuario.id == historico.c.usuario_id)
        .where(*filtros)
        .order_by(desc(historico.c.data_hora), desc(historico.c.id))
    )
    return db.execute(consulta).all()
