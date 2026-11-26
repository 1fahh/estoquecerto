import { NavLink } from 'react-router-dom';
import { useAuth } from '../auth';
import { Icon, type IconName } from './Icon';

const NAVEGACAO: { to: string; rotulo: string; icone: IconName; fim?: boolean }[] = [
  { to: '/', rotulo: 'Início', icone: 'casa', fim: true },
  { to: '/produtos', rotulo: 'Produtos', icone: 'caixa' },
  { to: '/historico', rotulo: 'Histórico', icone: 'relogio' },
  { to: '/relatorios', rotulo: 'Relatórios', icone: 'relatorio' },
  { to: '/alertas', rotulo: 'Alertas', icone: 'sino' },
  { to: '/parados', rotulo: 'Parados', icone: 'calendario' },
  { to: '/ajuste', rotulo: 'Conferir estoque', icone: 'ajuste' },
  { to: '/importar', rotulo: 'Importar CSV', icone: 'upload' },
];

export function SideNav() {
  const { usuario } = useAuth();

  return (
    <aside className="side-nav">
      <div className="side-nav-marca">
        <span className="side-nav-marca-icone">
          <Icon name="caixa" size={20} />
        </span>
        <span>EstoqueCerto</span>
      </div>

      <div className="side-nav-acoes">
        <NavLink to="/saida" className="btn btn-primario">
          <Icon name="saida" size={20} />
          <span>Saída</span>
        </NavLink>
        <NavLink to="/entrada" className="btn btn-secundario">
          <Icon name="entrada" size={20} />
          <span>Entrada</span>
        </NavLink>
      </div>

      <nav className="side-nav-lista" aria-label="Navegação principal">
        {NAVEGACAO.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.fim} className="side-nav-link">
            <Icon name={item.icone} size={20} />
            <span>{item.rotulo}</span>
          </NavLink>
        ))}
      </nav>

      <NavLink to="/conta" className="side-nav-link side-nav-conta">
        <span className="side-nav-avatar" aria-hidden="true">
          {usuario?.nome.charAt(0).toUpperCase()}
        </span>
        <span className="side-nav-conta-nome">{usuario?.nome}</span>
      </NavLink>
    </aside>
  );
}
