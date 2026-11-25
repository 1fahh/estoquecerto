import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth';
import { Loading } from './Loading';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { usuario, carregando } = useAuth();
  const local = useLocation();

  if (carregando) return <Loading />;
  if (!usuario) return <Navigate to="/login" replace state={{ from: local.pathname }} />;
  return <>{children}</>;
}
