import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Icon } from '../components/Icon';
import { Loading } from '../components/Loading';
import { Sheet } from '../components/Sheet';
import { Toast } from '../components/Toast';
import { formatNumero, formatQuantidade } from '../format';
import type { MotivoSaida, ProdutoOut, RegistroOut } from '../types';
import { ProdutoEscolha } from './registros/ProdutoEscolha';
import { arredondar, lerNumero, mensagemDeFalha, voltarOuIr } from './registros/utilitarios';
import './Saida.css';

const QUANTIDADES_RAPIDAS = [1, 2, 3, 4, 5];

const MOTIVOS: { valor: MotivoSaida; rotulo: string }[] = [
  { valor: 'consumo', rotulo: 'Consumo' },
  { valor: 'perda', rotulo: 'Perda' },
  { valor: 'outro', rotulo: 'Outro' },
];

export function Saida() {
  const navigate = useNavigate();
  const local = useLocation();
  const [params] = useSearchParams();
  const produtoUrl = params.get('produto');

  const [produto, setProduto] = useState<ProdutoOut | null>(null);
  const [carregandoProduto, setCarregandoProduto] = useState(false);
  const [erroProduto, setErroProduto] = useState<string | null>(null);
  const [quantidadeTexto, setQuantidadeTexto] = useState('');
  const [modoOutra, setModoOutra] = useState(false);
  const [motivo, setMotivo] = useState<MotivoSaida>('consumo');
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

  function escolherProduto(escolhido: ProdutoOut) {
    setProduto(escolhido);
    setQuantidadeTexto('');
    setModoOutra(false);
    setErroEnvio(null);
  }

  function escolherRapida(valor: number) {
    setQuantidadeTexto(String(valor));
    setModoOutra(false);
    if (produto && valor <= produto.saldo) void registrar(valor);
  }

  function escolherOutra() {
    setQuantidadeTexto('');
    setModoOutra(true);
  }

  const quantidade = lerNumero(quantidadeTexto);
  const quantidadeValida = quantidade !== null && quantidade > 0;
  const insuficiente = produto !== null && quantidade !== null && quantidadeValida && quantidade > produto.saldo;
  const podeConfirmar = produto !== null && quantidadeValida && !insuficiente && !enviando;
  const restante = produto !== null && quantidade !== null && quantidadeValida && !insuficiente ? arredondar(produto.saldo - quantidade) : null;
  const alertaSeraLigado =
    produto !== null && restante !== null && produto.limite > 0 && restante <= produto.limite && !produto.em_alerta;
  const alertaJaAtivo = produto !== null && restante !== null && produto.limite > 0 && restante <= produto.limite && produto.em_alerta;

  async function registrar(quantidadeRegistrada: number) {
    if (!produto || enviando) return;
    setEnviando(true);
    setErroEnvio(null);
    try {
      const registro = await api.post<RegistroOut>('/movimentacoes/saida', {
        produto_id: produto.id,
        quantidade: quantidadeRegistrada,
        motivo,
        motivo_detalhe: motivo === 'outro' && detalhe.trim() ? detalhe.trim() : null,
      });
      setConcluido(registro);
    } catch (falha) {
      setErroEnvio(mensagemDeFalha(falha));
    } finally {
      setEnviando(false);
    }
  }

  function confirmar() {
    if (quantidade !== null && podeConfirmar) void registrar(quantidade);
  }

  if (concluido) {
    const unidade = concluido.movimentacao.unidade;
    const detalheToast =
      `Saldo agora: ${formatQuantidade(concluido.saldo_atual, unidade)}` +
      (concluido.alerta === 'criado' ? ' · alerta de reposição ligado' : '');
    return (
      <main className="page">
        <Toast mensagem="Saída registrada" detalhe={detalheToast} onFechar={fechar} duracao={2200} />
      </main>
    );
  }

  return (
    <main className="page saida-pagina">
      <Sheet onFechar={fechar}>
        <div className="saida-cabecalho">
          <div className="saida-titulo">
            <span className="saida-rotulo">Saída rápida</span>
            {produto ? (
              <>
                <strong className="saida-produto">{produto.nome}</strong>
                <span className="texto-secundario">Tem {formatQuantidade(produto.saldo, produto.unidade)}</span>
              </>
            ) : (
              <strong className="saida-produto">Escolha o produto</strong>
            )}
          </div>
          <button type="button" className="saida-fechar" onClick={fechar} aria-label="Fechar">
            <Icon name="fechar" size={18} />
          </button>
        </div>

        {carregandoProduto && <Loading texto="Carregando produto…" />}

        {!carregandoProduto && erroProduto && <p className="campo-erro" role="alert">{erroProduto}</p>}

        {!carregandoProduto && !produto && <ProdutoEscolha onSelecionar={escolherProduto} />}

        {!carregandoProduto && produto && (
          <>
            <div className="saida-bloco">
              <div className="saida-motivos" role="group" aria-label="Motivo">
                <span className="campo-rotulo">Motivo</span>
                {MOTIVOS.map((opcao) => (
                  <button
                    key={opcao.valor}
                    type="button"
                    aria-pressed={motivo === opcao.valor}
                    onClick={() => setMotivo(opcao.valor)}
                  >
                    {opcao.rotulo}
                  </button>
                ))}
              </div>
              {motivo === 'outro' && (
                <input
                  className="saida-entrada-outra"
                  type="text"
                  maxLength={120}
                  placeholder="Qual o motivo? (opcional)"
                  value={detalhe}
                  onChange={(evento) => setDetalhe(evento.target.value)}
                  aria-label="Detalhe do motivo"
                />
              )}
            </div>

            <div className="saida-bloco">
              <span className="campo-rotulo">Quantidade ({produto.unidade})</span>
              <div className="saida-quantidades" role="radiogroup" aria-label="Quantidade">
                {QUANTIDADES_RAPIDAS.map((valor) => (
                  <button
                    key={valor}
                    type="button"
                    role="radio"
                    aria-checked={!modoOutra && quantidade === valor}
                    onClick={() => escolherRapida(valor)}
                  >
                    {valor}
                  </button>
                ))}
                <button
                  type="button"
                  role="radio"
                  aria-checked={modoOutra}
                  aria-label="Outra quantidade"
                  className="saida-outra"
                  onClick={escolherOutra}
                >
                  Outra
                </button>
              </div>
              {modoOutra && (
                <input
                  className="saida-entrada-outra"
                  type="text"
                  inputMode="decimal"
                  placeholder="Ex.: 2,5"
                  autoFocus
                  value={quantidadeTexto}
                  onChange={(evento) => setQuantidadeTexto(evento.target.value)}
                  aria-label={`Quantidade em ${produto.unidade}`}
                />
              )}
              {insuficiente && (
                <p className="campo-erro" role="alert">
                  {`Saldo insuficiente: disponível ${formatNumero(produto.saldo)} ${produto.unidade}, saída pedida ${formatNumero(quantidade ?? 0)} ${produto.unidade}.`}
                </p>
              )}
            </div>

            {restante !== null && (
              <p className="saida-previa">
                Ficam <strong className={alertaSeraLigado ? 'saida-previa-alerta' : undefined}>{formatQuantidade(restante, produto.unidade)}</strong>
                {alertaSeraLigado && ' — abaixo do limite, alerta será ligado.'}
                {alertaJaAtivo && ' — o produto já está em alerta.'}
              </p>
            )}

            {erroEnvio && <p className="campo-erro" role="alert">{erroEnvio}</p>}

            <button type="button" className="btn btn-primario saida-confirmar" disabled={!podeConfirmar} onClick={confirmar}>
              {enviando
                ? 'Registrando…'
                : quantidadeValida
                  ? `Tirar ${formatNumero(quantidade)} ${produto.unidade} do estoque`
                  : 'Informe a quantidade'}
            </button>

            <button type="button" className="btn btn-fantasma saida-trocar" onClick={() => setProduto(null)}>
              Trocar produto
            </button>
          </>
        )}
      </Sheet>
    </main>
  );
}
