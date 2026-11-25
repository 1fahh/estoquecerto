import type { CSSProperties } from 'react';

const CAMINHOS = {
  voltar: ['M19 12H5', 'M12 19l-7-7 7-7'],
  fechar: ['M18 6 6 18', 'M6 6l12 12'],
  busca: ['M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16z', 'M21 21l-4.3-4.3'],
  mais: ['M12 5v14', 'M5 12h14'],
  menos: ['M5 12h14'],
  saida: ['M12 21V9m0 0-5 5m5-5 5 5', 'M5 3h14'],
  entrada: ['M12 3v12m0 0-5-5m5 5 5-5', 'M5 21h14'],
  alerta: ['M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z', 'M12 9v4', 'M12 17h.01'],
  caixa: ['M21 8 12 3 3 8v8l9 5 9-5V8z', 'M3 8l9 5 9-5', 'M12 13v8'],
  relogio: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 7v5l3 2'],
  relatorio: ['M14 3H6v18h12V7l-4-4z', 'M14 3v4h4', 'M9 13h6', 'M9 17h6'],
  casa: ['M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z'],
  filtro: ['M22 3H2l8 9.46V19l4 2v-8.54L22 3z'],
  ajuste: ['M4 21v-7', 'M4 10V3', 'M12 21v-9', 'M12 8V3', 'M20 21v-5', 'M20 12V3', 'M1 14h6', 'M9 8h6', 'M17 16h6'],
  download: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M7 10l5 5 5-5', 'M12 15V3'],
  upload: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M17 8l-5-5-5 5', 'M12 3v12'],
  check: ['M20 6 9 17l-5-5'],
  cadeado: ['M5 11h14v10H5z', 'M8 11V7a4 4 0 0 1 8 0v4'],
  olho: ['M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z', 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z'],
  calendario: ['M3 4h18v18H3z', 'M16 2v4', 'M8 2v4', 'M3 10h18'],
  sino: ['M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9', 'M13.73 21a2 2 0 0 1-3.46 0'],
} as const;

export type IconName = keyof typeof CAMINHOS;

type Props = {
  name: IconName;
  size?: number;
  className?: string;
  style?: CSSProperties;
};

export function Icon({ name, size = 22, className, style }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden="true"
      focusable="false"
    >
      {CAMINHOS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
