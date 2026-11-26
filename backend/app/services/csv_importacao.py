import csv
import io
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Categoria, Movimentacao, Produto, Usuario
from app.schemas import LIMITE_CUSTO, LIMITE_QUANTIDADE
from app.services import notificador
from app.services.estoque import CASAS, CENTAVOS, avaliar_alerta, situacoes_em_lote

COLUNAS = (
    "nome",
    "codigo",
    "categoria",
    "unidade",
    "custo_unitario",
    "estoque_minimo",
    "percentual_alerta",
    "localizacao",
    "quantidade_inicial",
)
EXEMPLO = "Filtro de óleo;FO-100;Filtros;un;35,90;2;20;Prateleira A;10"
MOTIVO_INVENTARIO = "Inventário inicial"


class ImportacaoInvalida(Exception):
    pass


class _LinhaInvalida(Exception):
    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


@dataclass(frozen=True)
class _DadosLinha:
    nome: str
    codigo: str | None
    categoria: str | None
    unidade: str
    custo_unitario: Decimal | None
    estoque_minimo: Decimal | None
    percentual_alerta: Decimal
    localizacao: str | None
    quantidade_inicial: Decimal


def modelo_importacao() -> str:
    return "﻿" + ";".join(COLUNAS) + "\r\n" + EXEMPLO + "\r\n"


def _texto(conteudo: bytes) -> str:
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        # No fallback o BOM não é removido pelo cp1252; sem isso ele gruda no nome da primeira coluna.
        return conteudo.removeprefix(b"\xef\xbb\xbf").decode("cp1252", errors="replace")


