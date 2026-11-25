from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator


def _como_numero(valor: Decimal) -> float:
    return float(valor)


Numero = Annotated[Decimal, PlainSerializer(_como_numero, return_type=float, when_used="json")]


class _Saida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProdutoEdicaoIn(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    codigo: str | None = Field(default=None, max_length=60)
    categoria_id: int | None = None
    unidade: str = Field(default="un", min_length=1, max_length=20)
    custo_unitario: Numero | None = Field(default=None, ge=0)
    estoque_minimo: Numero | None = Field(default=None, ge=0)
    percentual_alerta: Numero = Field(default=Decimal(20), ge=0, le=100)
    localizacao: str | None = Field(default=None, max_length=120)
    observacoes: str | None = None

    @field_validator("nome")
    @classmethod
    def nome_sem_espacos(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Informe o nome do produto.")
        return valor

    @field_validator("codigo", "localizacao", "observacoes")
    @classmethod
    def texto_vazio_vira_nulo(cls, valor: str | None) -> str | None:
        if valor is None or not valor.strip():
            return None
        return valor.strip()


class ProdutoIn(ProdutoEdicaoIn):
    quantidade_inicial: Numero | None = Field(default=None, ge=0)


class ProdutoOut(_Saida):
    id: int
    nome: str
    codigo: str | None
    categoria_id: int | None
    categoria_nome: str | None
    unidade: str
    custo_unitario: Numero | None
    estoque_minimo: Numero | None
    percentual_alerta: Numero
    localizacao: str | None
    observacoes: str | None
    ativo: bool
    saldo: Numero
    limite: Numero
    em_alerta: bool
    quantidade_referencia: Numero
    ultima_movimentacao_em: datetime | None
    valor_estoque: Numero | None


class AtivoIn(BaseModel):
    ativo: bool


class EntradaIn(BaseModel):
    produto_id: int
    quantidade: Numero = Field(gt=0)
    custo_unitario: Numero | None = Field(default=None, ge=0)
    fornecedor: str | None = Field(default=None, max_length=160)


class SaidaIn(BaseModel):
    produto_id: int
    quantidade: Numero = Field(gt=0)
    motivo: Literal["consumo", "perda", "outro"]
    motivo_detalhe: str | None = Field(default=None, max_length=200)


class AjusteIn(BaseModel):
    produto_id: int
    quantidade_contada: Numero | None = Field(default=None, ge=0)
    variacao: Numero | None = None
    justificativa: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def exige_uma_forma_de_ajuste(self) -> "AjusteIn":
        if (self.quantidade_contada is None) == (self.variacao is None):
            raise ValueError("Informe a quantidade contada ou a variação, e não as duas.")
        return self


class MovOut(_Saida):
    id: int
    produto_id: int
    produto_nome: str
    unidade: str
    tipo: str
    quantidade: Numero
    data_hora: datetime
    motivo: str | None
    custo_unitario: Numero | None
    fornecedor: str | None
    usuario_nome: str
    saldo_apos: Numero


class MovLista(BaseModel):
    itens: list[MovOut]
    total: int


class RegistroOut(BaseModel):
    movimentacao: MovOut
    saldo_anterior: Numero
    saldo_atual: Numero
    limite: Numero
    alerta: Literal["criado", "encerrado", "mantido"] | None


class UltimaEntradaOut(_Saida):
    quantidade: Numero
    custo_unitario: Numero | None
    fornecedor: str | None
    data_hora: datetime


class AlertaOut(_Saida):
    id: int
    produto_id: int
    produto_nome: str
    unidade: str
    saldo_no_momento: Numero
    saldo_atual: Numero
    limite: Numero
    criado_em: datetime
    encerrado_em: datetime | None
    situacao: Literal["ativo", "encerrado"]


class PainelOut(BaseModel):
    data: date
    produtos_ativos: int
    alertas_ativos: list[AlertaOut] = Field(max_length=5)
    total_alertas: int
    parados_qtd: int
    parados_valor: Numero
    registros_hoje: int


class ParadoItemOut(BaseModel):
    produto_id: int
    nome: str
    unidade: str
    saldo: Numero
    custo_unitario: Numero | None
    valor: Numero | None
    dias_parado: int
    ultima_saida_em: datetime | None


class ParadosOut(BaseModel):
    dias: int
    itens: list[ParadoItemOut]
    total_valor: Numero
    sem_custo_qtd: int


class CategoriaIn(BaseModel):
    nome: str = Field(min_length=1, max_length=80)

    @field_validator("nome")
    @classmethod
    def nome_sem_espacos(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Informe o nome da categoria.")
        return valor


class CategoriaOut(_Saida):
    id: int
    nome: str
    total_produtos: int


class ConfigIn(BaseModel):
    periodo_parado_dias: int = Field(ge=1, le=365)
    percentual_alerta_padrao: Numero = Field(ge=0, le=100)


class ConfigOut(ConfigIn):
    model_config = ConfigDict(from_attributes=True)


class UsuarioOut(_Saida):
    id: int
    nome: str
    email: str


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    senha: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    usuario: UsuarioOut


class TrocarSenhaIn(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=200)
    nova_senha: str = Field(min_length=8, max_length=200)


class ImportacaoErroOut(BaseModel):
    linha: int
    motivo: str


class ImportacaoOut(BaseModel):
    criados: int
    ignorados: list[ImportacaoErroOut]
