const FUSO = 'America/Sao_Paulo';
const MS_DIA = 86400000;

const formatadorChave = new Intl.DateTimeFormat('en-CA', {
  timeZone: FUSO,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

function partesDe(iso: string): [number, number, number] {
  const [ano, mes, dia] = iso.split('-').map(Number);
  return [ano, mes, dia];
}

function utcDe(iso: string): number {
  const [ano, mes, dia] = partesDe(iso);
  return Date.UTC(ano, mes - 1, dia);
}

export function chaveDoDia(data: Date): string {
  return formatadorChave.format(data);
}

export function hojeIso(): string {
  return chaveDoDia(new Date());
}

export function deslocarIso(iso: string, dias: number): string {
  return new Date(utcDe(iso) + dias * MS_DIA).toISOString().slice(0, 10);
}

export function janelaIso(dias: number): { de: string; ate: string } {
  const ate = hojeIso();
  return { de: deslocarIso(ate, -(dias - 1)), ate };
}

export function diasNoPeriodo(de: string, ate: string): number {
  return Math.round((utcDe(ate) - utcDe(de)) / MS_DIA) + 1;
}

export function formatarPeriodo(de: string, ate: string): string {
  const formatar = (iso: string) => {
    const [ano, mes, dia] = partesDe(iso);
    return new Intl.DateTimeFormat('pt-BR', { day: 'numeric', month: 'long' }).format(new Date(ano, mes - 1, dia));
  };
  return `${formatar(de)} a ${formatar(ate)}`;
}

export function plural(quantidade: number, singular: string, plural: string): string {
  return quantidade === 1 ? singular : plural;
}
