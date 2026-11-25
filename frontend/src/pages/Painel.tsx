import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';
import { BottomNav } from '../components/BottomNav';
import { Icon } from '../components/Icon';
import { Loading } from '../components/Loading';
import { formatNumero } from '../format';
import type { PainelOut } from '../types';
import './Painel.css';

const FUSO = 'America/Sao_Paulo';

function dataDeHoje(): string {
  const texto = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, weekday: 'long', day: 'numeric', month: 'long' }).format(new Date());
  const semSufixo = texto.replace('-feira', '');
  return semSufixo.charAt(0).toUpperCase() + semSufixo.slice(1);
}

function iniciais(nome: string): string {
  return nome
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte.charAt(0))
    .join('')
    .toUpperCase();
}

function primeiroNome(nome: string): string {
  return nome.trim().split(' ')[0] ?? nome;
}

function percentualDoLimite(saldo: number, limite: number): number {
  if (limite <= 0) return 0;
  return Math.max(0, Math.min(100, (saldo / limite) * 100));
}

export function Painel() {
  const { usuario } = useAuth();
  const [painel, setPainel] = useState<PainelOut | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let ativo = true;
    setErro(null);
    api
      .get<PainelOut>('/relatorios/painel')
      .then((dados) => {
        if (ativo) setPainel(dados);
      })
      .catch((falha: unknown) => {
        if (ativo) setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar o painel.');
      });
    return () => {
      ativo = false;
    };
  }, [tentativa]);

  const nome = usuario?.nome ?? '';

  return (
    <>
      <main className="page painel">
        <header className="painel-topo">
          <div className="painel-saudacao">
            <span className="painel-data">{dataDeHoje()}</span>
            <h1 className="page-title">Olá, {primeiroNome(nome)}</h1>
            <span className="painel-subtitulo">O que você vai fazer?</span>
          </div>
          <Link to="/conta" className="painel-avatar" aria-label="Minha conta">
            {iniciais(nome) || 'EC'}
          </Link>
        </header>

        {erro && (
          <div className="card stack" role="alert">
            <p className="campo-erro">{erro}</p>
            <button type="button" className="btn btn-secundario" onClick={() => setTentativa((n) => n + 1)}>
              Tentar novamente
            </button>
          </div>
        )}

        {!painel && !erro && <Loading />}

        {painel && (
          <>
            <div className="painel-acoes">
              <Link to="/saida" className="painel-acao painel-acao-principal">
                <span className="painel-acao-icone">
                  <Icon name="saida" size={26} style={{ strokeWidth: 2.4 }} />
                </span>
                <span className="painel-acao-texto">
                  <span className="painel-acao-titulo">Saída</span>
                  <span className="painel-acao-detalhe">Tirei do estoque</span>
                </span>
              </Link>
              <Link to="/entrada" className="painel-acao">
                <span className="painel-acao-icone">
                  <Icon name="entrada" size={26} style={{ strokeWidth: 2.4 }} />
                </span>
                <span className="painel-acao-texto">
                  <span className="painel-acao-titulo">Entrada</span>
                  <span className="painel-acao-detalhe">Chegou mercadoria</span>
                </span>
              </Link>
            </div>

            <section className="painel-alertas" aria-labelledby="painel-alertas-titulo">
              <div className="painel-alertas-cabecalho">
                <h2 id="painel-alertas-titulo" className="painel-alertas-titulo">
                  <span className="painel-contador">{painel.total_alertas}</span>
                  Precisam de reposição
                </h2>
                <Link to="/alertas" className="painel-link">
                  Ver todos
                </Link>
              </div>

              {painel.alertas_ativos.length === 0 && (
                <p className="painel-vazio">Nenhum produto precisa de reposição agora.</p>
              )}

              {painel.alertas_ativos.map((alerta) => (
                <div className="painel-item" key={alerta.id}>
                  <div className="painel-item-linha">
                    <span className="painel-item-nome">{alerta.produto_nome}</span>
                    <span className="painel-item-saldo">
                      {formatNumero(alerta.saldo_atual)} / {formatNumero(alerta.limite)} {alerta.unidade}
                    </span>
                  </div>
                  <div className="barra-progresso alerta" aria-hidden="true">
                    <span style={{ width: `${percentualDoLimite(alerta.saldo_atual, alerta.limite)}%` }} />
                  </div>
                </div>
              ))}

              <p className="painel-nota">Barra = saldo em relação ao limite de reposição. Avisos também por e-mail.</p>
            </section>

            <div className="painel-numeros">
              <Link to="/produtos" className="painel-numero">
                <strong>{formatNumero(painel.produtos_ativos)}</strong>
                <span>produtos</span>
              </Link>
              <Link to="/parados" className="painel-numero">
                <strong>{formatNumero(painel.parados_qtd)}</strong>
                <span>parados</span>
              </Link>
              <Link to="/historico" className="painel-numero">
                <strong>{formatNumero(painel.registros_hoje)}</strong>
                <span>hoje</span>
              </Link>
            </div>
          </>
        )}
      </main>
      <BottomNav />
    </>
  );
}
