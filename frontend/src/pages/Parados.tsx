import { useEffect, useState } from 'react';
import { api, baixarCsv, qs } from '../api';
import { EmptyState } from '../components/EmptyState';
import { Loading } from '../components/Loading';
import { PageHeader } from '../components/PageHeader';
import { formatMoeda, formatNumero } from '../format';
import type { ParadosOut } from '../types';
import { plural } from './relatorios/periodo';
import './Parados.css';

const PERIODOS = [30, 60, 90] as const;
type Periodo = (typeof PERIODOS)[number];

export function Parados() {
  const [dias, setDias] = useState<Periodo>(30);
  const [dados, setDados] = useState<ParadosOut | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const [baixando, setBaixando] = useState(false);
  const [erroCsv, setErroCsv] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    setDados(null);
    setErro(null);
    api
      .get<ParadosOut>(`/relatorios/parados${qs({ dias })}`)
      .then((resultado) => {
        if (ativo) setDados(resultado);
      })
      .catch((falha: unknown) => {
        if (ativo) setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar os produtos parados.');
      });
    return () => {
      ativo = false;
    };
  }, [dias, tentativa]);

  async function baixar() {
    setBaixando(true);
    setErroCsv(null);
    try {
      await baixarCsv(`/relatorios/exportar/parados.csv${qs({ dias })}`, 'estoquecerto-parados.csv');
    } catch (falha) {
      setErroCsv(falha instanceof Error ? falha.message : 'Não foi possível baixar a lista.');
    } finally {
      setBaixando(false);
    }
  }

  const quantidade = dados?.itens.length ?? 0;

  return (
    <main className="page parados">
      <PageHeader titulo="Produtos parados" voltarPara="/" />

      {erro && (
        <div className="card stack" role="alert">
          <p className="campo-erro">{erro}</p>
          <button type="button" className="btn btn-secundario" onClick={() => setTentativa((n) => n + 1)}>
            Tentar novamente
          </button>
        </div>
      )}

      {!dados && !erro && <Loading />}

      {dados && (
        <div className="parados-resumo">
          <section className="parados-total" aria-label="Valor imobilizado">
            <span className="parados-total-rotulo">Dinheiro parado na prateleira</span>
            <span className="parados-total-valor">{formatMoeda(dados.total_valor)}</span>
            <span className="parados-total-texto">
              {quantidade} {plural(quantidade, 'produto', 'produtos')} sem nenhuma saída há mais de {dias} dias
            </span>
          </section>

          <div className="parados-periodo">
            <span className="parados-periodo-rotulo" id="parados-periodo-rotulo">
              Sem saída há
            </span>
            <div role="radiogroup" aria-labelledby="parados-periodo-rotulo" className="parados-chips">
              {PERIODOS.map((opcao) => (
                <button
                  key={opcao}
                  type="button"
                  role="radio"
                  aria-checked={dias === opcao}
                  className="parados-chip"
                  onClick={() => setDias(opcao)}
                >
                  {opcao === 30 ? '30 dias' : opcao}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {dados && (
        <div className="parados-detalhe">
          {dados.sem_custo_qtd > 0 && (
            <p className="parados-aviso" role="note">
              {dados.sem_custo_qtd} {plural(dados.sem_custo_qtd, 'produto parado não tem', 'produtos parados não têm')} custo
              cadastrado e {plural(dados.sem_custo_qtd, 'ficou', 'ficaram')} fora do total. Cadastre o custo para ver o valor completo.
            </p>
          )}

          {quantidade === 0 ? (
            <EmptyState
              icone="relogio"
              titulo="Nenhum produto parado"
              texto={`Todo produto com saldo teve saída nos últimos ${dias} dias.`}
            />
          ) : (
            <ul className="parados-lista">
              {dados.itens.map((item) => (
                <li key={item.produto_id} className="parados-item">
                  <span className="parados-item-texto">
                    <strong>{item.nome}</strong>
                    <span className="texto-secundario">
                      {item.custo_unitario != null
                        ? `${formatNumero(item.saldo)} ${item.unidade} × ${formatMoeda(item.custo_unitario)}`
                        : `${formatNumero(item.saldo)} ${item.unidade} · sem custo cadastrado`}
                      {` · ${item.dias_parado} ${plural(item.dias_parado, 'dia', 'dias')} parado`}
                    </span>
                  </span>
                  <strong className="parados-item-valor">{formatMoeda(item.valor)}</strong>
                </li>
              ))}
            </ul>
          )}

          <p className="parados-nota">Valor = saldo × custo unitário. Produtos sem custo cadastrado não entram no total.</p>
        </div>
      )}

      <div className="parados-acao">
        {erroCsv && (
          <p className="campo-erro" role="alert">
            {erroCsv}
          </p>
        )}

        <button type="button" className="parados-baixar" onClick={baixar} disabled={!dados || baixando || quantidade === 0}>
          {baixando ? 'Baixando…' : 'Baixar esta lista (CSV)'}
        </button>
      </div>
    </main>
  );
}
