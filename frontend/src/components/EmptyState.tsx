import type { ReactNode } from 'react';
import { Icon, type IconName } from './Icon';

type Props = {
  icone?: IconName;
  titulo: string;
  texto?: string;
  acao?: ReactNode;
};

export function EmptyState({ icone = 'caixa', titulo, texto, acao }: Props) {
  return (
    <div className="empty-state">
      <span className="empty-state-icone">
        <Icon name={icone} size={26} />
      </span>
      <p className="empty-state-titulo">{titulo}</p>
      {texto && <p className="texto-secundario">{texto}</p>}
      {acao}
    </div>
  );
}
