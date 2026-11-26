import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';
import { Icon } from '../components/Icon';
import './Login.css';

type EstadoDeRota = { from?: string } | null;

function mensagemDeFalha(falha: unknown): string {
  return falha instanceof Error ? falha.message : 'Não foi possível entrar. Tente novamente.';
}

export function Login() {
  const { usuario, login } = useAuth();
  const navigate = useNavigate();
  const local = useLocation();
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ajudaAberta, setAjudaAberta] = useState(false);

  const destino = (local.state as EstadoDeRota)?.from ?? '/';

  if (usuario) return <Navigate to={destino} replace />;

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (enviando) return;
    setErro(null);
    setEnviando(true);
    try {
      await login(email.trim(), senha);
      navigate(destino, { replace: true });
    } catch (falha: unknown) {
      setErro(mensagemDeFalha(falha));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="login">
      <section className="login-topo">
        <div className="login-marca">
          <span className="login-marca-icone">
            <Icon name="caixa" size={22} style={{ strokeWidth: 2.6 }} />
          </span>
          <span>EstoqueCerto</span>
        </div>

        <div className="login-aviso">
          <span className="login-aviso-icone">
            <Icon name="alerta" size={22} />
          </span>
          <div className="login-aviso-texto">
            <span className="login-aviso-rotulo">Hora de repor</span>
            <span className="login-aviso-produto">Óleo 5W30 sintético</span>
            <span className="texto-secundario">18 L · abaixo de 20% da última compra</span>
          </div>
        </div>

        <h1 className="login-titulo">O caderno da oficina, agora avisando você.</h1>
      </section>

      <section className="login-folha">
        <h2>Entrar</h2>
        <form className="login-form" onSubmit={enviar} noValidate>
          <label className="login-campo">
            E-mail
            <input
              type="email"
              name="email"
              placeholder="seu@email.com"
              autoComplete="username"
              autoCapitalize="none"
              value={email}
              onChange={(evento) => setEmail(evento.target.value)}
              required
            />
          </label>
          <label className="login-campo">
            Senha
            <input
              type="password"
              name="senha"
              autoComplete="current-password"
              value={senha}
              onChange={(evento) => setSenha(evento.target.value)}
              required
            />
          </label>

          <button type="button" className="login-esqueci" onClick={() => setAjudaAberta((aberta) => !aberta)} aria-expanded={ajudaAberta}>
            Esqueci minha senha
          </button>
          {ajudaAberta && (
            <p className="login-ajuda" role="note">
              A redefinição é feita pelo responsável pelo sistema, com o comando <code>python -m app.cli redefinir-senha</code>.
            </p>
          )}

          {erro && (
            <p className="campo-erro" role="alert">
              {erro}
            </p>
          )}

          <button type="submit" className="login-entrar" disabled={enviando}>
            {enviando ? 'Entrando…' : 'Entrar'}
          </button>
          <p className="login-primeira">Primeira vez? A equipe faz o cadastro com você.</p>
        </form>
      </section>
    </div>
  );
}
