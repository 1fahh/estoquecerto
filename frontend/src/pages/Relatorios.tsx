import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, baixarCsv, qs } from '../api';
import { BottomNav } from '../components/BottomNav';
import { Icon, type IconName } from '../components/Icon';
import { Loading } from '../components/Loading';
import { formatMoeda, formatNumero } from '../format';
import type { AlertaOut, ConfiguracoesOut, MovimentacaoLista, ParadosOut, ProdutoOut } from '../types';
import { formatarPeriodo, janelaIso, plural } from './relatorios/periodo';
import './Relatorios.css';

const ATALHOS = [15, 30, 90] as const;
const PERIODO_PADRAO = 15;

type Resumo = {
  produtos: number;
  alertas: number;
  paradosQtd: number;
  paradosValor: number;
  paradosDias: number;
};

type Relatorio = {
  id: string;
  titulo: string;
  subtitulo: string;
  icone: IconName;
  destaque?: boolean;
  caminho: string;
  nomeArquivo: string;
};

async function carregarResumo(): Promise<Resumo> {
  const [produtos, alertas, configuracao] = await Promise.all([
    api.get<ProdutoOut[]>('/produtos?ativo=true'),
    api.get<AlertaOut[]>('/alertas?situacao=ativo'),
    api.get<ConfiguracoesOut>('/configuracoes'),
  ]);
  const parados = await api.get<ParadosOut>(`/relatorios/parados${qs({ dias: configuracao.periodo_parado_dias })}`);
  return {
    produtos: produtos.length,
    alertas: alertas.length,
    paradosQtd: parados.itens.length,
    paradosValor: parados.total_valor,
    paradosDias: configuracao.periodo_parado_dias,
  };
}

