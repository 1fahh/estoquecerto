const FUSO = 'America/Sao_Paulo';

const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 });
const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const percentual = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });

export function formatNumero(valor: number): string {
  return numero.format(valor);
}

export function formatQuantidade(valor: number, unidade: string): string {
  return `${numero.format(valor)} ${unidade}`;
}

export function formatMoeda(valor: number | null | undefined): string {
  return valor == null ? '—' : moeda.format(valor);
}

export function formatPercentual(valor: number): string {
  return `${percentual.format(valor)}%`;
}

function chaveDia(data: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: FUSO, year: 'numeric', month: '2-digit', day: '2-digit' }).format(data);
}

function dataDe(iso: string): Date {
  const temFuso = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  return new Date(temFuso ? iso : `${iso}Z`);
}

export function formatDia(iso: string): string {
  const data = dataDe(iso);
  return new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, day: '2-digit', month: '2-digit' }).format(data);
}

export function formatDataRelativa(iso: string): string {
  const data = dataDe(iso);
  const hoje = new Date();
  const ontem = new Date(hoje.getTime() - 24 * 60 * 60 * 1000);
  const chave = chaveDia(data);
  if (chave === chaveDia(hoje)) return 'Hoje';
  if (chave === chaveDia(ontem)) return 'Ontem';
  return formatDia(iso);
}

export function formatHora(iso: string): string {
  return new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, hour: '2-digit', minute: '2-digit' }).format(dataDe(iso));
}

export function formatDataHora(iso: string): string {
  return `${formatDataRelativa(iso)}, ${formatHora(iso)}`;
}

export function formatDataCurta(iso: string): string {
  const data = dataDe(iso);
  return new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, day: '2-digit', month: '2-digit', year: 'numeric' }).format(data);
}
