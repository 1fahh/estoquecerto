from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Alerta, Movimentacao, Produto, Usuario
from app.services import notificador

CASAS = Decimal("0.001")
CENTAVOS = Decimal("0.01")
CEM = Decimal(100)


@dataclass(frozen=True)
class Situacao:
    saldo: Decimal
    referencia: Decimal
    limite: Decimal
    em_alerta: bool
    ultima_movimentacao_em: datetime | None


def quantizar(valor: Any) -> Decimal:
    return Decimal(valor).quantize(CASAS)


def formatar_quantidade(valor: Decimal) -> str:
    return format(valor.normalize(), "f").replace(".", ",")


def _expressao_saldo():
    return func.coalesce(
        func.sum(
            case(
                (Movimentacao.tipo == "saida", -Movimentacao.quantidade),
                else_=Movimentacao.quantidade,
            )
        ),
        0,
    )


def saldo(db: Session, produto_id: int) -> Decimal:
    return db.scalar(select(_expressao_saldo()).where(Movimentacao.produto_id == produto_id))


def saldos_em_lote(db: Session, produto_ids: Iterable[int]) -> dict[int, Decimal]:
    ids = list(produto_ids)
    if not ids:
        return {}
    linhas = db.execute(
        select(Movimentacao.produto_id, _expressao_saldo().label("saldo"))
        .where(Movimentacao.produto_id.in_(ids))
        .group_by(Movimentacao.produto_id)
    ).all()
    return {linha.produto_id: linha.saldo for linha in linhas}


def referencias_em_lote(db: Session, produto_ids: Iterable[int]) -> dict[int, Decimal]:
    ids = list(produto_ids)
    if not ids:
        return {}
    ordem = (Movimentacao.produto_id, Movimentacao.data_hora.desc(), Movimentacao.id.desc())
    entradas = db.execute(
        select(Movimentacao.produto_id, Movimentacao.quantidade)
        .where(Movimentacao.tipo == "entrada", Movimentacao.produto_id.in_(ids))
        .distinct(Movimentacao.produto_id)
        .order_by(*ordem)
    ).all()
    inventarios = db.execute(
        select(Movimentacao.produto_id, Movimentacao.quantidade)
        .where(
            Movimentacao.tipo == "ajuste",
            Movimentacao.inventario_inicial.is_(True),
            Movimentacao.quantidade > 0,
            Movimentacao.produto_id.in_(ids),
        )
        .distinct(Movimentacao.produto_id)
        .order_by(*ordem)
    ).all()
    referencias = {linha.produto_id: linha.quantidade for linha in inventarios}
    referencias.update({linha.produto_id: linha.quantidade for linha in entradas})
    return referencias


def calcular_limite(estoque_minimo: Decimal | None, percentual_alerta: Decimal, referencia: Decimal) -> Decimal:
    pelo_percentual = percentual_alerta / CEM * referencia
    return quantizar(max(estoque_minimo or Decimal(0), pelo_percentual))


def em_alerta(saldo_atual: Decimal, limite: Decimal) -> bool:
    return limite > 0 and saldo_atual <= limite


def situacoes_em_lote(db: Session, produtos: Sequence[Produto]) -> dict[int, Situacao]:
    if not produtos:
        return {}
    ids = [produto.id for produto in produtos]
    linhas = db.execute(
        select(
            Movimentacao.produto_id,
            _expressao_saldo().label("saldo"),
            func.max(Movimentacao.data_hora).label("ultima"),
        )
        .where(Movimentacao.produto_id.in_(ids))
        .group_by(Movimentacao.produto_id)
    ).all()
    agregados = {linha.produto_id: (linha.saldo, linha.ultima) for linha in linhas}
    referencias = referencias_em_lote(db, ids)
    resultado: dict[int, Situacao] = {}
    for produto in produtos:
        saldo_atual, ultima = agregados.get(produto.id, (Decimal(0), None))
        referencia = referencias.get(produto.id, Decimal(0))
        limite = calcular_limite(produto.estoque_minimo, produto.percentual_alerta, referencia)
        resultado[produto.id] = Situacao(
            saldo=saldo_atual,
            referencia=referencia,
            limite=limite,
            em_alerta=em_alerta(saldo_atual, limite),
            ultima_movimentacao_em=ultima,
        )
    return resultado


def situacao(db: Session, produto: Produto) -> Situacao:
    return situacoes_em_lote(db, [produto])[produto.id]


