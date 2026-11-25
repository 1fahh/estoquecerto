"""Esquema inicial do EstoqueCerto

Revision ID: 0001
Revises:
Create Date: 2026-11-25

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
    )

    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(80), nullable=False),
    )
    op.create_index("ux_categorias_nome_lower", "categorias", [sa.text("lower(nome)")], unique=True)

    op.create_table(
        "produtos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(160), nullable=False),
        sa.Column("codigo", sa.String(60), nullable=True),
        sa.Column("categoria_id", sa.Integer(), sa.ForeignKey("categorias.id"), nullable=True),
        sa.Column("unidade", sa.String(20), nullable=False, server_default=sa.text("'un'")),
        sa.Column("custo_unitario", sa.Numeric(12, 2), nullable=True),
        sa.Column("estoque_minimo", sa.Numeric(12, 3), nullable=True),
        sa.Column("percentual_alerta", sa.Numeric(5, 2), nullable=False, server_default=sa.text("20")),
        sa.Column("localizacao", sa.String(120), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "percentual_alerta >= 0 AND percentual_alerta <= 100", name="ck_produtos_percentual_alerta"
        ),
        sa.CheckConstraint("estoque_minimo IS NULL OR estoque_minimo >= 0", name="ck_produtos_estoque_minimo"),
        sa.CheckConstraint("custo_unitario IS NULL OR custo_unitario >= 0", name="ck_produtos_custo_unitario"),
    )
    op.create_index(
        "ux_produtos_codigo",
        "produtos",
        ["codigo"],
        unique=True,
        postgresql_where=sa.text("codigo IS NOT NULL"),
    )

    op.create_table(
        "movimentacoes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("data_hora", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("custo_unitario", sa.Numeric(12, 2), nullable=True),
        sa.Column("fornecedor", sa.String(160), nullable=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("inventario_inicial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("tipo IN ('entrada', 'saida', 'ajuste')", name="ck_movimentacoes_tipo"),
        sa.CheckConstraint(
            "(tipo IN ('entrada', 'saida') AND quantidade > 0) OR (tipo = 'ajuste' AND quantidade <> 0)",
            name="ck_movimentacoes_quantidade",
        ),
    )
    op.create_index(
        "ix_movimentacoes_produto_data", "movimentacoes", ["produto_id", sa.text("data_hora DESC")]
    )
    op.create_index("ix_movimentacoes_tipo_data", "movimentacoes", ["tipo", sa.text("data_hora DESC")])
    op.execute(
        """
        CREATE FUNCTION impedir_alteracao_movimentacoes() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Movimentações não podem ser editadas nem excluídas (RN03). Use um ajuste de estoque.';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_movimentacoes_imutaveis
        BEFORE UPDATE OR DELETE ON movimentacoes
        FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_movimentacoes()
        """
    )

    op.create_table(
        "alertas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("saldo_no_momento", sa.Numeric(12, 3), nullable=False),
        sa.Column("limite", sa.Numeric(12, 3), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("encerrado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("situacao", sa.String(10), nullable=False, server_default=sa.text("'ativo'")),
        sa.Column("email_enviado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("situacao IN ('ativo', 'encerrado')", name="ck_alertas_situacao"),
    )
    op.create_index(
        "ux_alertas_ativo_por_produto",
        "alertas",
        ["produto_id"],
        unique=True,
        postgresql_where=sa.text("situacao = 'ativo'"),
    )

    op.create_table(
        "configuracoes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("periodo_parado_dias", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("percentual_alerta_padrao", sa.Numeric(5, 2), nullable=False, server_default=sa.text("20")),
        sa.CheckConstraint("id = 1", name="ck_configuracoes_linha_unica"),
    )
    op.execute("INSERT INTO configuracoes (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("configuracoes")
    op.drop_index("ux_alertas_ativo_por_produto", table_name="alertas")
    op.drop_table("alertas")
    op.execute("DROP TRIGGER IF EXISTS trg_movimentacoes_imutaveis ON movimentacoes")
    op.execute("DROP FUNCTION IF EXISTS impedir_alteracao_movimentacoes()")
    op.drop_index("ix_movimentacoes_tipo_data", table_name="movimentacoes")
    op.drop_index("ix_movimentacoes_produto_data", table_name="movimentacoes")
    op.drop_table("movimentacoes")
    op.drop_index("ux_produtos_codigo", table_name="produtos")
    op.drop_table("produtos")
    op.drop_index("ux_categorias_nome_lower", table_name="categorias")
    op.drop_table("categorias")
    op.drop_table("usuarios")
