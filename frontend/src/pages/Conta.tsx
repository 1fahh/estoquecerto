import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setToken } from '../api';
import { useAuth } from '../auth';
import { Loading } from '../components/Loading';
import { PageHeader } from '../components/PageHeader';
import type { ConfiguracoesIn, ConfiguracoesOut, LoginResposta, TrocarSenhaIn } from '../types';
import './Conta.css';

const MENSAGEM_PADRAO = 'Não foi possível concluir a operação. Tente novamente.';

function mensagemDe(falha: unknown): string {
  return falha instanceof Error ? falha.message : MENSAGEM_PADRAO;
}

function FormularioSenha() {
  const [senhaAtual, setSenhaAtual] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [confirmacao, setConfirmacao] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);
    setSucesso(false);
    if (novaSenha.length < 8) {
      setErro('A nova senha precisa ter pelo menos 8 caracteres.');
      return;
    }
    if (novaSenha !== confirmacao) {
      setErro('A confirmação não é igual à nova senha.');
      return;
    }
    const corpo: TrocarSenhaIn = { senha_atual: senhaAtual, nova_senha: novaSenha };
    setEnviando(true);
    try {
      const resposta = await api.post<LoginResposta>('/auth/trocar-senha', corpo);
      setToken(resposta.access_token);
      setSenhaAtual('');
      setNovaSenha('');
      setConfirmacao('');
      setSucesso(true);
    } catch (falha: unknown) {
      setErro(mensagemDe(falha));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="conta-secao" aria-labelledby="conta-senha">
      <h2 id="conta-senha">Trocar senha</h2>
      <form className="conta-form" onSubmit={enviar} noValidate>
        <label className="campo">
          <span className="campo-rotulo">Senha atual</span>
          <input type="password" autoComplete="current-password" value={senhaAtual} onChange={(e) => setSenhaAtual(e.target.value)} required />
        </label>
        <label className="campo">
          <span className="campo-rotulo">Nova senha</span>
          <input type="password" autoComplete="new-password" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} required />
          <span className="campo-ajuda">Mínimo de 8 caracteres.</span>
        </label>
        <label className="campo">
          <span className="campo-rotulo">Confirmar nova senha</span>
          <input type="password" autoComplete="new-password" value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} required />
        </label>
        {erro && <p className="campo-erro" role="alert">{erro}</p>}
        {sucesso && <p className="conta-sucesso" role="status">Senha alterada com sucesso.</p>}
        <button type="submit" className="btn btn-primario btn-bloco" disabled={enviando}>
          {enviando ? 'Salvando…' : 'Trocar senha'}
        </button>
      </form>
    </section>
  );
}

function FormularioPreferencias() {
  const [config, setConfig] = useState<ConfiguracoesOut | null>(null);
  const [periodo, setPeriodo] = useState('');
  const [percentual, setPercentual] = useState('');
  const [carregando, setCarregando] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let ativo = true;
    setCarregando(true);
    setErro(null);
    api
      .get<ConfiguracoesOut>('/configuracoes')
      .then((dados) => {
        if (!ativo) return;
        setConfig(dados);
        setPeriodo(String(dados.periodo_parado_dias));
        setPercentual(String(dados.percentual_alerta_padrao));
      })
      .catch((falha: unknown) => {
        if (ativo) setErro(mensagemDe(falha));
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, [tentativa]);

  async function salvar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);
    setSucesso(false);
    const diasParado = Number(periodo);
    const percentualPadrao = Number(percentual.replace(',', '.'));
    if (!Number.isInteger(diasParado) || diasParado < 1 || diasParado > 365) {
      setErro('O período de produto parado deve ser de 1 a 365 dias.');
      return;
    }
    if (!Number.isFinite(percentualPadrao) || percentualPadrao < 0 || percentualPadrao > 100) {
      setErro('O percentual de alerta deve estar entre 0 e 100.');
      return;
    }
    const corpo: ConfiguracoesIn = { periodo_parado_dias: diasParado, percentual_alerta_padrao: percentualPadrao };
    setEnviando(true);
    try {
      const salvo = await api.put<ConfiguracoesOut>('/configuracoes', corpo);
      setConfig(salvo);
      setSucesso(true);
    } catch (falha: unknown) {
      setErro(mensagemDe(falha));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="conta-secao" aria-labelledby="conta-preferencias">
      <h2 id="conta-preferencias">Preferências do estoque</h2>
      {carregando && <Loading texto="Carregando preferências…" />}
      {!carregando && !config && (
        <div className="stack">
          <p className="campo-erro" role="alert">{erro}</p>
          <button type="button" className="btn btn-secundario" onClick={() => setTentativa((n) => n + 1)}>
            Tentar novamente
          </button>
        </div>
      )}
      {!carregando && config && (
        <form className="conta-form" onSubmit={salvar} noValidate>
          <label className="campo">
            <span className="campo-rotulo">Produto parado após (dias)</span>
            <input type="number" inputMode="numeric" min={1} max={365} step={1} value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
            <span className="campo-ajuda">Produtos sem saída nesse período aparecem como parados.</span>
          </label>
          <label className="campo">
            <span className="campo-rotulo">Percentual de alerta padrão (%)</span>
            <input type="number" inputMode="decimal" min={0} max={100} step="any" value={percentual} onChange={(e) => setPercentual(e.target.value)} />
            <span className="campo-ajuda">Aplicado a produtos que não têm percentual próprio.</span>
          </label>
          {erro && <p className="campo-erro" role="alert">{erro}</p>}
          {sucesso && <p className="conta-sucesso" role="status">Preferências salvas.</p>}
          <button type="submit" className="btn btn-primario btn-bloco" disabled={enviando}>
            {enviando ? 'Salvando…' : 'Salvar preferências'}
          </button>
        </form>
      )}
    </section>
  );
}

export function Conta() {
  const { usuario, logout } = useAuth();
  const navigate = useNavigate();

  function sair() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <main className="page">
      <PageHeader titulo="Conta" voltarPara="/" />

      <section className="conta-secao" aria-labelledby="conta-dados">
        <h2 id="conta-dados">Seu acesso</h2>
        <div className="conta-dados">
          <strong>{usuario?.nome}</strong>
          <span className="texto-secundario">{usuario?.email}</span>
        </div>
      </section>

      <FormularioSenha />
      <FormularioPreferencias />

      <button type="button" className="btn conta-sair" onClick={sair}>
        Sair
      </button>
    </main>
  );
}
