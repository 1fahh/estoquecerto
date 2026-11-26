import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { SideNav } from './components/SideNav';
import { Alertas } from './pages/Alertas';
import { Ajuste } from './pages/Ajuste';
import { Conta } from './pages/Conta';
import { Entrada } from './pages/Entrada';
import { Historico } from './pages/Historico';
import { ImportarCsv } from './pages/ImportarCsv';
import { Login } from './pages/Login';
import { Painel } from './pages/Painel';
import { Parados } from './pages/Parados';
import { ProdutoForm } from './pages/ProdutoForm';
import { Produtos } from './pages/Produtos';
import { Relatorios } from './pages/Relatorios';
import { Saida } from './pages/Saida';

function AreaProtegida() {
  return (
    <ProtectedRoute>
      <SideNav />
      <div className="app-conteudo">
        <Outlet />
      </div>
    </ProtectedRoute>
  );
}

export function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<AreaProtegida />}>
          <Route path="/" element={<Painel />} />
          <Route path="/produtos" element={<Produtos />} />
          <Route path="/produtos/novo" element={<ProdutoForm />} />
          <Route path="/produtos/:id" element={<ProdutoForm />} />
          <Route path="/saida" element={<Saida />} />
          <Route path="/entrada" element={<Entrada />} />
          <Route path="/ajuste" element={<Ajuste />} />
          <Route path="/historico" element={<Historico />} />
          <Route path="/parados" element={<Parados />} />
          <Route path="/relatorios" element={<Relatorios />} />
          <Route path="/alertas" element={<Alertas />} />
          <Route path="/importar" element={<ImportarCsv />} />
          <Route path="/conta" element={<Conta />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
