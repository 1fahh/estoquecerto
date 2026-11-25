import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.services import estoque, relatorios

TipoExportacao = Literal["estoque", "movimentacoes", "parados", "reposicao", "quinzena"]

SEPARADOR = ";"
BOM_UTF8 = "﻿"
FIM_DE_LINHA = "\r\n"
ROTULO_TIPO = {"entrada": "Entrada", "saida": "Saída", "ajuste": "Ajuste"}

CABECALHO_ESTOQUE = [
    "Produto",
    "Código",
    "Categoria",
    "Unidade",
    "Saldo",
    "Limite de reposição",
    "Situação",
    "Custo unitário",
    "Valor em estoque",
    "Última movimentação",
]
CABECALHO_MOVIMENTACOES = [
    "Data e hora",
    "Produto",
    "Unidade",
    "Tipo",
    "Quantidade",
    "Motivo",
    "Custo unitário",
    "Fornecedor",
    "Usuário",
    "Saldo após",
]
CABECALHO_PARADOS = [
    "Produto",
    "Unidade",
    "Saldo",
    "Custo unitário",
    "Valor imobilizado",
    "Dias parado",
    "Última saída",
]
CABECALHO_REPOSICAO = ["Produto", "Unidade", "Saldo atual", "Limite de reposição", "Alerta desde"]

Linha = list[str]
Secao = tuple[list[Linha], list[Linha]]


@dataclass(frozen=True)
class Exportacao:
    conteudo: bytes
    nome_arquivo: str


INICIOS_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def texto(valor: str | None) -> str:
    """Texto digitado pela usuária; neutraliza fórmulas de planilha (CSV injection)."""
    valor = valor or ""
    return "'" + valor if valor.startswith(INICIOS_DE_FORMULA) else valor


def formatar_data(valor: datetime | None) -> str:
    if valor is None:
        return ""
    return valor.astimezone(relatorios.FUSO_NEGOCIO).strftime("%d/%m/%Y %H:%M")


def formatar_quantidade(valor: Decimal | None) -> str:
    if valor is None:
        return ""
    return estoque.formatar_quantidade(Decimal(valor))


def formatar_dinheiro(valor: Decimal | None) -> str:
    if valor is None:
        return ""
    return str(Decimal(valor).quantize(relatorios.CENTAVOS)).replace(".", ",")


def _escrever(cabecalho: list[str], linhas: list[Linha]) -> str:
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=SEPARADOR, lineterminator=FIM_DE_LINHA)
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    return buffer.getvalue()


def montar_csv(secoes: list[Secao]) -> bytes:
    partes = [_escrever(cabecalho, linhas) for cabecalho, linhas in secoes]
    return (BOM_UTF8 + FIM_DE_LINHA.join(partes)).encode("utf-8")


def _linhas_estoque(db: Session) -> list[Linha]:
    return [
        [
            texto(item["nome"]),
            texto(item["codigo"]),
            texto(item["categoria_nome"]),
            texto(item["unidade"]),
            formatar_quantidade(item["saldo"]),
            formatar_quantidade(item["limite"]),
            "Repor" if item["em_alerta"] else "OK",
            formatar_dinheiro(item["custo_unitario"]),
            formatar_dinheiro(item["valor_estoque"]),
            formatar_data(item["ultima_movimentacao_em"]),
        ]
        for item in relatorios.estoque_atual(db)
    ]


def _linhas_movimentacoes(db: Session, **filtros: Any) -> list[Linha]:
    return [
        [
            formatar_data(linha.data_hora),
            texto(linha.produto_nome),
            texto(linha.unidade),
            ROTULO_TIPO[linha.tipo],
            formatar_quantidade(linha.quantidade),
            texto(linha.motivo),
            formatar_dinheiro(linha.custo_unitario),
            texto(linha.fornecedor),
            texto(linha.usuario_nome),
            formatar_quantidade(linha.saldo_apos),
        ]
        for linha in relatorios.movimentacoes(db, **filtros)
    ]


def _linhas_parados(db: Session, dias: int) -> list[Linha]:
    relatorio = relatorios.parados(db, dias)
    linhas = [
        [
            texto(item["nome"]),
            texto(item["unidade"]),
            formatar_quantidade(item["saldo"]),
            formatar_dinheiro(item["custo_unitario"]),
            formatar_dinheiro(item["valor"]),
            str(item["dias_parado"]),
            formatar_data(item["ultima_saida_em"]),
        ]
        for item in relatorio["itens"]
    ]
    linhas.append(["Total imobilizado", "", "", "", formatar_dinheiro(relatorio["total_valor"]), "", ""])
    return linhas


def _linhas_reposicao(db: Session) -> list[Linha]:
    return [
        [
            texto(alerta["produto_nome"]),
            texto(alerta["unidade"]),
            formatar_quantidade(alerta["saldo_atual"]),
            formatar_quantidade(alerta["limite"]),
            formatar_data(alerta["criado_em"]),
        ]
        for alerta in relatorios.alertas_ativos(db)
    ]


def exportar(
    db: Session,
    tipo: TipoExportacao,
    *,
    de: date | None = None,
    ate: date | None = None,
    produto_id: int | None = None,
    tipo_mov: str | None = None,
    dias: int | None = None,
) -> Exportacao:
    dia = relatorios.hoje()
    nome = f"estoquecerto-{tipo}-{dia.isoformat()}.csv"
    if tipo == "estoque":
        secoes = [(CABECALHO_ESTOQUE, _linhas_estoque(db))]
    elif tipo == "movimentacoes":
        secoes = [
            (
                CABECALHO_MOVIMENTACOES,
                _linhas_movimentacoes(db, produto_id=produto_id, tipo=tipo_mov, de=de, ate=ate),
            )
        ]
    elif tipo == "parados":
        secoes = [(CABECALHO_PARADOS, _linhas_parados(db, dias or relatorios.periodo_parado(db)))]
    elif tipo == "reposicao":
        secoes = [(CABECALHO_REPOSICAO, _linhas_reposicao(db))]
    else:
        inicio = dia - timedelta(days=relatorios.DIAS_QUINZENA - 1)
        secoes = [
            (CABECALHO_ESTOQUE, _linhas_estoque(db)),
            (
                CABECALHO_MOVIMENTACOES,
                _linhas_movimentacoes(db, de=inicio, ate=dia),
            ),
        ]
    return Exportacao(conteudo=montar_csv(secoes), nome_arquivo=nome)
