import { useEffect, useState } from 'react';
import { api } from '../api';
import { formatQuantidade } from '../format';
import type { ProdutoOut } from '../types';
import { EmptyState } from './EmptyState';
import { Icon } from './Icon';
import { Loading } from './Loading';

type Props = {
  onSelecionar: (produto: ProdutoOut) => void;
};

export function ProdutoPicker({ onSelecionar }: Props) {
  const [busca, setBusca] = useState('');
  const [produtos, setProdutos] = useState<ProdutoOut[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    const temporizador = window.setTimeout(() => {
      const termo = encodeURIComponent(busca.trim());
      api
        .get<ProdutoOut[]>(`/produtos?ativo=true&busca=${termo}`)
        .then((lista) => {
          if (!ativo) return;
          setProdutos(lista);
          setErro(null);
        })
        .catch((falha: unknown) => {
          if (!ativo) return;
          setErro(falha instanceof Error ? falha.message : 'Não foi possível buscar os produtos.');
        });
    }, 250);
    return () => {
      ativo = false;
      window.clearTimeout(temporizador);
    };
  }, [busca]);

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
      {erro && <p className="campo-erro">{erro}</p>}
      {produtos === null && !erro && <Loading />}
      {produtos !== null && produtos.length === 0 && (
        <EmptyState titulo="Nenhum produto encontrado" texto="Confira o nome ou o código." />
      )}
      {produtos !== null && produtos.length > 0 && (
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
      )}
    </div>
  );
}
