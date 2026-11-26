import unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alerta, Categoria, Movimentacao, Produto, Usuario
from app.routers.configuracoes import obter_configuracao
from app.schemas import AtivoIn, ImportacaoOut, ProdutoEdicaoIn, ProdutoIn, ProdutoOut
from app.security import get_current_user
from app.services import csv_importacao, estoque, notificador
from app.services.estoque import CENTAVOS, Situacao

router = APIRouter()
LIMITE_IMPORTACAO_BYTES = 2 * 1024 * 1024


def _normalizar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(caractere for caractere in decomposto if not unicodedata.combining(caractere)).casefold()


def _consulta_produtos():
    return select(Produto, Categoria.nome).outerjoin(Categoria, Categoria.id == Produto.categoria_id)


def _carregar(db: Session, produto_id: int) -> tuple[Produto, str | None]:
    linha = db.execute(_consulta_produtos().where(Produto.id == produto_id)).first()
    if linha is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return linha[0], linha[1]


def _centavos(valor: Decimal | None) -> Decimal | None:
    return None if valor is None else valor.quantize(CENTAVOS)


def _produto_out(produto: Produto, categoria_nome: str | None, estado: Situacao) -> ProdutoOut:
    valor = None if produto.custo_unitario is None else (estado.saldo * produto.custo_unitario).quantize(CENTAVOS)
    return ProdutoOut(
        id=produto.id,
        nome=produto.nome,
        codigo=produto.codigo,
        categoria_id=produto.categoria_id,
        categoria_nome=categoria_nome,
        unidade=produto.unidade,
        custo_unitario=produto.custo_unitario,
        estoque_minimo=produto.estoque_minimo,
        percentual_alerta=produto.percentual_alerta,
        localizacao=produto.localizacao,
        observacoes=produto.observacoes,
        ativo=produto.ativo,
        saldo=estado.saldo,
        limite=estado.limite,
        em_alerta=estado.em_alerta,
        quantidade_referencia=estado.referencia,
        ultima_movimentacao_em=estado.ultima_movimentacao_em,
        valor_estoque=valor,
    )


def _resposta(db: Session, produto_id: int) -> ProdutoOut:
    produto, categoria_nome = _carregar(db, produto_id)
    return _produto_out(produto, categoria_nome, estoque.situacao(db, produto))


def _ids_parados(db: Session, estados: dict[int, Situacao], dias: int) -> set[int]:
    candidatos = [produto_id for produto_id, estado in estados.items() if estado.saldo > 0]
    if not candidatos:
        return set()
    linhas = db.execute(
        select(
            Movimentacao.produto_id,
            func.max(case((Movimentacao.tipo == "saida", Movimentacao.data_hora))).label("ultima_saida"),
            func.min(Movimentacao.data_hora).label("primeira"),
        )
        .where(Movimentacao.produto_id.in_(candidatos))
        .group_by(Movimentacao.produto_id)
    ).all()
    agora = datetime.now(timezone.utc)
    return {
        linha.produto_id
        for linha in linhas
        if (agora - (linha.ultima_saida or linha.primeira)).days >= dias
    }


def _campos(db: Session, dados: ProdutoEdicaoIn, atual: Produto | None = None) -> dict:
    if dados.categoria_id is not None and db.get(Categoria, dados.categoria_id) is None:
        raise HTTPException(status_code=422, detail="Categoria não encontrada.")
    if dados.codigo is not None:
        consulta = select(Produto.id).where(Produto.codigo == dados.codigo)
        if atual is not None:
            consulta = consulta.where(Produto.id != atual.id)
        if db.scalar(consulta) is not None:
            raise HTTPException(status_code=409, detail="Já existe um produto com este código.")
    if "percentual_alerta" in dados.model_fields_set:
        percentual = _centavos(dados.percentual_alerta)
    elif atual is not None:
        percentual = atual.percentual_alerta
    else:
        percentual = obter_configuracao(db).percentual_alerta_padrao
    return {
        "nome": dados.nome,
        "codigo": dados.codigo,
        "categoria_id": dados.categoria_id,
        "unidade": dados.unidade,
        "custo_unitario": _centavos(dados.custo_unitario),
        "estoque_minimo": dados.estoque_minimo,
        "percentual_alerta": percentual,
        "localizacao": dados.localizacao,
        "observacoes": dados.observacoes,
    }


def _reavaliar_alerta(db: Session, produto: Produto, usuario: Usuario) -> None:
    estado = estoque.situacao(db, produto)
    status, alerta = estoque.avaliar_alerta(db, produto, estado)
    db.commit()
    if status == "criado" and alerta is not None:
        if notificador.enviar_alerta(alerta, produto, estado.saldo, estado.limite, usuario.email):
            alerta.email_enviado = True
            db.commit()