def avaliar_alerta(
    db: Session, produto: Produto, estado: Situacao | None = None
) -> tuple[str | None, Alerta | None]:
    estado = estado or situacao(db, produto)
    ativo = db.scalar(
        select(Alerta).where(Alerta.produto_id == produto.id, Alerta.situacao == "ativo")
    )
    if estado.em_alerta:
        if ativo is not None:
            return "mantido", ativo
        alerta = Alerta(
            produto_id=produto.id,
            saldo_no_momento=estado.saldo,
            limite=estado.limite,
            situacao="ativo",
        )
        db.add(alerta)
        return "criado", alerta
    if ativo is not None:
        ativo.situacao = "encerrado"
        ativo.encerrado_em = datetime.now(timezone.utc)
        return "encerrado", ativo
    return None, None


def _variacao_do_ajuste(dados: dict[str, Any], saldo_anterior: Decimal, unidade: str) -> Decimal:
    if dados.get("quantidade_contada") is not None:
        variacao = quantizar(dados["quantidade_contada"]) - saldo_anterior
    else:
        variacao = quantizar(dados["variacao"])
    if variacao == 0:
        raise HTTPException(status_code=422, detail="Nada a ajustar.")
    if saldo_anterior + variacao < 0:
        novo_saldo = formatar_quantidade(saldo_anterior + variacao)
        raise HTTPException(
            status_code=422,
            detail=f"Ajuste inválido: o saldo ficaria negativo ({novo_saldo} {unidade}).",
        )
    return variacao


def _movimento_da_entrada(produto: Produto, dados: dict[str, Any], usuario: Usuario) -> Movimentacao:
    custo = dados.get("custo_unitario")
    if custo is not None:
        custo = Decimal(custo).quantize(CENTAVOS)
        produto.custo_unitario = custo
    return Movimentacao(
        produto_id=produto.id,
        tipo="entrada",
        quantidade=quantizar(dados["quantidade"]),
        custo_unitario=custo,
        fornecedor=dados.get("fornecedor"),
        usuario_id=usuario.id,
    )


def _movimento_da_saida(produto: Produto, dados: dict[str, Any], usuario: Usuario, saldo_anterior: Decimal) -> Movimentacao:
    quantidade = quantizar(dados["quantidade"])
    if quantidade > saldo_anterior:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Saldo insuficiente: disponível {formatar_quantidade(saldo_anterior)} {produto.unidade}, "
                f"saída pedida {formatar_quantidade(quantidade)} {produto.unidade}."
            ),
        )
    motivo = dados["motivo"]
    detalhe = (dados.get("motivo_detalhe") or "").strip()
    if motivo == "outro" and detalhe:
        motivo = f"outro: {detalhe}"
    return Movimentacao(
        produto_id=produto.id,
        tipo="saida",
        quantidade=quantidade,
        motivo=motivo,
        usuario_id=usuario.id,
    )


def _movimento_do_ajuste(
    produto: Produto, dados: dict[str, Any], usuario: Usuario, saldo_anterior: Decimal
) -> Movimentacao:
    variacao = _variacao_do_ajuste(dados, saldo_anterior, produto.unidade)
    return Movimentacao(
        produto_id=produto.id,
        tipo="ajuste",
        quantidade=variacao,
        motivo=dados["justificativa"].strip(),
        usuario_id=usuario.id,
        inventario_inicial=bool(dados.get("inventario_inicial", False)),
    )


def registrar_movimentacao(db: Session, usuario: Usuario, tipo: str, dados: dict[str, Any]) -> dict[str, Any]:
    produto = db.scalar(
        select(Produto).where(Produto.id == dados["produto_id"]).with_for_update()
    )
    if produto is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    if not produto.ativo:
        raise HTTPException(
            status_code=409,
            detail="Produto inativo não recebe movimentações. Reative-o para registrar.",
        )

    saldo_anterior = saldo(db, produto.id)
    if tipo == "entrada":
        movimento = _movimento_da_entrada(produto, dados, usuario)
    elif tipo == "saida":
        movimento = _movimento_da_saida(produto, dados, usuario, saldo_anterior)
    elif tipo == "ajuste":
        movimento = _movimento_do_ajuste(produto, dados, usuario, saldo_anterior)
    else:
        raise ValueError(f"Tipo de movimentação desconhecido: {tipo}")

    movimento.data_hora = datetime.now(timezone.utc)
    db.add(movimento)
    db.flush()
    estado = situacao(db, produto)
    status_alerta, alerta = avaliar_alerta(db, produto, estado)
    db.commit()

    if status_alerta == "criado" and alerta is not None:
        enviado = notificador.enviar_alerta(alerta, produto, estado.saldo, estado.limite, usuario.email)
        if enviado:
            alerta.email_enviado = True
            db.commit()

    return {
        "movimentacao": movimento,
        "saldo_anterior": saldo_anterior,
        "saldo_atual": estado.saldo,
        "limite": estado.limite,
        "alerta": status_alerta,
    }
