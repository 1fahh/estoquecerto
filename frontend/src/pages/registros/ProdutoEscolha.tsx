import { useEffect, useState } from 'react';
import { api } from '../../api';
import { EmptyState } from '../../components/EmptyState';
import { Icon } from '../../components/Icon';
import { Loading } from '../../components/Loading';
import { formatQuantidade } from '../../format';
import type { MaisUsado, ProdutoOut } from '../../types';
import { mensagemDeFalha } from './utilitarios';

type Props = {
  onSelecionar: (produto: ProdutoOut) => void;
};

export function ProdutoEscolha({ onSelecionar }: Props) {
  const [busca, setBusca] = useState('');
  const [maisUsados, setMaisUsados] = useState<MaisUsado[]>([]);
  const [produtos, setProdutos] = useState<ProdutoOut[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [escolhendo, setEscolhendo] = useState<number | null>(null);

  useEffect(() => {
    let ativo = true;
    api
      .get<MaisUsado[]>('/movimentacoes/mais-usados?limite=6')
      .then((lista) => {
        if (ativo) setMaisUsados(lista);
      })
      .catch(() => undefined);
    return () => {
      ativo = false;
    };
  }, []);

  useEffect(() => {
    let ativo = true;
    const temporizador = window.setTimeout(() => {
      api
        .get<ProdutoOut[]>(`/produtos?ativo=true&busca=${encodeURIComponent(busca.trim())}`)
        .then((lista) => {
          if (!ativo) return;
          setProdutos(lista);
          setErro(null);
        })
        .catch((falha: unknown) => {
          if (ativo) setErro(mensagemDeFalha(falha));
        });
    }, 250);
    return () => {
      ativo = false;
      window.clearTimeout(temporizador);
    };
  }, [busca]);

  function escolherMaisUsado(produtoId: number) {
    setEscolhendo(produtoId);
    setErro(null);
    api
      .get<ProdutoOut>(`/produtos/${produtoId}`)
      .then(onSelecionar)
      .catch((falha: unknown) => setErro(mensagemDeFalha(falha)))
      .finally(() => setEscolhendo(null));
  }

  const buscando = busca.trim() !== '';
  const mostrarMaisUsados = !buscando && maisUsados.length > 0;

  return (
    <div className="stack">
      <label className="campo-busca">
        <Icon name="busca" size={20} />
        <input
          type="search"
          placeholder="Buscar produto"
          value={busca}
          onChange={(evento) => setBusca(evento.target.value)}
          autoComplete="off"
        />
      </label>

      {erro && <p className="campo-erro" role="alert">{erro}</p>}

      {mostrarMaisUsados && (
        <section className="stack">
          <h2 className="texto-secundario texto-destaque">Mais usados</h2>
          <ul className="lista">
            {maisUsados.map((item) => (
              <li key={item.produto_id}>
                <button
                  type="button"
                  className="lista-item lista-item-botao"
                  disabled={escolhendo !== null}
                  onClick={() => escolherMaisUsado(item.produto_id)}
                >
                  <span className="lista-item-texto">
                    <strong>{item.nome}</strong>
                    <span className="texto-secundario">{item.saidas_30d} saídas nos últimos 30 dias</span>
                  </span>
                  <Icon name="saida" size={18} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {produtos === null && !erro && <Loading />}

      {produtos !== null && produtos.length === 0 && (
        <EmptyState titulo="Nenhum produto encontrado" texto="Confira o nome ou o código." />
      )}

      {produtos !== null && produtos.length > 0 && (
        <section className="stack">
          <h2 className="texto-secundario texto-destaque">{buscando ? 'Resultados' : 'Todos os produtos'}</h2>
          <ul className="lista">
            {produtos.map((produto) => (
              <li key={produto.id}>
                <button type="button" className="lista-item lista-item-botao" onClick={() => onSelecionar(produto)}>
                  <span className="lista-item-texto">
                    <strong>{produto.nome}</strong>
                    <span className="texto-secundario">{produto.categoria_nome ?? 'Sem categoria'}</span>
                  </span>
                  <span className="texto-secundario">{formatQuantidade(produto.saldo, produto.unidade)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
