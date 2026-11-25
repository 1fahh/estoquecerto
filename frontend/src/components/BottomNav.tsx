import { NavLink } from 'react-router-dom';
import { Icon, type IconName } from './Icon';

const ABAS: { to: string; rotulo: string; icone: IconName; fim?: boolean }[] = [
  { to: '/', rotulo: 'Início', icone: 'casa', fim: true },
  { to: '/produtos', rotulo: 'Produtos', icone: 'caixa' },
  { to: '/historico', rotulo: 'Histórico', icone: 'relogio' },
  { to: '/relatorios', rotulo: 'Relatórios', icone: 'relatorio' },
];

export function BottomNav() {
  return (
    <nav className="bottom-nav" aria-label="Navegação principal">
      {ABAS.map((aba) => (
        <NavLink key={aba.to} to={aba.to} end={aba.fim} className="bottom-nav-item">
          <Icon name={aba.icone} />
          <span>{aba.rotulo}</span>
        </NavLink>
      ))}
    </nav>
  );
}
