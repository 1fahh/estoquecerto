import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError } from '../api';
import { EmptyState } from '../components/EmptyState';
import { Loading } from '../components/Loading';
import { PageHeader } from '../components/PageHeader';
import { formatNumero, formatQuantidade } from '../format';
import type { Categoria, ConfiguracoesOut, ProdutoIn, ProdutoOut } from '../types';
import './ProdutoForm.css';

const UNIDADES: { valor: string; rotulo: string; curto: string }[] = [
  { valor: 'un', rotulo: 'Unidade (un)', curto: 'unidade' },
  { valor: 'L', rotulo: 'Litro (L)', curto: 'litro' },
  { valor: 'jogo', rotulo: 'Jogo (jogo)', curto: 'jogo' },
  { valor: 'kg', rotulo: 'Quilo (kg)', curto: 'quilo' },
  { valor: 'm', rotulo: 'Metro (m)', curto: 'metro' },
  { valor: 'cx', rotulo: 'Caixa (cx)', curto: 'caixa' },
  { valor: 'par', rotulo: 'Par (par)', curto: 'par' },
];

const PERCENTUAIS = [10, 20, 30];
const PERCENTUAL_PADRAO = 20;
const MENSAGEM_PADRAO = 'Não foi possível concluir a operação. Tente novamente.';

type Formulario = {
  nome: string;
  codigo: string;
  categoriaId: number | null;
  unidade: string;
  custo: string;
  estoqueMinimo: string;
  percentual: string;
  modoOutro: boolean;
  localizacao: string;
  observacoes: string;
  quantidadeInicial: string;
};

function lerDecimal(texto: string): number | null {
  const limpo = texto.replace(/R\$/g, '').replace(/\s/g, '');
  if (!limpo) return null;
  const milharSemDecimal = /^\d{1,3}(\.\d{3})+$/.test(limpo);
  const normalizado = limpo.includes(',') || milharSemDecimal ? limpo.replace(/\./g, '').replace(',', '.') : limpo;
  const valor = Number(normalizado);
  return Number.isFinite(valor) ? valor : null;
}

function textoDecimal(valor: number | null, minimo: number, maximo: number): string {
  if (valor === null) return '';
  return valor.toLocaleString('pt-BR', {
    minimumFractionDigits: minimo,
    maximumFractionDigits: maximo,
    useGrouping: false,
  });
}

function rotuloCurto(unidade: string): string {
  return UNIDADES.find((item) => item.valor === unidade)?.curto ?? unidade;
}

function formularioVazio(percentualPadrao: number): Formulario {
  return {
    nome: '',
    codigo: '',
    categoriaId: null,
    unidade: 'un',
    custo: '',
    estoqueMinimo: '',
    percentual: String(percentualPadrao),
    modoOutro: false,
    localizacao: '',
    observacoes: '',
    quantidadeInicial: '',
  };
}

function formularioDeProduto(produto: ProdutoOut): Formulario {
  const predefinido = PERCENTUAIS.includes(produto.percentual_alerta);
  return {
    nome: produto.nome,
    codigo: produto.codigo ?? '',
    categoriaId: produto.categoria_id,
    unidade: produto.unidade,
    custo: textoDecimal(produto.custo_unitario, 2, 2),
    estoqueMinimo: textoDecimal(produto.estoque_minimo, 0, 3),
    percentual: String(produto.percentual_alerta),
    modoOutro: !predefinido,
    localizacao: produto.localizacao ?? '',
    observacoes: produto.observacoes ?? '',
    quantidadeInicial: '',
  };
}

