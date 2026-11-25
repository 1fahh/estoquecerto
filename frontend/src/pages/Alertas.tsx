import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, qs } from '../api';
import { EmptyState } from '../components/EmptyState';
import { Loading } from '../components/Loading';
import { PageHeader } from '../components/PageHeader';
import { formatDataHora, formatNumero } from '../format';
import type { AlertaOut } from '../types';
import './Alertas.css';

type Aba = 'ativo' | 'encerrado';

const LIMITE_ENCERRADOS = 20;

const ABAS: { valor: Aba; rotulo: string }[] = [
  { valor: 'ativo', rotulo: 'Precisam de reposição' },
  { valor: 'encerrado', rotulo: 'Encerrados recentes' },
];

function ordenarPorEncerramento(lista: AlertaOut[]): AlertaOut[] {
  return [...lista]
    .sort((a, b) => (b.encerrado_em ?? '').localeCompare(a.encerrado_em ?? ''))
    .slice(0, LIMITE_ENCERRADOS);
}

export function Alertas() {
  const [aba, setAba] = useState<Aba>('ativo');
  const [alertas, setAlertas] = useState<AlertaOut[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let ativo = true;
    setAlertas(null);
    setErro(null);
    api
      .get<AlertaOut[]>(`/alertas${qs({ situacao: aba })}`)
      .then((lista) => {
        if (ativo) setAlertas(aba === 'encerrado' ? ordenarPorEncerramento(lista) : lista);
      })
      .catch((falha: unknown) => {
        if (ativo) setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar os alertas.');
      });
    return () => {
      ativo = false;
    };
  }, [aba, tentativa]);

  return (
    <>
      <main className="page">
        <PageHeader titulo="Alertas" voltarPara="/" />

        <div className="segmented alertas-abas" role="group" aria-label="Situação dos alertas">
          {ABAS.map((item) => (
            <button key={item.valor} type="button" aria-pressed={aba === item.valor} onClick={() => setAba(item.valor)}>
              {item.rotulo}
            </button>
          ))}
        </div>

        {erro && (
          <div className="card stack" role="alert">
            <p className="campo-erro">{erro}</p>
            <button type="button" className="btn btn-secundario" onClick={() => setTentativa((n) => n + 1)}>
              Tentar novamente
            </button>
          </div>
        )}

        {!alertas && !erro && <Loading />}

        {alertas && alertas.length === 0 && (
          <EmptyState
            icone="alerta"
            titulo={aba === 'ativo' ? 'Nenhum produto precisa de reposição' : 'Nenhum alerta encerrado recentemente'}
            texto={aba === 'ativo' ? 'Quando um produto chegar ao limite, ele aparece aqui.' : undefined}
          />
        )}

        {alertas && alertas.length > 0 && (
          <ul className="alertas-lista lista">
            {alertas.map((alerta) => (
              <li key={alerta.id}>
                {aba === 'ativo' ? (
                  <div className="alertas-item">
                    <div className="alertas-item-topo">
                      <span className="alertas-item-nome">{alerta.produto_nome}</span>
                      <span className="badge-alerta">Repor</span>
                    </div>
                    <span className="alertas-item-detalhe">
                      Saldo {formatNumero(alerta.saldo_atual)} {alerta.unidade} · limite {formatNumero(alerta.limite)} {alerta.unidade}
                    </span>
                    <Link to={`/entrada?produto=${alerta.produto_id}`} className="btn btn-primario">
                      Registrar entrada
                    </Link>
                  </div>
                ) : (
                  <div className="alertas-item alertas-item-encerrado">
                    <div className="alertas-item-topo">
                      <span className="alertas-item-nome">{alerta.produto_nome}</span>
                      <span className="badge-alerta">Encerrado</span>
                    </div>
                    <span className="alertas-item-detalhe">
                      Reposto em {alerta.encerrado_em ? formatDataHora(alerta.encerrado_em) : '—'}
                    </span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>
    </>
  );
}