def _chave_coluna(titulo: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", titulo) if not unicodedata.combining(c))
    return sem_acento.strip().casefold().replace(" ", "_").replace("-", "_")


def _separador(primeira_linha: str) -> str:
    return ";" if primeira_linha.count(";") >= primeira_linha.count(",") else ","


def ler_linhas(conteudo: bytes) -> list[tuple[int, dict[str, str]]]:
    if not conteudo.strip():
        raise ImportacaoInvalida("O arquivo está vazio.")
    texto = _texto(conteudo)
    # newline="" faz o leitor aceitar \r, \n e \r\n (planilhas antigas de Mac usam só \r).
    fluxo = io.StringIO(texto, newline="")
    leitor = csv.reader(fluxo, delimiter=_separador(fluxo.readline()))
    fluxo.seek(0)
    try:
        cabecalho = [_chave_coluna(titulo) for titulo in next(leitor, [])]
        if "nome" not in cabecalho:
            raise ImportacaoInvalida("Cabeçalho inválido: a primeira linha precisa ter a coluna nome.")
        linhas = []
        for valores in leitor:
            if not any(valor.strip() for valor in valores):
                continue
            registro = {
                coluna: (valores[indice].strip() if indice < len(valores) else "")
                for indice, coluna in enumerate(cabecalho)
            }
            linhas.append((leitor.line_num, registro))
    except csv.Error:
        raise ImportacaoInvalida(f"Arquivo com formato inválido a partir da linha {leitor.line_num}.")
    return linhas


def _decimal(valor: str, campo: str, limite: Decimal | None = None) -> Decimal | None:
    if not valor:
        return None
    normalizado = valor.replace(" ", "")
    if "," in normalizado:
        normalizado = normalizado.replace(".", "").replace(",", ".")
    try:
        numero = Decimal(normalizado)
    except InvalidOperation:
        raise _LinhaInvalida(f"{campo} inválido: {valor}.")
    if not numero.is_finite():
        raise _LinhaInvalida(f"{campo} inválido: {valor}.")
    if numero < 0:
        raise _LinhaInvalida(f"{campo} não pode ser negativo: {valor}.")
    if limite is not None and numero > limite:
        raise _LinhaInvalida(f"{campo} acima do limite permitido: {valor}.")
    return numero


def _texto_limitado(valor: str, limite: int, campo: str) -> str | None:
    if not valor:
        return None
    if "\x00" in valor:
        raise _LinhaInvalida(f"{campo} contém caractere inválido.")
    if len(valor) > limite:
        raise _LinhaInvalida(f"{campo} com mais de {limite} caracteres.")
    return valor


def _interpretar(registro: dict[str, str], percentual_padrao: Decimal) -> _DadosLinha:
    nome = _texto_limitado(registro.get("nome", ""), 160, "Nome")
    if nome is None:
        raise _LinhaInvalida("Nome obrigatório.")
    custo = _decimal(registro.get("custo_unitario", ""), "Custo unitário", LIMITE_CUSTO)
    minimo = _decimal(registro.get("estoque_minimo", ""), "Estoque mínimo", LIMITE_QUANTIDADE)
    percentual = _decimal(registro.get("percentual_alerta", ""), "Percentual de alerta")
    if percentual is None:
        percentual = percentual_padrao
    if percentual > 100:
        raise _LinhaInvalida("Percentual de alerta deve estar entre 0 e 100.")
    quantidade = _decimal(registro.get("quantidade_inicial", ""), "Quantidade inicial", LIMITE_QUANTIDADE)
    if quantidade is not None and quantidade != quantidade.quantize(CASAS):
        # Sem isso o banco arredonda em silêncio e o CHECK de movimentação derruba a linha.
        raise _LinhaInvalida("Quantidade inicial deve ter no máximo 3 casas decimais.")
    return _DadosLinha(
        nome=nome,
        codigo=_texto_limitado(registro.get("codigo", ""), 60, "Código"),
        categoria=_texto_limitado(registro.get("categoria", ""), 80, "Categoria"),
        unidade=_texto_limitado(registro.get("unidade", "") or "un", 20, "Unidade") or "un",
        custo_unitario=None if custo is None else custo.quantize(CENTAVOS),
        estoque_minimo=minimo,
        percentual_alerta=percentual,
        localizacao=_texto_limitado(registro.get("localizacao", ""), 120, "Localização"),
        quantidade_inicial=Decimal(0) if quantidade is None else quantidade,
    )


def _categoria(
    db: Session,
    existentes: dict[str, Categoria],
    novas: dict[str, Categoria],
    nome: str | None,
) -> Categoria | None:
    if nome is None:
        return None
    chave = nome.casefold()
    if chave in existentes:
        return existentes[chave]
    if chave in novas:
        return novas[chave]
    categoria = Categoria(nome=nome)
    db.add(categoria)
    db.flush()
    novas[chave] = categoria
    return categoria


def _produto_da_linha(db: Session, dados: _DadosLinha, categoria: Categoria | None, usuario: Usuario) -> Produto:
    produto = Produto(
        nome=dados.nome,
        codigo=dados.codigo,
        categoria_id=categoria.id if categoria is not None else None,
        unidade=dados.unidade,
        custo_unitario=dados.custo_unitario,
        estoque_minimo=dados.estoque_minimo,
        percentual_alerta=dados.percentual_alerta,
        localizacao=dados.localizacao,
    )
    db.add(produto)
    db.flush()
    if dados.quantidade_inicial > 0:
        db.add(
            Movimentacao(
                produto_id=produto.id,
                tipo="ajuste",
                quantidade=dados.quantidade_inicial,
                motivo=MOTIVO_INVENTARIO,
                usuario_id=usuario.id,
                inventario_inicial=True,
            )
        )
        db.flush()
    return produto


def importar_produtos(
    db: Session, usuario: Usuario, conteudo: bytes, percentual_padrao: Decimal
) -> dict[str, Any]:
    linhas = ler_linhas(conteudo)
    categorias = {categoria.nome.casefold(): categoria for categoria in db.scalars(select(Categoria))}
    codigos = set(db.scalars(select(Produto.codigo).where(Produto.codigo.is_not(None))))
    criados: list[Produto] = []
    ignorados: list[dict[str, Any]] = []

    for numero, registro in linhas:
        try:
            dados = _interpretar(registro, percentual_padrao)
            if dados.codigo is not None and dados.codigo in codigos:
                raise _LinhaInvalida(f"Código já cadastrado: {dados.codigo}.")
            novas: dict[str, Categoria] = {}
            with db.begin_nested():
                categoria = _categoria(db, categorias, novas, dados.categoria)
                produto = _produto_da_linha(db, dados, categoria, usuario)
        except _LinhaInvalida as erro:
            ignorados.append({"linha": numero, "motivo": erro.motivo})
            continue
        except IntegrityError:
            ignorados.append({"linha": numero, "motivo": "Não foi possível gravar esta linha: dado não aceito pelo banco."})
            continue
        except DataError:
            ignorados.append({"linha": numero, "motivo": "Não foi possível gravar esta linha: valor fora da faixa permitida."})
            continue
        categorias.update(novas)
        if dados.codigo is not None:
            codigos.add(dados.codigo)
        criados.append(produto)

    estados = situacoes_em_lote(db, criados)
    alertas = []
    for produto in criados:
        status, alerta = avaliar_alerta(db, produto, estados[produto.id])
        if status == "criado" and alerta is not None:
            alertas.append((produto, alerta))
    db.commit()

    for produto, alerta in alertas:
        estado = estados[produto.id]
        if notificador.enviar_alerta(alerta, produto, estado.saldo, estado.limite, usuario.email):
            alerta.email_enviado = True
    if alertas:
        db.commit()

    return {"criados": len(criados), "ignorados": ignorados}