function montarPayload(formulario: Formulario, novo: boolean): ProdutoIn | string {
  const nome = formulario.nome.trim();
  if (!nome) return 'Informe o nome do produto.';

  const custo = formulario.custo.trim() ? lerDecimal(formulario.custo) : null;
  if (formulario.custo.trim() && (custo === null || custo < 0)) return 'Custo inválido. Use um valor como 38,90.';

  const minimo = formulario.estoqueMinimo.trim() ? lerDecimal(formulario.estoqueMinimo) : null;
  if (formulario.estoqueMinimo.trim() && (minimo === null || minimo < 0)) {
    return 'Estoque mínimo inválido. Use um número maior ou igual a zero.';
  }

  const percentual = lerDecimal(formulario.percentual);
  if (percentual === null || percentual < 0 || percentual > 100) {
    return 'O percentual de alerta deve ficar entre 0 e 100.';
  }

  const inicial = novo && formulario.quantidadeInicial.trim() ? lerDecimal(formulario.quantidadeInicial) : null;
  if (novo && formulario.quantidadeInicial.trim() && (inicial === null || inicial < 0)) {
    return 'Quantidade inicial inválida. Use um número maior ou igual a zero.';
  }

  return {
    nome,
    codigo: formulario.codigo.trim() || null,
    categoria_id: formulario.categoriaId,
    unidade: formulario.unidade,
    custo_unitario: custo,
    estoque_minimo: minimo,
    percentual_alerta: percentual,
    localizacao: formulario.localizacao.trim() || null,
    observacoes: formulario.observacoes.trim() || null,
    ...(inicial ? { quantidade_inicial: inicial } : {}),
  };
}

function mensagemDeFalha(falha: unknown): string {
  return falha instanceof Error ? falha.message : MENSAGEM_PADRAO;
}

