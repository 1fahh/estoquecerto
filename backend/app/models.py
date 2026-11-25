from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    token_versao: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Categoria(Base):
    __tablename__ = "categorias"
    __table_args__ = (Index("ux_categorias_nome_lower", text("lower(nome)"), unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))

    produtos: Mapped[list["Produto"]] = relationship(back_populates="categoria")


class Produto(Base):
    __tablename__ = "produtos"
    __table_args__ = (
        Index("ux_produtos_codigo", "codigo", unique=True, postgresql_where=text("codigo IS NOT NULL")),
        CheckConstraint("percentual_alerta >= 0 AND percentual_alerta <= 100", name="ck_produtos_percentual_alerta"),
        CheckConstraint("estoque_minimo IS NULL OR estoque_minimo >= 0", name="ck_produtos_estoque_minimo"),
        CheckConstraint("custo_unitario IS NULL OR custo_unitario >= 0", name="ck_produtos_custo_unitario"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(160))
    codigo: Mapped[str | None] = mapped_column(String(60))
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id"))
    unidade: Mapped[str] = mapped_column(String(20), server_default=text("'un'"))
    custo_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estoque_minimo: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    percentual_alerta: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=text("20"))
    localizacao: Mapped[str | None] = mapped_column(String(120))
    observacoes: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    categoria: Mapped[Categoria | None] = relationship(back_populates="produtos")
    movimentacoes: Mapped[list["Movimentacao"]] = relationship(back_populates="produto")
    alertas: Mapped[list["Alerta"]] = relationship(back_populates="produto")


class Movimentacao(Base):
    __tablename__ = "movimentacoes"
    __table_args__ = (
        CheckConstraint("tipo IN ('entrada', 'saida', 'ajuste')", name="ck_movimentacoes_tipo"),
        CheckConstraint(
            "(tipo IN ('entrada', 'saida') AND quantidade > 0) OR (tipo = 'ajuste' AND quantidade <> 0)",
            name="ck_movimentacoes_quantidade",
        ),
        Index("ix_movimentacoes_produto_data", "produto_id", text("data_hora DESC")),
        Index("ix_movimentacoes_tipo_data", "tipo", text("data_hora DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))
    tipo: Mapped[str] = mapped_column(String(10))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    motivo: Mapped[str | None] = mapped_column(Text)
    custo_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fornecedor: Mapped[str | None] = mapped_column(String(160))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    inventario_inicial: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    produto: Mapped[Produto] = relationship(back_populates="movimentacoes")
    usuario: Mapped[Usuario] = relationship()


class Alerta(Base):
    __tablename__ = "alertas"
    __table_args__ = (
        CheckConstraint("situacao IN ('ativo', 'encerrado')", name="ck_alertas_situacao"),
        Index(
            "ux_alertas_ativo_por_produto",
            "produto_id",
            unique=True,
            postgresql_where=text("situacao = 'ativo'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))
    saldo_no_momento: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    limite: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    encerrado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    situacao: Mapped[str] = mapped_column(String(10), server_default=text("'ativo'"))
    email_enviado: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    produto: Mapped[Produto] = relationship(back_populates="alertas")


class Configuracao(Base):
    __tablename__ = "configuracoes"
    __table_args__ = (CheckConstraint("id = 1", name="ck_configuracoes_linha_unica"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    periodo_parado_dias: Mapped[int] = mapped_column(Integer, server_default=text("30"))
    percentual_alerta_padrao: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=text("20"))
