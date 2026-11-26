import type { Location, NavigateFunction } from 'react-router-dom';
import { ApiError } from '../../api';

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

// Erros de validação do FastAPI/Pydantic (422 com detail em lista) vêm em inglês.
// Mensagens de regra de negócio do backend já são em português e não entram aqui.
const VALIDACAO_EM_INGLES = /(^|\s)(Input should|Field required|String should|Extra inputs)/;

export function mensagemDeFalha(falha: unknown): string {
  if (falha instanceof ApiError) {
    if (falha.status === 422 && VALIDACAO_EM_INGLES.test(falha.message)) {
      return 'Valor inválido. Confira os dados e tente novamente.';
    }
    return falha.message.replace(/Value error, /g, '');
  }
  return falha instanceof Error ? falha.message : 'Não foi possível concluir a operação. Tente novamente.';
}
