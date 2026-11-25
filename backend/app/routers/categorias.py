from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Categoria, Produto, Usuario
from app.schemas import CategoriaIn, CategoriaOut
from app.security import get_current_user

router = APIRouter()


def _total_produtos(db: Session, categoria_id: int) -> int:
    return db.scalar(select(func.count(Produto.id)).where(Produto.categoria_id == categoria_id)) or 0


def _saida(categoria: Categoria, total_produtos: int) -> CategoriaOut:
    return CategoriaOut(id=categoria.id, nome=categoria.nome, total_produtos=total_produtos)


def _garantir_nome_livre(db: Session, nome: str, ignorar_id: int | None = None) -> None:
    consulta = select(Categoria.id).where(func.lower(Categoria.nome) == func.lower(nome))
    if ignorar_id is not None:
        consulta = consulta.where(Categoria.id != ignorar_id)
    if db.scalar(consulta) is not None:
        raise HTTPException(status_code=409, detail="Já existe uma categoria com este nome.")


def _obter(db: Session, categoria_id: int) -> Categoria:
    categoria = db.get(Categoria, categoria_id)
    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    return categoria


@router.get("/categorias", response_model=list[CategoriaOut])
def listar(db: Session = Depends(get_db), _usuario: Usuario = Depends(get_current_user)) -> list[CategoriaOut]:
    linhas = db.execute(
        select(Categoria, func.count(Produto.id))
        .outerjoin(Produto, Produto.categoria_id == Categoria.id)
        .group_by(Categoria.id)
        .order_by(func.lower(Categoria.nome))
    ).all()
    return [_saida(categoria, total) for categoria, total in linhas]


@router.post("/categorias", status_code=201, response_model=CategoriaOut)
def criar(
    dados: CategoriaIn,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
) -> CategoriaOut:
    _garantir_nome_livre(db, dados.nome)
    categoria = Categoria(nome=dados.nome)
    db.add(categoria)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma categoria com este nome.")
    db.refresh(categoria)
    return _saida(categoria, 0)


@router.put("/categorias/{categoria_id}", response_model=CategoriaOut)
def atualizar(
    categoria_id: int,
    dados: CategoriaIn,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
) -> CategoriaOut:
    categoria = _obter(db, categoria_id)
    _garantir_nome_livre(db, dados.nome, ignorar_id=categoria_id)
    categoria.nome = dados.nome
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma categoria com este nome.")
    db.refresh(categoria)
    return _saida(categoria, _total_produtos(db, categoria_id))
