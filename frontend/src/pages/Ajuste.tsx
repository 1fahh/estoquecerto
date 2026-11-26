import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Icon } from '../components/Icon';
import { Loading } from '../components/Loading';
import { Toast } from '../components/Toast';
import { formatNumero, formatQuantidade } from '../format';
import type { ProdutoOut, RegistroOut } from '../types';
import { ProdutoEscolha } from './registros/ProdutoEscolha';
import { arredondar, mensagemDeFalha, voltarOuIr } from './registros/utilitarios';
import './Ajuste.css';

const MOTIVOS = [
  { valor: 'uso-sem-registro', rotulo: 'Usei e esqueci de registrar' },
  { valor: 'defeito-ou-perda', rotulo: 'Peça com defeito ou perdida' },
  { valor: 'registro-errado', rotulo: 'Registrei errado antes' },
] as const;

type MotivoAjuste = (typeof MOTIVOS)[number]['valor'];

export function Ajuste() {
  const navigate = useNavigate();
  const local = useLocation();
  const [params] = useSearchParams();
  const produtoUrl = params.get('produto');

  const [produto, setProduto] = useState<ProdutoOut | null>(null);
  const [carregandoProduto, setCarregandoProduto] = useState(false);
  const [erroProduto, setErroProduto] = useState<string | null>(null);
  const [contado, setContado] = useState<number>(0);
  const [motivo, setMotivo] = useState<MotivoAjuste | null>(null);
  const [detalhe, setDetalhe] = useState('');
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
        if (!ativo) return;
        setProduto(dados);
        setContado(dados.saldo);
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

  function escolherProduto(escolhido: ProdutoOut) {
    setProduto(escolhido);
    setContado(escolhido.saldo);
    setMotivo(null);
    setDetalhe('');
    setErroEnvio(null);
  }

  function ajustarContagem(delta: number) {
    setContado((atual) => Math.max(0, arredondar(atual + delta)));
  }

  const diferenca = produto !== null ? arredondar(contado - produto.saldo) : 0;
  const semDiferenca = diferenca === 0;
  const podeSalvar = produto !== null && !semDiferenca && motivo !== null && !enviando;

  async function salvar() {
    if (!produto || !podeSalvar || motivo === null) return;
    const rotulo = MOTIVOS.find((opcao) => opcao.valor === motivo)?.rotulo ?? '';
    const justificativa = detalhe.trim() ? `${rotulo}: ${detalhe.trim()}` : rotulo;
    setEnviando(true);
    setErroEnvio(null);
    try {
      const registro = await api.post<RegistroOut>('/movimentacoes/ajuste', {
        produto_id: produto.id,
        quantidade_contada: contado,
        justificativa,
      });
      setConcluido(registro);
    } catch (falha) {
      setErroEnvio(mensagemDeFalha(falha));
    } finally {
      setEnviando(false);
    }
  }

  if (concluido) {
    return (
      <main className="page">
        <Toast
          mensagem="Ajuste registrado"
          detalhe={`Saldo agora: ${formatQuantidade(concluido.saldo_atual, concluido.movimentacao.unidade)}`}
          onFechar={fechar}
          duracao={2200}
        />
      </main>
    );
  }

  return (
    <main className="page ajuste">
      <header className="page-header">
        <button type="button" className="botao-icone" onClick={fechar} aria-label="Voltar">
          <Icon name="voltar" />
        </button>
        <div className="ajuste-titulo">
          <h1 className="page-title">Conferir estoque</h1>
          {produto && <span className="texto-secundario">{produto.nome}</span>}
        </div>
      </header>

      {carregandoProduto && <Loading texto="Carregando produto…" />}

      {!carregandoProduto && erroProduto && <p className="campo-erro" role="alert">{erroProduto}</p>}

      {!carregandoProduto && !produto && <ProdutoEscolha onSelecionar={escolherProduto} />}

      {!carregandoProduto && produto && (
        <div className="ajuste-corpo">
          <div className="ajuste-coluna-contagem">
            <div className="ajuste-contagem">
              <div className="ajuste-cartao">
                <span className="ajuste-cartao-rotulo">No sistema</span>
                <span className="ajuste-cartao-valor ajuste-sistema">{formatNumero(produto.saldo)}</span>
                <span className="texto-secundario">{produto.unidade}</span>
              </div>
              <div className="ajuste-cartao ajuste-cartao-contado">
                <span className="ajuste-cartao-rotulo ajuste-cartao-rotulo-destaque">Eu contei</span>
                <span className="ajuste-cartao-valor">{formatNumero(contado)}</span>
                <div className="ajuste-passos">
                  <button type="button" aria-label="Menos um" onClick={() => ajustarContagem(-1)} disabled={contado <= 0}>
                    <Icon name="menos" size={18} />
                  </button>
                  <button type="button" aria-label="Mais um" onClick={() => ajustarContagem(1)}>
                    <Icon name="mais" size={18} />
                  </button>
                </div>
              </div>
            </div>

            <div className={semDiferenca ? 'ajuste-diferenca ajuste-diferenca-ok' : 'ajuste-diferenca'}>
              <span>Diferença</span>
              <strong>
                {semDiferenca
                  ? 'Nada a ajustar'
                  : `${diferenca > 0 ? '+' : '−'}${formatQuantidade(Math.abs(diferenca), produto.unidade)}`}
              </strong>
            </div>
          </div>

          <div className="ajuste-coluna-motivo">
            <section className="ajuste-motivos">
              <h2 className="ajuste-secao-titulo">
                O que aconteceu? <span>(obrigatório)</span>
              </h2>
              <div role="radiogroup" aria-label="Motivo do ajuste" className="ajuste-opcoes">
                {MOTIVOS.map((opcao) => {
                  const selecionado = motivo === opcao.valor;
                  return (
                    <button
                      key={opcao.valor}
                      type="button"
                      role="radio"
                      aria-checked={selecionado}
                      className={selecionado ? 'ajuste-opcao ajuste-opcao-selecionada' : 'ajuste-opcao'}
                      onClick={() => setMotivo(opcao.valor)}
                    >
                      <span className="ajuste-opcao-bolinha" aria-hidden="true" />
                      {opcao.rotulo}
                    </button>
                  );
                })}
              </div>
              <label className="ajuste-detalhe">
                Detalhe (opcional)
                <input
                  type="text"
                  placeholder="Ex.: contagem de 25/11"
                  maxLength={160}
                  value={detalhe}
                  onChange={(evento) => setDetalhe(evento.target.value)}
                />
              </label>
            </section>

            {erroEnvio && <p className="campo-erro" role="alert">{erroEnvio}</p>}

            <div className="ajuste-rodape">
              <button type="button" className="btn btn-primario ajuste-salvar" disabled={!podeSalvar} onClick={salvar}>
                {enviando ? 'Salvando…' : 'Salvar ajuste'}
              </button>
              <span className="ajuste-aviso">Fica no histórico. Nada é apagado.</span>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