export function ProdutoForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const editando = id !== undefined;

  const [form, setForm] = useState<Formulario | null>(null);
  const [erroCarga, setErroCarga] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [categoriaNova, setCategoriaNova] = useState<string | null>(null);
  const [erroCategoria, setErroCategoria] = useState<string | null>(null);
  const [categoriaEditada, setCategoriaEditada] = useState<string | null>(null);
  const [erroCategoriaEditada, setErroCategoriaEditada] = useState<string | null>(null);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [produto, setProduto] = useState<ProdutoOut | null>(null);

  useEffect(() => {
    let ativo = true;
    setForm(null);
    setErroCarga(null);
    setErro(null);
    setAviso(null);

    async function carregar(): Promise<{ categorias: Categoria[]; produto: ProdutoOut | null; percentualPadrao: number }> {
      const categoriasCarregadas = await api.get<Categoria[]>('/categorias');
      if (id !== undefined) {
        const produtoCarregado = await api.get<ProdutoOut>(`/produtos/${id}`);
        return { categorias: categoriasCarregadas, produto: produtoCarregado, percentualPadrao: PERCENTUAL_PADRAO };
      }
      const configuracoes = await api.get<ConfiguracoesOut>('/configuracoes').catch(() => null);
      return {
        categorias: categoriasCarregadas,
        produto: null,
        percentualPadrao: configuracoes?.percentual_alerta_padrao ?? PERCENTUAL_PADRAO,
      };
    }

    carregar()
      .then((resultado) => {
        if (!ativo) return;
        setCategorias(resultado.categorias);
        setProduto(resultado.produto);
        setForm(
          resultado.produto
            ? formularioDeProduto(resultado.produto)
            : formularioVazio(resultado.percentualPadrao),
        );
      })
      .catch((falha: unknown) => {
        if (ativo) setErroCarga(mensagemDeFalha(falha));
      });

    return () => {
      ativo = false;
    };
  }, [id]);

  function atualizar(parcial: Partial<Formulario>) {
    setForm((atual) => (atual ? { ...atual, ...parcial } : atual));
  }

  async function criarCategoria() {
    const nome = (categoriaNova ?? '').trim();
    if (!nome) {
      setErroCategoria('Informe o nome da categoria.');
      return;
    }
    try {
      const criada = await api.post<Categoria>('/categorias', { nome });
      setCategorias((lista) => [...lista, criada].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR')));
      atualizar({ categoriaId: criada.id });
      setCategoriaNova(null);
      setErroCategoria(null);
    } catch (falha) {
      setErroCategoria(mensagemDeFalha(falha));
    }
  }

  async function renomearCategoria() {
    const categoria = categorias.find((item) => item.id === form?.categoriaId);
    const nome = (categoriaEditada ?? '').trim();
    if (!categoria) return;
    if (!nome) {
      setErroCategoriaEditada('Informe o nome da categoria.');
      return;
    }
    try {
      const atualizada = await api.put<Categoria>(`/categorias/${categoria.id}`, { nome });
      setCategorias((lista) =>
        lista
          .map((item) => (item.id === atualizada.id ? atualizada : item))
          .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR')),
      );
      setCategoriaEditada(null);
      setErroCategoriaEditada(null);
    } catch (falha) {
      setErroCategoriaEditada(mensagemDeFalha(falha));
    }
  }

  async function salvar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!form || salvando) return;
    const payload = montarPayload(form, !editando);
    if (typeof payload === 'string') {
      setErro(payload);
      return;
    }
    setSalvando(true);
    setErro(null);
    try {
      if (editando) {
        await api.put<ProdutoOut>(`/produtos/${id}`, payload);
      } else {
        await api.post<ProdutoOut>('/produtos', payload);
      }
      navigate('/produtos');
    } catch (falha) {
      setErro(mensagemDeFalha(falha));
      setSalvando(false);
    }
  }

  async function alternarAtivo() {
    if (!produto || ocupado) return;
    setOcupado(true);
    setErro(null);
    try {
      const atualizado = await api.patch<ProdutoOut>(`/produtos/${produto.id}/ativo`, { ativo: !produto.ativo });
      setProduto(atualizado);
      setAviso(
        atualizado.ativo
          ? 'Produto reativado. Ele volta a aparecer nas listas de registro.'
          : 'Produto inativado. Ele some das listas de registro e continua no histórico.',
      );
    } catch (falha) {
      setErro(mensagemDeFalha(falha));
    } finally {
      setOcupado(false);
    }
  }

  async function excluir() {
    if (!produto || ocupado) return;
    if (!window.confirm('Excluir este produto? Essa ação não pode ser desfeita.')) return;
    setOcupado(true);
    setErro(null);
    try {
      await api.delete(`/produtos/${produto.id}`);
      navigate('/produtos');
    } catch (falha) {
      if (falha instanceof ApiError && falha.status === 409) {
        setErro(
          'Este produto já tem movimentações, então não pode ser excluído. Inative-o: ele some das listas de registro e continua no histórico.',
        );
      } else {
        setErro(mensagemDeFalha(falha));
      }
      setOcupado(false);
    }
  }

  if (erroCarga) {
    return (
      <div className="produto-form">
        <PageHeader titulo="Produto" voltarPara="/produtos" />
        <EmptyState
          titulo="Não foi possível abrir o produto"
          texto={erroCarga}
          acao={
            <Link to="/produtos" className="btn btn-secundario">
              Voltar aos produtos
            </Link>
          }
        />
      </div>
    );
  }

  if (!form) {
    return (
      <div className="produto-form">
        <PageHeader titulo={editando ? 'Produto' : 'Novo produto'} voltarPara="/produtos" />
        <Loading texto="Carregando produto…" />
      </div>
    );
  }

  const unidadeConhecida = UNIDADES.some((item) => item.valor === form.unidade);
  const percentualNumero = lerDecimal(form.percentual) ?? 0;
  const referencia = produto ? produto.quantidade_referencia : (lerDecimal(form.quantidadeInicial) ?? 0);
  const saldo = produto ? produto.saldo : (lerDecimal(form.quantidadeInicial) ?? 0);
  const minimo = lerDecimal(form.estoqueMinimo) ?? 0;
  const limite = Math.max(minimo, (percentualNumero / 100) * referencia);
  const emAlerta = limite > 0 && saldo <= limite;

  return (
    <div className="produto-form">
      <PageHeader titulo={editando ? (produto?.nome ?? 'Produto') : 'Novo produto'} voltarPara="/produtos" />

      {produto && (
        <p className="pf-saldo-atual">
          Saldo atual <strong>{formatQuantidade(produto.saldo, produto.unidade)}</strong>
          {produto.em_alerta && <span className="badge-alerta">Repor</span>}
        </p>
      )}

      <form className="pf-formulario" onSubmit={salvar} noValidate>
        <section className="pf-secao">
          <h2 className="pf-titulo">
            <span className="pf-numero">1</span>O que é
          </h2>

          <label className="pf-campo">
            <span className="pf-rotulo">Nome</span>
            <input
              type="text"
              value={form.nome}
              onChange={(evento) => atualizar({ nome: evento.target.value })}
              maxLength={160}
              required
            />
          </label>

          <div className="pf-rotulo">Categoria</div>
          <div className="pf-chips">
            {categorias.map((categoria) => {
              const marcada = form.categoriaId === categoria.id;
              return (
                <button
                  key={categoria.id}
                  type="button"
                  className="pf-chip"
                  aria-pressed={marcada}
                  onClick={() => {
                    atualizar({ categoriaId: marcada ? null : categoria.id });
                    setCategoriaEditada(null);
                    setErroCategoriaEditada(null);
                  }}
                >
                  {categoria.nome}
                </button>
              );
            })}
            <button
              type="button"
              className="pf-chip pf-chip-nova"
              onClick={() => {
                setCategoriaNova(categoriaNova === null ? '' : null);
                setErroCategoria(null);
              }}
            >
              + Nova
            </button>
          </div>

          {categoriaNova !== null && (
            <div className="pf-categoria-nova">
              <input
                type="text"
                placeholder="Nome da categoria"
                aria-label="Nome da nova categoria"
                value={categoriaNova}
                maxLength={80}
                onChange={(evento) => setCategoriaNova(evento.target.value)}
                onKeyDown={(evento) => {
                  if (evento.key === 'Enter') {
                    evento.preventDefault();
                    void criarCategoria();
                  }
                }}
              />
              <button type="button" className="btn btn-primario pf-botao-compacto" onClick={() => void criarCategoria()}>
                Criar
              </button>
            </div>
          )}
          {erroCategoria && <p className="campo-erro">{erroCategoria}</p>}

          {form.categoriaId !== null && categoriaEditada === null && (
            <button
              type="button"
              className="pf-botao-texto"
              onClick={() =>
                setCategoriaEditada(categorias.find((item) => item.id === form.categoriaId)?.nome ?? '')
              }
            >
              Renomear categoria selecionada
            </button>
          )}

          {categoriaEditada !== null && (
            <div className="pf-categoria-nova">
              <input
                type="text"
                aria-label="Novo nome da categoria"
                value={categoriaEditada}
                maxLength={80}
                onChange={(evento) => setCategoriaEditada(evento.target.value)}
                onKeyDown={(evento) => {
                  if (evento.key === 'Enter') {
                    evento.preventDefault();
                    void renomearCategoria();
                  }
                }}
              />
              <button type="button" className="btn btn-primario pf-botao-compacto" onClick={() => void renomearCategoria()}>
                Salvar
              </button>
              <button
                type="button"
                className="pf-botao-texto"
                onClick={() => {
                  setCategoriaEditada(null);
                  setErroCategoriaEditada(null);
                }}
              >
                Cancelar
              </button>
            </div>
          )}
          {erroCategoriaEditada && <p className="campo-erro">{erroCategoriaEditada}</p>}

          <div className="pf-linha-dupla">
            <label className="pf-campo">
              <span className="pf-rotulo">Unidade</span>
              <select value={form.unidade} onChange={(evento) => atualizar({ unidade: evento.target.value })}>
                {UNIDADES.map((item) => (
                  <option key={item.valor} value={item.valor}>
                    {item.rotulo}
                  </option>
                ))}
                {!unidadeConhecida && <option value={form.unidade}>{form.unidade}</option>}
              </select>
            </label>
            <label className="pf-campo">
              <span className="pf-rotulo">
                Código <span className="pf-opcional">(opcional)</span>
              </span>
              <input
                type="text"
                value={form.codigo}
                maxLength={60}
                onChange={(evento) => atualizar({ codigo: evento.target.value })}
              />
            </label>
          </div>

          {!editando && (
            <label className="pf-campo">
              <span className="pf-rotulo">Quanto tem agora</span>
              <input
                type="text"
                inputMode="decimal"
                placeholder="0"
                value={form.quantidadeInicial}
                onChange={(evento) => atualizar({ quantidadeInicial: evento.target.value })}
              />
              <span className="pf-ajuda">Conte o que há na oficina hoje. Esse número vira o saldo inicial.</span>
            </label>
          )}
        </section>

        <section className="pf-secao">
          <h2 className="pf-titulo">
            <span className="pf-numero">2</span>Quanto custa e onde fica
          </h2>

          <div className="pf-linha-dupla">
            <label className="pf-campo">
              <span className="pf-rotulo">Custo por {rotuloCurto(form.unidade)} (R$)</span>
              <input
                type="text"
                inputMode="decimal"
                placeholder="0,00"
                value={form.custo}
                onChange={(evento) => atualizar({ custo: evento.target.value })}
              />
            </label>
            <label className="pf-campo">
              <span className="pf-rotulo">Localização</span>
              <input
                type="text"
                value={form.localizacao}
                maxLength={120}
                onChange={(evento) => atualizar({ localizacao: evento.target.value })}
              />
            </label>
          </div>

          <label className="pf-campo">
            <span className="pf-rotulo">
              Observações <span className="pf-opcional">(opcional)</span>
            </span>
            <textarea
              value={form.observacoes}
              rows={3}
              onChange={(evento) => atualizar({ observacoes: evento.target.value })}
            />
          </label>
        </section>

        <section className="pf-secao">
          <h2 className="pf-titulo">
            <span className="pf-numero pf-numero-alerta">3</span>Quando me avisar
          </h2>

          <span className="pf-rotulo">Quando sobrar menos de</span>
          <div className="pf-percentuais">
            {PERCENTUAIS.map((percentual) => {
              const marcado = !form.modoOutro && form.percentual === String(percentual);
              return (
                <button
                  key={percentual}
                  type="button"
                  className="pf-percentual"
                  aria-pressed={marcado}
                  onClick={() => atualizar({ percentual: String(percentual), modoOutro: false })}
                >
                  {percentual}%
                </button>
              );
            })}
            <button
              type="button"
              className="pf-percentual pf-percentual-texto"
              aria-pressed={form.modoOutro}
              onClick={() =>
                atualizar({
                  modoOutro: true,
                  percentual: PERCENTUAIS.map(String).includes(form.percentual) ? '' : form.percentual,
                })
              }
            >
              Outro
            </button>
          </div>

          {form.modoOutro && (
            <label className="pf-campo">
              <span className="pf-rotulo">Percentual personalizado (0 a 100)</span>
              <input
                type="text"
                inputMode="decimal"
                placeholder="Ex.: 15"
                value={form.percentual}
                onChange={(evento) => atualizar({ percentual: evento.target.value })}
              />
            </label>
          )}

          <label className="pf-minimo">
            <span className="pf-rotulo">Nunca menos que (mínimo fixo)</span>
            <input
              type="text"
              inputMode="decimal"
              placeholder="—"
              value={form.estoqueMinimo}
              onChange={(evento) => atualizar({ estoqueMinimo: evento.target.value })}
            />
          </label>

          <p className="pf-previa">
            {referencia > 0 ? (
              <>
                Referência: {produto ? 'a última entrada' : 'a quantidade inicial'} foi de{' '}
                <strong>{formatQuantidade(referencia, form.unidade)}</strong>. O aviso chega quando restarem{' '}
                <strong>{formatQuantidade(limite, form.unidade)}</strong> — hoje há{' '}
                <strong>{formatQuantidade(saldo, form.unidade)}</strong>
                {emAlerta ? ', então este produto já está em alerta.' : ', então ainda não está em alerta.'}
              </>
            ) : (
              <>
                Ainda não há referência para calcular o aviso. Com a primeira entrada, ele passa a seguir o percentual
                escolhido
                {minimo > 0 ? ` e nunca fica abaixo de ${formatNumero(minimo)} ${form.unidade}` : ''}.
              </>
            )}
          </p>
        </section>

        {erro && (
          <p className="mensagem-erro pf-erro" role="alert">
            {erro}
          </p>
        )}
        {aviso && <p className="pf-aviso">{aviso}</p>}

        <div className="pf-rodape">
          <button type="submit" className="btn btn-primario btn-bloco pf-salvar" disabled={salvando}>
            {salvando ? 'Salvando…' : 'Salvar'}
          </button>

          {editando && produto && (
            <>
              <div className="pf-acoes-secundarias">
                <Link to={`/ajuste?produto=${produto.id}`} className="pf-link">
                  Conferir saldo (contagem)
                </Link>
                <button type="button" className="pf-botao-texto" disabled={ocupado} onClick={() => void alternarAtivo()}>
                  {produto.ativo ? 'Inativar produto' : 'Reativar produto'}
                </button>
              </div>
              {produto.ultima_movimentacao_em === null && (
                <button type="button" className="pf-excluir" disabled={ocupado} onClick={() => void excluir()}>
                  Excluir produto
                </button>
              )}
            </>
          )}
        </div>
      </form>
    </div>
  );
}
