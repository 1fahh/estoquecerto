import { useEffect } from 'react';
import { Icon } from './Icon';

type Props = {
  mensagem: string;
  detalhe?: string;
  onFechar: () => void;
  duracao?: number;
};

export function Toast({ mensagem, detalhe, onFechar, duracao = 4000 }: Props) {
  useEffect(() => {
    const temporizador = window.setTimeout(onFechar, duracao);
    return () => window.clearTimeout(temporizador);
  }, [onFechar, duracao]);

  return (
    <div className="toast" role="status">
      <span className="toast-icone">
        <Icon name="check" size={18} />
      </span>
      <span className="toast-texto">
        <strong>{mensagem}</strong>
        {detalhe && <span>{detalhe}</span>}
      </span>
    </div>
  );
}
