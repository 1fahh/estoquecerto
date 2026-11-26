import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Icon } from '../components/Icon';
import { Loading } from '../components/Loading';
import { Toast } from '../components/Toast';
import { formatMoeda, formatNumero, formatPercentual, formatQuantidade } from '../format';
import type { ProdutoOut, RegistroOut } from '../types';
import { ProdutoEscolha } from './registros/ProdutoEscolha';
import { arredondar, lerNumero, mensagemDeFalha, voltarOuIr } from './registros/utilitarios';
import './Entrada.css';

type EntradaHistorico = { itens: { fornecedor: string | null }[]; total: number };

const LIMITE_FORNECEDORES = 5;

function fornecedoresDistintos(nomes: (string | null)[]): string[] {
  const vistos = new Set<string>();
  for (const nome of nomes) {
    const limpo = nome?.trim();
    if (limpo) vistos.add(limpo);
  }
  return [...vistos].slice(0, LIMITE_FORNECEDORES);
}

function limiteAposEntrada(produto: ProdutoOut, quantidade: number): number {
  return Math.max(produto.estoque_minimo ?? 0, (produto.percentual_alerta / 100) * quantidade);
}

export function Entrada() {
  const navigate = useNavigate();
  const local = useLocation();
  const [params] = useSearchParams();
  const produtoUrl = params.get('produto');

  const [produto, setProduto] = useState<ProdutoOut | null>(null);
  const [carregandoProduto, setCarregandoProduto] = useState(false);
  const [erroProduto, setErroProduto] = useState<string | null>(null);
  const [fornecedoresUsados, setFornecedoresUsados] = useState<string[]>([]);
  const [quantidadeTexto, setQuantidadeTexto] = useState('');
  const [custoTexto, setCustoTexto] = useState('');
  const [fornecedor, setFornecedor] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [concluido, setConcluido] = useState<RegistroOut | null>(null);

  const fechar = useCallback(() => voltarOuIr(navigate, local), [navigate, local]);

  useEffect(() => {
    if (!produtoUrl) return;
    let ativo = true;
    setCarregandoProduto(true);
    setErroProduto(null);
    api
      .get<ProdutoOut>(`/produtos/${encodeURIComponent(produtoUrl)}`)
      .then((dados) => {
        if (ativo) setProduto(dados);
      })
      .catch((falha: unknown) => {
        if (ativo) setErroProduto(mensagemDeFalha(falha));
      })
      .finally(() => {
        if (ativo) setCarregandoProduto(false);
      });
    return () => {
      ativo = false;
    };
  }, [produtoUrl]);

  useEffect(() => {
    if (!produto) return;
    let ativo = true;
    api
      .get<EntradaHistorico>(`/movimentacoes?produto_id=${produto.id}&tipo=entrada&limite=100`)
      .then((dados) => {
        if (ativo) setFornecedoresUsados(fornecedoresDistintos(dados.itens.map((item) => item.fornecedor)));
      })
      .catch(() => {
        if (ativo) setFornecedoresUsados([]);
      });
    return () => {
      ativo = false;
    };
  }, [produto]);

  function escolherProduto(escolhido: ProdutoOut) {
    setProduto(escolhido);
    setQuantidadeTexto('');
    setCustoTexto('');
    setFornecedor('');
    setErroEnvio(null);
  }

  const quantidade = lerNumero(quantidadeTexto);
  const quantidadeValida = quantidade !== null && quantidade > 0;
  const custo = lerNumero(custoTexto);
  const custoInvalido = custoTexto.trim() !== '' && custo === null;
  const total = quantidadeValida && custo !== null ? arredondar(quantidade * custo) : null;
  const podeConfirmar = produto !== null && quantidadeValida && !custoInvalido && !enviando;

  const depois = produto !== null && quantidadeValida ? arredondar(produto.saldo + quantidade) : null;
  const novoLimite = produto !== null && quantidadeValida ? limiteAposEntrada(produto, quantidade) : null;
  const alertaSaiSozinho = produto !== null && produto.em_alerta && depois !== null && novoLimite !== null && depois > novoLimite;
  const continuaEmAlerta = produto !== null && produto.em_alerta && depois !== null && novoLimite !== null && depois <= novoLimite;

  async function confirmar() {
    if (!produto || quantidade === null || !podeConfirmar) return;
    setEnviando(true);
    setErroEnvio(null);
    try {
      const registro = await api.post<RegistroOut>('/movimentacoes/entrada', {
        produto_id: produto.id,
        quantidade,
        custo_unitario: custo,
        fornecedor: fornecedor.trim() || null,
      });
      setConcluido(registro);
    } catch (falha) {
      setErroEnvio(mensagemDeFalha(falha));
    } finally {
      setEnviando(false);
    }
  }

  if (concluido) {
    const detalheToast =
      `Saldo agora: ${formatQuantidade(concluido.saldo_atual, concluido.movimentacao.unidade)}` +
      (concluido.alerta === 'encerrado' ? ' · alerta encerrado' : '');
    return (
      <main className="page">
        <Toast mensagem="Entrada registrada" detalhe={detalheToast} onFechar={fechar} duracao={2200} />
      </main>
    );
  }

  return (
    <main className="page entrada">
      <header className="page-header">
        <button type="button" className="botao-icone" onClick={fechar} aria-label="Voltar">
          <Icon name="voltar" />
        </button>
        <div className="entrada-titulo">
          <h1 className="page-title">Chegou mercadoria</h1>
          {produto && <span className="texto-secundario">{produto.nome}</span>}
        </div>
      </header>

      {carregandoProduto && <Loading texto="Carregando produto…" />}

      {!carregandoProduto && erroProduto && <p className="campo-erro" role="alert">{erroProduto}</p>}

      {!carregandoProduto && !produto && <ProdutoEscolha onSelecionar={escolherProduto} />}

      {!carregandoProduto && produto && (
        <div className="entrada-corpo">
          <section className="card entrada-cartao">
            <div className="linha">
              <strong className="entrada-produto">{produto.nome}</strong>
              {produto.em_alerta && <span className="badge-alerta">Em alerta</span>}
            </div>
            <div className="entrada-comparacao">
              <div className="entrada-caixa entrada-antes">
                <span className="entrada-caixa-rotulo">Antes</span>
                <span className="entrada-caixa-valor">{formatQuantidade(produto.saldo, produto.unidade)}</span>
              </div>
              <svg className="entrada-seta" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
              <div className="entrada-caixa entrada-depois">
                <span className="entrada-caixa-rotulo">Depois</span>
                <span className="entrada-caixa-valor">
                  {depois !== null ? formatQuantidade(depois, produto.unidade) : '—'}
                </span>
              </div>
            </div>
            {alertaSaiSozinho && novoLimite !== null && (
              <p className="entrada-aviso">
                O alerta sai sozinho. O novo limite passa a ser <strong>{formatQuantidade(arredondar(novoLimite), produto.unidade)}</strong>{' '}
                ({formatPercentual(produto.percentual_alerta)} de {formatNumero(quantidade ?? 0)}).
              </p>
            )}
            {continuaEmAlerta && (
              <p className="entrada-aviso">Ainda abaixo do limite: o alerta continua ativo.</p>
            )}
          </section>

          <div className="entrada-formulario">
            <section className="entrada-campos">
              <label className="entrada-linha">
                <span className="entrada-numero">1</span>
                <span className="entrada-campo">
                  <span className="entrada-campo-rotulo">Quantidade recebida ({produto.unidade})</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder="Ex.: 30"
                    value={quantidadeTexto}
                    onChange={(evento) => setQuantidadeTexto(evento.target.value)}
                  />
                </span>
              </label>

              <label className="entrada-linha">
                <span className="entrada-numero">2</span>
                <span className="entrada-campo">
                  <span className="entrada-campo-rotulo">Quanto pagou por unidade</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder="R$ 0,00"
                    value={custoTexto}
                    onChange={(evento) => setCustoTexto(evento.target.value)}
                  />
                </span>
                {total !== null && <span className="entrada-total">total {formatMoeda(total)}</span>}
                {custoInvalido && (
                  <span className="campo-erro" role="alert">
                    Custo inválido. Use só números, como 12,50.
                  </span>
                )}
              </label>

              <label className="entrada-linha">
                <span className="entrada-numero">3</span>
                <span className="entrada-campo">
                  <span className="entrada-campo-rotulo">De quem comprou (opcional)</span>
                  <input
                    type="text"
                    placeholder="Nome do fornecedor"
                    maxLength={160}
                    value={fornecedor}
                    onChange={(evento) => setFornecedor(evento.target.value)}
                  />
                </span>
              </label>
            </section>

            {fornecedoresUsados.length > 0 && (
              <div className="entrada-fornecedores">
                <span className="texto-secundario">Usados antes:</span>
                {fornecedoresUsados.map((nome) => (
                  <button key={nome} type="button" aria-pressed={fornecedor === nome} onClick={() => setFornecedor(nome)}>
                    {nome}
                  </button>
                ))}
              </div>
            )}

            {erroEnvio && <p className="campo-erro" role="alert">{erroEnvio}</p>}

            <button type="button" className="btn btn-primario entrada-confirmar" disabled={!podeConfirmar} onClick={confirmar}>
              {enviando ? 'Registrando…' : 'Confirmar entrada'}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
