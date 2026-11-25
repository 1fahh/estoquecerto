export function Loading({ texto = 'Carregando…' }: { texto?: string }) {
  return (
    <div className="loading" role="status">
      <span className="loading-spinner" aria-hidden="true" />
      <span>{texto}</span>
    </div>
  );
}
