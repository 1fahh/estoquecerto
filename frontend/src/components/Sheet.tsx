import { useEffect, useRef, type ReactNode } from 'react';

type Props = {
  titulo?: string;
  onFechar: () => void;
  children: ReactNode;
};

const SELETOR_FOCAVEL =
  'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

export function Sheet({ titulo, onFechar, children }: Props) {
  const folhaRef = useRef<HTMLDivElement>(null);
  const pressionouFundo = useRef(false);

  useEffect(() => {
    const folha = folhaRef.current;
    if (!folha) return;
    const anterior = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (!folha.contains(document.activeElement)) {
      const primeiro = folha.querySelector<HTMLElement>(SELETOR_FOCAVEL);
      (primeiro ?? folha).focus();
    }
    return () => {
      if (anterior?.isConnected) anterior.focus();
    };
  }, []);

  useEffect(() => {
    function aoPressionarTecla(evento: KeyboardEvent) {
      if (evento.key === 'Escape') {
        onFechar();
        return;
      }
      const folha = folhaRef.current;
      if (evento.key !== 'Tab' || !folha) return;
      const focaveis = Array.from(folha.querySelectorAll<HTMLElement>(SELETOR_FOCAVEL));
      if (focaveis.length === 0) {
        evento.preventDefault();
        return;
      }
      const indice = focaveis.indexOf(document.activeElement as HTMLElement);
      if (evento.shiftKey && indice <= 0) {
        evento.preventDefault();
        focaveis[focaveis.length - 1].focus();
      } else if (!evento.shiftKey && (indice === -1 || indice === focaveis.length - 1)) {
        evento.preventDefault();
        focaveis[0].focus();
      }
    }
    document.addEventListener('keydown', aoPressionarTecla);
    return () => document.removeEventListener('keydown', aoPressionarTecla);
  }, [onFechar]);

  return (
    <div
      className="sheet-overlay"
      onPointerDown={(evento) => {
        pressionouFundo.current = evento.target === evento.currentTarget;
      }}
      onClick={(evento) => {
        if (pressionouFundo.current && evento.target === evento.currentTarget) onFechar();
      }}
    >
      <div
        ref={folhaRef}
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        tabIndex={-1}
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="sheet-handle" aria-hidden="true" />
        {titulo && <h2 className="sheet-title">{titulo}</h2>}
        {children}
      </div>
    </div>
  );
}
