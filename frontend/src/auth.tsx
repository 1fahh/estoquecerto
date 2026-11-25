import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, clearToken, EVENTO_SESSAO_EXPIRADA, getToken, setToken } from './api';
import type { LoginResposta, Usuario } from './types';

type AuthValor = {
  usuario: Usuario | null;
  carregando: boolean;
  login: (email: string, senha: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthValor | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState<boolean>(() => getToken() !== null);

  useEffect(() => {
    if (!getToken()) return;
    let ativo = true;
    api
      .get<Usuario>('/auth/me')
      .then((dados) => {
        if (ativo) setUsuario(dados);
      })
      .catch(() => {
        clearToken();
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, []);

  useEffect(() => {
    const expirou = () => setUsuario(null);
    window.addEventListener(EVENTO_SESSAO_EXPIRADA, expirou);
    return () => window.removeEventListener(EVENTO_SESSAO_EXPIRADA, expirou);
  }, []);

  const login = useCallback(async (email: string, senha: string) => {
    const resposta = await api.post<LoginResposta>('/auth/login', { email, senha });
    setToken(resposta.access_token);
    setUsuario(resposta.usuario);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUsuario(null);
  }, []);

  const valor = useMemo(() => ({ usuario, carregando, login, logout }), [usuario, carregando, login, logout]);

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValor {
  const contexto = useContext(AuthContext);
  if (!contexto) throw new Error('useAuth deve ser usado dentro de AuthProvider');
  return contexto;
}
