export type Usuario = {
  id: number;
  nome: string;
  email: string;
};

export type LoginResposta = {
  access_token: string;
  token_type: 'bearer';
  usuario: Usuario;
};

export type Categoria = {
  id: number;
  nome: string;
  total_produtos: number;
};

export type Situacao = 'todos' | 'repor' | 'parados';
export type AtivoFiltro = 'true' | 'false' | 'todos';

export type ProdutoOut = {
  id: number;
  nome: string;
  codigo: string | null;
  categoria_id: number | null;
  categoria_nome: string | null;
  unidade: string;
  custo_unitario: number | null;
  estoque_minimo: number | null;
  percentual_alerta: number;
  localizacao: string | null;
  observacoes: string | null;
  ativo: boolean;
  saldo: number;
  limite: number;
  em_alerta: boolean;
  quantidade_referencia: number;
  ultima_movimentacao_em: string | null;
  valor_estoque: number | null;
};

export type ProdutoIn = {
  nome: string;
  codigo?: string | null;
  categoria_id?: number | null;
  unidade: string;
  custo_unitario?: number | null;
  estoque_minimo?: number | null;
  percentual_alerta?: number;
  localizacao?: string | null;
  observacoes?: string | null;
  quantidade_inicial?: number;
};

export type TipoMovimentacao = 'entrada' | 'saida' | 'ajuste';
export type MotivoSaida = 'consumo' | 'perda' | 'outro';

export type EntradaIn = {
  produto_id: number;
  quantidade: number;
  custo_unitario?: number | null;
  fornecedor?: string | null;
};

export type SaidaIn = {
  produto_id: number;
  quantidade: number;
  motivo: MotivoSaida;
  motivo_detalhe?: string | null;
};

export type AjusteIn = {
  produto_id: number;
  quantidade_contada?: number;
  variacao?: number;
  justificativa: string;
};

export type AlertaRegistro = 'criado' | 'encerrado' | 'mantido' | null;

export type MovimentacaoOut = {
  id: number;
  produto_id: number;
  produto_nome: string;
  unidade: string;
  tipo: TipoMovimentacao;
  quantidade: number;
  data_hora: string;
  motivo: string | null;
  custo_unitario: number | null;
  fornecedor: string | null;
  usuario_nome: string;
  saldo_apos: number;
};

export type MovimentacaoLista = {
  itens: MovimentacaoOut[];
  total: number;
};

export type RegistroOut = {
  movimentacao: MovimentacaoOut;
  saldo_anterior: number;
  saldo_atual: number;
  limite: number;
  alerta: AlertaRegistro;
};

export type UltimaEntradaOut = {
  quantidade: number;
  custo_unitario: number | null;
  fornecedor: string | null;
  data_hora: string;
};

export type AlertaSituacao = 'ativo' | 'encerrado' | 'todos';

export type AlertaOut = {
  id: number;
  produto_id: number;
  produto_nome: string;
  unidade: string;
  saldo_no_momento: number;
  saldo_atual: number;
  limite: number;
  criado_em: string;
  encerrado_em: string | null;
  situacao: 'ativo' | 'encerrado';
};

export type PainelAlerta = {
  id: number;
  produto_id: number;
  produto_nome: string;
  unidade: string;
  saldo_atual: number;
  limite: number;
};

export type PainelOut = {
  data: string;
  produtos_ativos: number;
  alertas_ativos: PainelAlerta[];
  total_alertas: number;
  parados_qtd: number;
  parados_valor: number;
  registros_hoje: number;
};

export type ParadoItem = {
  produto_id: number;
  nome: string;
  unidade: string;
  saldo: number;
  custo_unitario: number | null;
  valor: number | null;
  dias_parado: number;
  ultima_saida_em: string | null;
};

export type ParadosOut = {
  dias: number;
  itens: ParadoItem[];
  total_valor: number;
  sem_custo_qtd: number;
};

export type MaisUsado = {
  produto_id: number;
  nome: string;
  unidade: string;
  saidas_30d: number;
};

export type ImportacaoIgnorado = {
  linha: number;
  motivo: string;
};

export type ImportacaoOut = {
  criados: number;
  ignorados: ImportacaoIgnorado[];
};

export type ConfiguracoesOut = {
  periodo_parado_dias: number;
  percentual_alerta_padrao: number;
};

export type ConfiguracoesIn = ConfiguracoesOut;

export type HealthOut = {
  status: 'ok';
  banco: 'ok';
};

export type TrocarSenhaIn = {
  senha_atual: string;
  nova_senha: string;
};
