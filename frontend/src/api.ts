import type { ImportacaoOut } from './types';

const TOKEN_KEY = 'estoquecerto.token';
export const EVENTO_SESSAO_EXPIRADA = 'estoquecerto:sessao-expirada';

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    return;
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    return;
  }
}

export class ApiError extends Error {
  readonly status: number;

  constructor(mensagem: string, status: number) {
    super(mensagem);
    this.name = 'ApiError';
    this.status = status;
  }
}

type Params = Record<string, string | number | boolean | null | undefined>;

export function qs(params: Params): string {
  const partes = Object.entries(params)
    .filter(([, valor]) => valor !== undefined && valor !== null && valor !== '')
    .map(([chave, valor]) => `${encodeURIComponent(chave)}=${encodeURIComponent(String(valor))}`);
  return partes.length ? `?${partes.join('&')}` : '';
}

const MENSAGEM_PADRAO = 'Não foi possível concluir a operação. Tente novamente.';

function mensagemDeErro(corpo: unknown): string {
  if (corpo && typeof corpo === 'object' && 'detail' in corpo) {
    const detalhe = (corpo as { detail: unknown }).detail;
    if (typeof detalhe === 'string') return detalhe;
    if (Array.isArray(detalhe)) {
      const mensagens = detalhe
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : ''))
        .filter(Boolean);
      if (mensagens.length) return mensagens.join(' ');
    }
  }
  return MENSAGEM_PADRAO;
}

const MENSAGEM_REDE = 'Sem conexão com o servidor. Verifique sua internet e tente novamente.';

async function buscar(url: string, opcoes: RequestInit): Promise<Response> {
  try {
    return await fetch(url, opcoes);
  } catch (falha) {
    if (falha instanceof TypeError) throw new ApiError(MENSAGEM_REDE, 0);
    throw falha;
  }
}

type Opcoes = Omit<RequestInit, 'body'> & { json?: unknown; body?: BodyInit };

async function requisitar<T>(caminho: string, opcoes: Opcoes = {}): Promise<T> {
  const { json, headers: cabecalhosExtra, ...resto } = opcoes;
  const headers = new Headers(cabecalhosExtra);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let body = resto.body;
  if (json !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(json);
  }
  const resposta = await buscar(`/api${caminho}`, { ...resto, headers, body });

  if (resposta.status === 401 && !caminho.startsWith('/auth/login')) {
    clearToken();
    window.dispatchEvent(new Event(EVENTO_SESSAO_EXPIRADA));
  }
  if (!resposta.ok) {
    const corpo: unknown = await resposta.json().catch(() => null);
    throw new ApiError(mensagemDeErro(corpo), resposta.status);
  }
  if (resposta.status === 204) return undefined as T;
  return (await resposta.json()) as T;
}

export const api = {
  get: <T>(caminho: string) => requisitar<T>(caminho),
  post: <T>(caminho: string, json?: unknown) => requisitar<T>(caminho, { method: 'POST', json: json ?? {} }),
  put: <T>(caminho: string, json: unknown) => requisitar<T>(caminho, { method: 'PUT', json }),
  patch: <T>(caminho: string, json: unknown) => requisitar<T>(caminho, { method: 'PATCH', json }),
  delete: <T = void>(caminho: string) => requisitar<T>(caminho, { method: 'DELETE' }),
  upload: (caminho: string, arquivo: File) => {
    const formulario = new FormData();
    formulario.append('arquivo', arquivo);
    return requisitar<ImportacaoOut>(caminho, { method: 'POST', body: formulario });
  },
};

export async function baixarCsv(caminho: string, nomePadrao: string): Promise<void> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const resposta = await buscar(`/api${caminho}`, { headers });
  if (resposta.status === 401) {
    clearToken();
    window.dispatchEvent(new Event(EVENTO_SESSAO_EXPIRADA));
  }
  if (!resposta.ok) {
    const corpo: unknown = await resposta.json().catch(() => null);
    throw new ApiError(mensagemDeErro(corpo), resposta.status);
  }
  const nome = /filename="([^"]+)"/.exec(resposta.headers.get('Content-Disposition') ?? '')?.[1] ?? nomePadrao;
  const url = URL.createObjectURL(await resposta.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
