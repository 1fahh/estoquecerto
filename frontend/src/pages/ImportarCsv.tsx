import { useState, type FormEvent } from 'react';
import { api, baixarCsv } from '../api';
import { Icon } from '../components/Icon';
import { PageHeader } from '../components/PageHeader';
import type { ImportacaoOut } from '../types';
import './ImportarCsv.css';

const COLUNAS = [
  'nome',
  'codigo',
  'categoria',
  'unidade',
  'custo_unitario',
  'estoque_minimo',
  'percentual_alerta',
  'localizacao',
  'quantidade_inicial',
];

const MENSAGEM_PADRAO = 'Não foi possível concluir a importação. Tente novamente.';

function mensagemDeFalha(falha: unknown): string {
  return falha instanceof Error ? falha.message : MENSAGEM_PADRAO;
}

export function ImportarCsv() {
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [baixando, setBaixando] = useState(false);
  const [resultado, setResultado] = useState<ImportacaoOut | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function importar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!arquivo || enviando) return;
    setEnviando(true);
    setErro(null);
    setResultado(null);
    try {
      setResultado(await api.upload('/produtos/importar', arquivo));
    } catch (falha) {
      setErro(mensagemDeFalha(falha));
    } finally {
      setEnviando(false);
    }
  }

  async function baixarModelo() {
    setBaixando(true);
    setErro(null);
    try {
      await baixarCsv('/produtos/modelo-importacao.csv', 'modelo-importacao.csv');
    } catch (falha) {
      setErro(mensagemDeFalha(falha));
    } finally {
      setBaixando(false);
    }
  }

  return (
    <main className="importar">
      <PageHeader titulo="Importar produtos" voltarPara="/relatorios" />

      <section className="importar-card">
        <p>
          Se a oficina já tem uma planilha organizada, envie o arquivo CSV e os produtos entram de uma vez. A primeira
          linha precisa ser o cabeçalho com estas colunas:
        </p>
        <ul className="importar-colunas">
          {COLUNAS.map((coluna) => (
            <li key={coluna}>{coluna}</li>
          ))}
        </ul>
        <p className="texto-secundario">
          Categorias que não existirem são criadas. Use ponto e vírgula (;) como separador e vírgula ou ponto nos
          decimais.
        </p>
        <button type="button" className="btn btn-secundario btn-bloco" onClick={() => void baixarModelo()} disabled={baixando}>
          <Icon name="download" size={20} />
          {baixando ? 'Baixando modelo…' : 'Baixar modelo CSV'}
        </button>
      </section>

      <form className="importar-card importar-formulario" onSubmit={importar}>
        <label className="importar-arquivo">
          <Icon name="upload" size={24} />
          <span className="importar-arquivo-texto">
            {arquivo ? arquivo.name : 'Escolher arquivo CSV'}
          </span>
          {arquivo && (
            <span className="texto-secundario">{Math.max(1, Math.round(arquivo.size / 1024))} KB</span>
          )}
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(evento) => {
              setArquivo(evento.target.files?.[0] ?? null);
              setResultado(null);
              setErro(null);
            }}
          />
        </label>

        {erro && <p className="campo-erro" role="alert">{erro}</p>}

        <button type="submit" className="btn btn-primario btn-bloco" disabled={!arquivo || enviando}>
          {enviando ? 'Importando…' : 'Importar planilha'}
        </button>
      </form>

      {resultado && (
        <section className="importar-card importar-resultado" aria-live="polite">
          <h2>
            {resultado.criados === 1 ? '1 produto criado' : `${resultado.criados} produtos criados`}
          </h2>
          {resultado.ignorados.length === 0 ? (
            <p className="texto-secundario">Todas as linhas foram importadas.</p>
          ) : (
            <>
              <p className="texto-secundario">
                {resultado.ignorados.length === 1
                  ? '1 linha foi ignorada:'
                  : `${resultado.ignorados.length} linhas foram ignoradas:`}
              </p>
              <ul className="importar-ignorados">
                {resultado.ignorados.map((item) => (
                  <li key={`${item.linha}-${item.motivo}`}>
                    <strong>Linha {item.linha}</strong>
                    <span>{item.motivo}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </main>
  );
}