@router.get("/produtos/modelo-importacao.csv")
def modelo_importacao(_usuario: Usuario = Depends(get_current_user)) -> Response:
    return Response(
        content=csv_importacao.modelo_importacao().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="modelo-importacao-produtos.csv"'},
    )


@router.post("/produtos/importar", response_model=ImportacaoOut)
def importar_produtos(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
) -> dict:
    conteudo = arquivo.file.read(LIMITE_IMPORTACAO_BYTES + 1)
    if len(conteudo) > LIMITE_IMPORTACAO_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo muito grande (limite de 2 MB).")
    percentual_padrao = obter_configuracao(db).percentual_alerta_padrao
    try:
        return csv_importacao.importar_produtos(db, usuario, conteudo, percentual_padrao)
    except csv_importacao.ImportacaoInvalida as erro:
        raise HTTPException(status_code=422, detail=str(erro))


@router.get("/produtos", response_model=list[ProdutoOut])
def listar_produtos(
    busca: str | None = None,
    categoria_id: int | None = None,
    situacao: Literal["todos", "repor", "parados"] = "todos",
    ativo: Literal["true", "false", "todos"] = "true",
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
) -> list[ProdutoOut]:
    consulta = _consulta_produtos()
    if ativo != "todos":
        consulta = consulta.where(Produto.ativo.is_(ativo == "true"))
    if categoria_id is not None:
        consulta = consulta.where(Produto.categoria_id == categoria_id)
    linhas = db.execute(consulta).all()

    if busca is not None and busca.strip():
        termo = _normalizar(busca.strip())
        linhas = [
            (produto, nome)
            for produto, nome in linhas
            if termo in _normalizar(produto.nome) or (produto.codigo and termo in _normalizar(produto.codigo))
        ]

    estados = estoque.situacoes_em_lote(db, [produto for produto, _ in linhas])
    if situacao == "repor":
        linhas = [(produto, nome) for produto, nome in linhas if estados[produto.id].em_alerta]
    elif situacao == "parados":
        paradas = _ids_parados(db, estados, obter_configuracao(db).periodo_parado_dias)
        linhas = [(produto, nome) for produto, nome in linhas if produto.id in paradas]

    linhas.sort(key=lambda linha: _normalizar(linha[0].nome))
    return [_produto_out(produto, nome, estados[produto.id]) for produto, nome in linhas]


@router.get("/produtos/{produto_id}", response_model=ProdutoOut)
def obter_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
) -> ProdutoOut:
    return _resposta(db, produto_id)


@router.post("/produtos", status_code=201, response_model=ProdutoOut)
def criar_produto(
    dados: ProdutoIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
) -> ProdutoOut:
    produto = Produto(**_campos(db, dados))
    db.add(produto)
    try:
        db.flush()
    except IntegrityError:
        # Duas requisições com o mesmo código: a checagem por SELECT pode ter passado nas duas.
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um produto com este código.")
    if dados.quantidade_inicial:
        estoque.registrar_movimentacao(
            db,
            usuario,
            "ajuste",
            {
                "produto_id": produto.id,
                "variacao": dados.quantidade_inicial,
                "justificativa": "Inventário inicial",
                "inventario_inicial": True,
            },
        )
    else:
        _reavaliar_alerta(db, produto, usuario)
    return _resposta(db, produto.id)


@router.put("/produtos/{produto_id}", response_model=ProdutoOut)
def atualizar_produto(
    produto_id: int,
    dados: ProdutoEdicaoIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
) -> ProdutoOut:
    produto, _ = _carregar(db, produto_id)
    for campo, valor in _campos(db, dados, produto).items():
        setattr(produto, campo, valor)
    produto.atualizado_em = datetime.now(timezone.utc)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um produto com este código.")
    _reavaliar_alerta(db, produto, usuario)
    return _resposta(db, produto_id)


@router.patch("/produtos/{produto_id}/ativo", response_model=ProdutoOut)
def alterar_ativo(
    produto_id: int,
    dados: AtivoIn,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
) -> ProdutoOut:
    produto, _ = _carregar(db, produto_id)
    produto.ativo = dados.ativo
    produto.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    return _resposta(db, produto_id)


@router.delete("/produtos/{produto_id}", status_code=204)
def excluir_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
) -> Response:
    produto, _ = _carregar(db, produto_id)
    possui_movimentacao = db.scalar(
        select(Movimentacao.id).where(Movimentacao.produto_id == produto_id).limit(1)
    )
    if possui_movimentacao is not None:
        raise HTTPException(
            status_code=409,
            detail="Produto com movimentações não pode ser excluído; inative-o.",
        )
    db.execute(delete(Alerta).where(Alerta.produto_id == produto_id))
    db.delete(produto)
    db.commit()
    return Response(status_code=204)
