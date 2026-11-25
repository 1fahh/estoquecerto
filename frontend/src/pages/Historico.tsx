import { useEffect, useState } from 'react';
import { api, qs } from '../api';
import { BottomNav } from '../components/BottomNav';
import { EmptyState } from '../components/EmptyState';
import { Icon } from '../components/Icon';
import { Loading } from '../components/Loading';
import { ProdutoPicker } from '../components/ProdutoPicker';
import { Sheet } from '../components/Sheet';
import { formatDataRelativa, formatDia, formatHora, formatMoeda, formatNumero, formatQuantidade } from '../format';
import type { MovimentacaoLista, MovimentacaoOut, ProdutoOut } from '../types';
import { diasNoPeriodo, janelaIso } from './relatorios/periodo';
import './Historico.css';

type Tipo = 'todos' | 'entrada' | 'saida' | 'ajuste';
type Periodo = '7' | '30' | '90' | 'datas';

const TAMANHO_PAGINA = 50;
const PONTOS_GRAFICO = 8;
const LIMITE_SAIDAS_MEDIA = 500;

const TIPOS: { valor: Tipo; rotulo: string }[] = [
  { valor: 'todos', rotulo: 'Todos os tipos' },
  { valor: 'entrada', rotulo: 'Entradas' },
  { valor: 'saida', rotulo: 'Saídas' },
  { valor: 'ajuste', rotulo: 'Ajustes' },
];

const PERIODOS: { valor: Periodo; rotulo: string }[] = [
  { valor: '7', rotulo: 'Últimos 7 dias' },
  { valor: '30', rotulo: 'Últimos 30 dias' },
  { valor: '90', rotulo: 'Últimos 90 dias' },
  { valor: 'datas', rotulo: 'Escolher datas' },
];

type Grupo = { chave: string; rotulo: string; itens: MovimentacaoOut[] };

function agruparPorDia(itens: MovimentacaoOut[]): Grupo[] {
  const grupos: Grupo[] = [];
  for (const item of itens) {
    const chave = formatDia(item.data_hora);
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.chave === chave) {
      ultimo.itens.push(item);
    } else {
      grupos.push({ chave, rotulo: formatDataRelativa(item.data_hora), itens: [item] });
    }
  }
  return grupos;
}

