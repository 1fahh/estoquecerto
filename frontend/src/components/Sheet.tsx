import { useEffect, type ReactNode } from 'react';

type Props = {
  titulo?: string;
  onFechar: () => void;
  children: ReactNode;
};

export function Sheet({ titulo, onFechar, children }: Props) {
  useEffect(() => {
    function aoPressionarTecla(evento: KeyboardEvent) {
      if (evento.key === 'Escape') onFechar();
    }
    document.addEventListener('keydown', aoPressionarTecla);
    return () => document.removeEventListener('keydown', aoPressionarTecla);
  }, [onFechar]);

  return (
    <div className="sheet-overlay" onClick={onFechar}>
      <div
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="sheet-handle" aria-hidden="true" />
        {titulo && <h2 className="sheet-title">{titulo}</h2>}
        {children}
      </div>
    </div>
  );
}