export function Relatorios() {
  const [{ de, ate }, setPeriodo] = useState(() => janelaIso(PERIODO_PADRAO));
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [totalMovimentacoes, setTotalMovimentacoes] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const [baixando, setBaixando] = useState<string | null>(null);
  const [erroDownload, setErroDownload] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    setErro(null);
    carregarResumo()
      .then((dados) => {
        if (ativo) setResumo(dados);
      })
      .catch((falha: unknown) => {
        if (ativo) setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar os relatórios.');
      });
    return () => {
      ativo = false;
    };
  }, [tentativa]);

  useEffect(() => {
    let ativo = true;
    setTotalMovimentacoes(null);
    api
      .get<MovimentacaoLista>(`/movimentacoes${qs({ de, ate, limite: 1 })}`)
      .then((lista) => {
        if (ativo) setTotalMovimentacoes(lista.total);
      })
      .catch(() => {
        if (ativo) setTotalMovimentacoes(null);
      });
    return () => {
      ativo = false;
    };
  }, [de, ate]);

  async function baixar(relatorio: Relatorio) {
    setBaixando(relatorio.id);
    setErroDownload(null);
    try {
      await baixarCsv(relatorio.caminho, relatorio.nomeArquivo);
    } catch (falha) {
      setErroDownload(falha instanceof Error ? falha.message : 'Não foi possível baixar o arquivo.');
    } finally {
      setBaixando(null);
    }
  }

  const periodoCsv = { de, ate };
  const relatorios: Relatorio[] = [
    {
      id: 'estoque',
      titulo: 'Estoque atual',
      subtitulo: resumo
        ? `${formatNumero(resumo.produtos)} ${plural(resumo.produtos, 'produto', 'produtos')} · saldo, limite e valor`
        : 'Saldo, limite e valor de cada produto',
      icone: 'caixa',
      caminho: '/relatorios/exportar/estoque.csv',
      nomeArquivo: 'estoquecerto-estoque.csv',
    },
    {
      id: 'movimentacoes',
      titulo: 'Movimentações',
      subtitulo:
        totalMovimentacoes !== null
          ? `${formatNumero(totalMovimentacoes)} ${plural(totalMovimentacoes, 'registro', 'registros')} no período`
          : 'Entradas, saídas e ajustes do período',
      icone: 'relogio',
      caminho: `/relatorios/exportar/movimentacoes.csv${qs(periodoCsv)}`,
      nomeArquivo: 'estoquecerto-movimentacoes.csv',
    },
    {
      id: 'parados',
      titulo: 'Produtos parados',
      subtitulo: resumo
        ? `${formatNumero(resumo.paradosQtd)} ${plural(resumo.paradosQtd, 'produto', 'produtos')} · ${formatMoeda(resumo.paradosValor)}`
        : '—',
      icone: 'alerta',
      caminho: `/relatorios/exportar/parados.csv${qs({ dias: resumo?.paradosDias })}`,
      nomeArquivo: 'estoquecerto-parados.csv',
    },
    {
      id: 'reposicao',
      titulo: 'Lista de reposição',
      subtitulo: resumo
        ? `${formatNumero(resumo.alertas)} ${plural(resumo.alertas, 'alerta ativo', 'alertas ativos')} · pronta para cotar`
        : '—',
      icone: 'sino',
      destaque: true,
      caminho: '/relatorios/exportar/reposicao.csv',
      nomeArquivo: 'estoquecerto-reposicao.csv',
    },
  ];

  return (
    <>
      <main className="page relatorios">
        <header className="relatorios-topo">
          <h1 className="relatorios-titulo">Relatórios</h1>
          <span className="texto-secundario">Baixe em CSV e abra no Excel ou Google Planilhas</span>
        </header>

        <section className="relatorios-periodo" aria-label="Período dos relatórios">
          <span className="campo-rotulo">Período</span>
          <div className="chips">
            {ATALHOS.map((dias) => {
              const janela = janelaIso(dias);
              const ativo = janela.de === de && janela.ate === ate;
              return (
                <button
                  key={dias}
                  type="button"
                  className="chip"
                  aria-pressed={ativo}
                  onClick={() => setPeriodo(janela)}
                >
                  {dias} dias
                </button>
              );
            })}
          </div>
          <div className="relatorios-datas">
            <label className="campo">
              <span className="campo-rotulo">De</span>
              <input
                type="date"
                value={de}
                max={ate}
                onChange={(evento) => evento.target.value && setPeriodo({ de: evento.target.value, ate })}
              />
            </label>
            <label className="campo">
              <span className="campo-rotulo">Até</span>
              <input
                type="date"
                value={ate}
                min={de}
                onChange={(evento) => evento.target.value && setPeriodo({ de, ate: evento.target.value })}
              />
            </label>
          </div>
          <p className="texto-secundario">{formatarPeriodo(de, ate)}</p>
        </section>

        {erro && (
          <div className="card stack" role="alert">
            <p className="campo-erro">{erro}</p>
            <button type="button" className="btn btn-secundario" onClick={() => setTentativa((n) => n + 1)}>
              Tentar novamente
            </button>
          </div>
        )}

        {!resumo && !erro && <Loading />}

        {resumo && (
          <div className="relatorios-cartoes">
            {relatorios.map((relatorio) => (
              <CartaoRelatorio
                key={relatorio.id}
                titulo={relatorio.titulo}
                subtitulo={relatorio.subtitulo}
                icone={relatorio.icone}
                destaque={relatorio.destaque}
                rotuloBotao={`Baixar ${relatorio.titulo.toLowerCase()}`}
                ocupado={baixando === relatorio.id}
                onBaixar={() => baixar(relatorio)}
              />
            ))}
          </div>
        )}

        {erroDownload && (
          <p className="campo-erro" role="alert">
            {erroDownload}
          </p>
        )}

        <Link to="/importar" className="relatorios-importar">
          Importar produtos por CSV
        </Link>
      </main>
      <BottomNav />
    </>
  );
}

type CartaoProps = {
  titulo: string;
  subtitulo: string;
  icone: IconName;
  destaque?: boolean;
  rotuloBotao: string;
  ocupado: boolean;
  onBaixar: () => void;
};

function CartaoRelatorio({ titulo, subtitulo, icone, destaque, rotuloBotao, ocupado, onBaixar }: CartaoProps) {
  return (
    <div className="card relatorios-cartao">
      <span className={`relatorios-icone${destaque ? ' relatorios-icone-alerta' : ''}`}>
        <Icon name={icone} />
      </span>
      <span className="relatorios-cartao-texto">
        <strong>{titulo}</strong>
        <span className="texto-secundario">{subtitulo}</span>
      </span>
      <button type="button" className="relatorios-baixar" aria-label={rotuloBotao} title={rotuloBotao} onClick={onBaixar} disabled={ocupado}>
        <Icon name="download" />
      </button>
    </div>
  );
}