function capitalizar(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function descricao(movimentacao: MovimentacaoOut): string {
  if (movimentacao.tipo === 'entrada') {
    const custo = movimentacao.custo_unitario != null ? ` · ${formatMoeda(movimentacao.custo_unitario)}/${movimentacao.unidade}` : '';
    return `Entrada${custo}`;
  }
  if (movimentacao.tipo === 'saida') return `Saída · ${capitalizar(movimentacao.motivo ?? 'consumo')}`;
  return `Ajuste · ${capitalizar(movimentacao.motivo ?? 'sem justificativa')}`;
}

function sinalDe(movimentacao: MovimentacaoOut): '+' | '−' {
  if (movimentacao.tipo === 'entrada') return '+';
  if (movimentacao.tipo === 'saida') return '−';
  return movimentacao.quantidade >= 0 ? '+' : '−';
}

function classeDe(movimentacao: MovimentacaoOut): string {
  if (movimentacao.tipo === 'entrada') return 'historico-qtd-entrada';
  if (movimentacao.tipo === 'saida') return 'historico-qtd-saida';
  return 'historico-qtd-ajuste';
}

export function Historico() {
  const [produto, setProduto] = useState<ProdutoOut | null>(null);
  const [escolhendoProduto, setEscolhendoProduto] = useState(false);
  const [tipo, setTipo] = useState<Tipo>('todos');
  const [periodo, setPeriodo] = useState<Periodo>('30');
  const [datas, setDatas] = useState(() => janelaIso(30));
  const [itens, setItens] = useState<MovimentacaoOut[]>([]);
  const [total, setTotal] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [detalheProduto, setDetalheProduto] = useState<ProdutoOut | null>(null);
  const [mediaSaida, setMediaSaida] = useState<number | null>(null);

  const intervalo = periodo === 'datas' ? datas : janelaIso(Number(periodo));
  const { de, ate } = intervalo;

  useEffect(() => {
    let ativo = true;
    setCarregando(true);
    setErro(null);
    api
      .get<MovimentacaoLista>(
        `/movimentacoes${qs({ produto_id: produto?.id, tipo: tipo === 'todos' ? null : tipo, de, ate, limite: TAMANHO_PAGINA, offset: 0 })}`,
      )
      .then((lista) => {
        if (!ativo) return;
        setItens(lista.itens);
        setTotal(lista.total);
      })
      .catch((falha: unknown) => {
        if (ativo) setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar o histórico.');
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, [produto, tipo, de, ate]);

  useEffect(() => {
    if (!produto) {
      setDetalheProduto(null);
      setMediaSaida(null);
      return;
    }
    let ativo = true;
    Promise.all([
      api.get<ProdutoOut>(`/produtos/${produto.id}`),
      api.get<MovimentacaoLista>(
        `/movimentacoes${qs({ produto_id: produto.id, tipo: 'saida', de, ate, limite: LIMITE_SAIDAS_MEDIA })}`,
      ),
    ])
      .then(([detalhe, saidas]) => {
        if (!ativo) return;
        const soma = saidas.itens.reduce((acumulado, movimento) => acumulado + movimento.quantidade, 0);
        setDetalheProduto(detalhe);
        setMediaSaida(soma > 0 ? soma / diasNoPeriodo(de, ate) : null);
      })
      .catch((falha: unknown) => {
        if (!ativo) return;
        setDetalheProduto(null);
        setMediaSaida(null);
        setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar o gráfico do produto.');
      });
    return () => {
      ativo = false;
    };
  }, [produto, de, ate]);

  async function carregarMais() {
    setCarregandoMais(true);
    setErro(null);
    try {
      const lista = await api.get<MovimentacaoLista>(
        `/movimentacoes${qs({ produto_id: produto?.id, tipo: tipo === 'todos' ? null : tipo, de, ate, limite: TAMANHO_PAGINA, offset: itens.length })}`,
      );
      setItens((atuais) => [...atuais, ...lista.itens]);
      setTotal(lista.total);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar mais registros.');
    } finally {
      setCarregandoMais(false);
    }
  }

  const pontos = itens.slice(0, PONTOS_GRAFICO).reverse();
  const maiorValor = Math.max(detalheProduto?.limite ?? 0, ...pontos.map((ponto) => ponto.saldo_apos), 1);
  const grupos = agruparPorDia(itens);
  const mediaArredondada = mediaSaida !== null ? Math.round(mediaSaida * 10) / 10 : null;
  const diasRestantes =
    detalheProduto && mediaSaida ? Math.round(detalheProduto.saldo / mediaSaida) : null;

  return (
    <>
      <main className="page historico">
        <h1 className="page-title">Histórico</h1>

        <section className="card historico-filtros" aria-label="Filtros">
          <div className="historico-produto">
            {produto ? (
              <span className="historico-produto-ativo">
                <button type="button" className="historico-produto-nome" onClick={() => setEscolhendoProduto(true)}>
                  {produto.nome}
                </button>
                <button
                  type="button"
                  className="historico-produto-remover"
                  aria-label="Remover filtro de produto"
                  onClick={() => setProduto(null)}
                >
                  <Icon name="fechar" size={14} />
                </button>
              </span>
            ) : (
              <button type="button" className="chip" onClick={() => setEscolhendoProduto(true)}>
                <Icon name="busca" size={18} />
                Todos os produtos
              </button>
            )}
          </div>

          <div className="historico-selects">
            <label className="campo">
              <span className="campo-rotulo">Período</span>
              <select value={periodo} onChange={(evento) => setPeriodo(evento.target.value as Periodo)}>
                {PERIODOS.map((item) => (
                  <option key={item.valor} value={item.valor}>
                    {item.rotulo}
                  </option>
                ))}
              </select>
            </label>
            <label className="campo">
              <span className="campo-rotulo">Tipo</span>
              <select value={tipo} onChange={(evento) => setTipo(evento.target.value as Tipo)}>
                {TIPOS.map((item) => (
                  <option key={item.valor} value={item.valor}>
                    {item.rotulo}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {periodo === 'datas' && (
            <div className="historico-datas">
              <label className="campo">
                <span className="campo-rotulo">De</span>
                <input type="date" value={datas.de} max={datas.ate} onChange={(evento) => setDatas({ ...datas, de: evento.target.value })} />
              </label>
              <label className="campo">
                <span className="campo-rotulo">Até</span>
                <input type="date" value={datas.ate} min={datas.de} onChange={(evento) => setDatas({ ...datas, ate: evento.target.value })} />
              </label>
            </div>
          )}
        </section>

        {produto && detalheProduto && (
          <section className="card historico-grafico" aria-label={`Saldo de ${produto.nome} ao longo dos registros`}>
            <div className="historico-grafico-topo">
              <h2>Saldo depois de cada registro</h2>
              <span className="historico-grafico-limite">— limite {formatQuantidade(detalheProduto.limite, detalheProduto.unidade)}</span>
            </div>
            {pontos.length > 0 ? (
              <>
                <div className="historico-barras" style={{ gridTemplateColumns: `repeat(${pontos.length}, minmax(0, 1fr))` }}>
                  {detalheProduto.limite > 0 && (
                    <span className="historico-limite" style={{ bottom: `${(detalheProduto.limite / maiorValor) * 100}%` }} />
                  )}
                  {pontos.map((ponto) => (
                    <span
                      key={ponto.id}
                      className={`historico-barra${ponto.saldo_apos <= detalheProduto.limite ? ' historico-barra-alerta' : ''}`}
                      style={{ height: `${(ponto.saldo_apos / maiorValor) * 100}%` }}
                      title={`${formatDia(ponto.data_hora)}: ${formatQuantidade(ponto.saldo_apos, ponto.unidade)}`}
                    />
                  ))}
                </div>
                <div className="historico-eixo" style={{ gridTemplateColumns: `repeat(${pontos.length}, minmax(0, 1fr))` }}>
                  {pontos.map((ponto) => (
                    <span key={ponto.id}>{formatDia(ponto.data_hora)}</span>
                  ))}
                </div>
              </>
            ) : (
              <p className="texto-secundario">Nenhum registro para desenhar o gráfico.</p>
            )}
            {mediaArredondada !== null && (
              <p className="historico-media">
                Média de saída: cerca de {formatNumero(mediaArredondada)} {detalheProduto.unidade} por dia.
                {diasRestantes !== null && ` Nesse ritmo, o estoque dura mais uns ${diasRestantes} dias.`}
              </p>
            )}
          </section>
        )}

        {erro && (
          <div className="card stack" role="alert">
            <p className="campo-erro">{erro}</p>
          </div>
        )}

        {carregando && <Loading />}

        {!carregando && itens.length === 0 && !erro && (
          <EmptyState
            icone="relogio"
            titulo="Nenhuma movimentação neste filtro"
            texto="Mude o período ou o tipo para ver outros registros."
          />
        )}

        {!carregando && itens.length > 0 && (
          <div className="historico-lista">
            {grupos.map((grupo) => (
              <section key={grupo.chave} className="historico-dia" aria-label={grupo.rotulo}>
                <h2 className="historico-dia-titulo">{grupo.rotulo}</h2>
                <ul className="lista">
                  {grupo.itens.map((movimentacao) => (
                    <li key={movimentacao.id} className="historico-item">
                      <span className="historico-hora">{formatHora(movimentacao.data_hora)}</span>
                      <span className="historico-desc">
                        <span className="historico-tipo">{descricao(movimentacao)}</span>
                        <span className="texto-secundario">
                          {produto ? movimentacao.usuario_nome : `${movimentacao.produto_nome} · ${movimentacao.usuario_nome}`}
                        </span>
                      </span>
                      <span className="historico-valores">
                        <strong className={`historico-qtd ${classeDe(movimentacao)}`}>
                          {sinalDe(movimentacao)}
                          {formatNumero(Math.abs(movimentacao.quantidade))}
                        </strong>
                        <span className="historico-saldo">
                          saldo {formatQuantidade(movimentacao.saldo_apos, movimentacao.unidade)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}

        {!carregando && itens.length > 0 && itens.length < total && (
          <button type="button" className="btn btn-secundario btn-bloco" onClick={carregarMais} disabled={carregandoMais}>
            {carregandoMais ? 'Carregando…' : 'Carregar mais'}
          </button>
        )}
      </main>

      {escolhendoProduto && (
        <Sheet titulo="Escolher produto" onFechar={() => setEscolhendoProduto(false)}>
          <ProdutoPicker
            onSelecionar={(escolhido) => {
              setProduto(escolhido);
              setEscolhendoProduto(false);
            }}
          />
        </Sheet>
      )}

      <BottomNav />
    </>
  );
}
