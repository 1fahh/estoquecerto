import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, qs } from '../api';
import { BottomNav } from '../components/BottomNav';
import { EmptyState } from '../components/EmptyState';
import { Icon } from '../components/Icon';
import { Loading } from '../components/Loading';
import { formatNumero } from '../format';
import type { ProdutoOut, Situacao } from '../types';
import './Produtos.css';

const ABAS: { valor: Situacao; rotulo: string }[] = [
  { valor: 'todos', rotulo: 'Todos' },
  { valor: 'repor', rotulo: 'Repor' },
  { valor: 'parados', rotulo: 'Parados' },
];

type Contagens = Record<'repor' | 'parados', number | null>;

function useContagens(): Contagens | null {
  const [contagens, setContagens] = useState<Contagens | null>(null);

  useEffect(() => {
    let ativo = true;
    Promise.all([
      api.get<ProdutoOut[]>('/produtos?ativo=true&situacao=repor'),
      api.get<ProdutoOut[]>('/produtos?ativo=true&situacao=parados'),
    ])
      .then(([repor, parados]) => {
        if (ativo) setContagens({ repor: repor.length, parados: parados.length });
      })
      .catch(() => {
        if (ativo) setContagens({ repor: null, parados: null });
      });
    return () => {
      ativo = false;
    };
  }, []);

  return contagens;
}

export function Produtos() {
  const [termo, setTermo] = useState('');
  const [busca, setBusca] = useState('');
  const [situacao, setSituacao] = useState<Situacao>('todos');
  const [produtos, setProdutos] = useState<ProdutoOut[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const contagens = useContagens();

  useEffect(() => {
    const temporizador = window.setTimeout(() => setBusca(termo.trim()), 250);
    return () => window.clearTimeout(temporizador);
  }, [termo]);

  useEffect(() => {
    let ativo = true;
    setProdutos(null);
    setErro(null);
    api
      .get<ProdutoOut[]>(`/produtos${qs({ ativo: 'true', busca, situacao })}`)
      .then((lista) => {
        if (ativo) setProdutos(lista);
      })
      .catch((falha: unknown) => {
        if (!ativo) return;
        setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar os produtos.');
      });
    return () => {
      ativo = false;
    };
  }, [busca, situacao]);

  const nenhumCadastrado = produtos !== null && produtos.length === 0 && !busca && situacao === 'todos';

  return (
    <>
      <main className="produtos">
        <header className="produtos-topo">
          <div className="produtos-busca-linha">
            <label className="produtos-busca">
              <Icon name="busca" size={20} />
              <input
                type="search"
                placeholder="Buscar produto"
                aria-label="Buscar produto"
                value={termo}
                onChange={(evento) => setTermo(evento.target.value)}
                autoComplete="off"
              />
              {termo && (
                <button
                  type="button"
                  className="produtos-limpar"
                  aria-label="Limpar busca"
                  onClick={() => setTermo('')}
                >
                  <Icon name="fechar" size={14} />
                </button>
              )}
            </label>
            <Link to="/produtos/novo" className="produtos-novo" aria-label="Novo produto">
              <Icon name="mais" size={22} />
            </Link>
          </div>

          <div className="produtos-abas" role="group" aria-label="Situação">
            {ABAS.map((aba) => {
              const contagem = aba.valor === 'todos' ? null : contagens?.[aba.valor];
              return (
                <button
                  key={aba.valor}
                  type="button"
                  aria-pressed={situacao === aba.valor}
                  onClick={() => setSituacao(aba.valor)}
                >
                  {aba.rotulo}
                  {contagem !== null && contagem !== undefined && ` (${contagem})`}
                </button>
              );
            })}
          </div>

          {produtos !== null && busca && (
            <span className="texto-secundario">
              {produtos.length === 1 ? '1 resultado' : `${produtos.length} resultados`} para “{busca}”
            </span>
          )}
        </header>

        {erro && <p className="campo-erro produtos-aviso">{erro}</p>}
        {produtos === null && !erro && <Loading texto="Carregando produtos…" />}

        {nenhumCadastrado && (
          <EmptyState
            titulo="Nenhum produto cadastrado"
            texto="Cadastre o primeiro produto para começar a controlar o estoque."
            acao={
              <Link to="/produtos/novo" className="btn btn-primario">
                Cadastrar produto
              </Link>
            }
          />
        )}

        {produtos !== null && produtos.length === 0 && !nenhumCadastrado && (
          <EmptyState
            titulo="Nenhum produto encontrado"
            texto={busca ? 'Confira o nome ou o código.' : 'Nenhum produto nesta aba.'}
          />
        )}

        {produtos !== null && produtos.length > 0 && (
          <>
            <ul className="produtos-lista">
              {produtos.map((produto) => (
                <li key={produto.id} className="produtos-linha">
                  <Link to={`/produtos/${produto.id}`} className="produtos-nome">
                    <strong>{produto.nome}</strong>
                    {produto.em_alerta ? (
                      <span className="produtos-status-alerta">
                        Repor · limite {formatNumero(produto.limite)} {produto.unidade}
                      </span>
                    ) : (
                      <span className="texto-secundario">
                        {[produto.categoria_nome, produto.localizacao].filter(Boolean).join(' · ') || 'Sem categoria'}
                      </span>
                    )}
                  </Link>
                  <Link
                    to={`/saida?produto=${produto.id}`}
                    className="produtos-acao produtos-acao-saida"
                    aria-label={`Registrar saída de ${produto.nome}`}
                  >
                    <Icon name="menos" size={20} />
                  </Link>
                  <span className={produto.em_alerta ? 'produtos-saldo alerta' : 'produtos-saldo'}>
                    {formatNumero(produto.saldo)}
                    <span className="produtos-unidade">{produto.unidade}</span>
                  </span>
                  <Link
                    to={`/entrada?produto=${produto.id}`}
                    className="produtos-acao produtos-acao-entrada"
                    aria-label={`Registrar entrada de ${produto.nome}`}
                  >
                    <Icon name="mais" size={20} />
                  </Link>
                </li>
              ))}
            </ul>
            <p className="produtos-dica">
              <Icon name="alerta" size={20} />
              <span>
                <strong>−</strong> abre a saída e <strong>+</strong> abre a entrada já com o produto escolhido. Só falta a
                quantidade.
              </span>
            </p>
          </>
        )}
      </main>
      <BottomNav />
    </>
  );
}
