from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.schemas import PainelOut, ParadosOut
from app.security import get_current_user
from app.services import csv_io, relatorios

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


@router.get("/painel", response_model=PainelOut)
def painel(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> dict:
    return relatorios.painel(db)


@router.get("/parados", response_model=ParadosOut)
def parados(
    dias: int | None = Query(None, ge=1, le=365),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> dict:
    return relatorios.parados(db, dias or relatorios.periodo_parado(db))


@router.get("/exportar/{tipo}.csv")
def exportar_csv(
    tipo: csv_io.TipoExportacao,
    de: date | None = None,
    ate: date | None = None,
    produto_id: int | None = None,
    tipo_mov: relatorios.TipoMovimentacao | None = None,
    dias: int | None = Query(None, ge=1, le=365),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> Response:
    exportacao = csv_io.exportar(
        db,
        tipo,
        de=de,
        ate=ate,
        produto_id=produto_id,
        tipo_mov=tipo_mov,
        dias=dias,
    )
    return Response(
        content=exportacao.conteudo,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{exportacao.nome_arquivo}"'},
    )
