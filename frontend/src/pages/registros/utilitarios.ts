import type { Location, NavigateFunction } from 'react-router-dom';

export function lerNumero(texto: string): number | null {
  const apenasNumeros = texto.replace(/[^\d.,]/g, '');
  const normalizado = apenasNumeros.includes(',') ? apenasNumeros.replace(/\./g, '').replace(',', '.') : apenasNumeros;
  if (!/^\d+(\.\d+)?$/.test(normalizado)) return null;
  return Math.round(Number(normalizado) * 1000) / 1000;
}

export function arredondar(valor: number): number {
  return Math.round(valor * 1000) / 1000;
}

export function voltarOuIr(navegar: NavigateFunction, local: Location): void {
  if (local.key !== 'default') {
    navegar(-1);
  } else {
    navegar('/');
  }
}

export function mensagemDeFalha(falha: unknown): string {
  return falha instanceof Error ? falha.message : 'Não foi possível concluir a operação. Tente novamente.';
}
