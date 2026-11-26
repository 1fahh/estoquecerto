#!/usr/bin/env bash
# Backup do banco e teste de restauração. Uso: DATABASE_URL=postgresql://... scripts/backup.sh [pasta]
# Precisa de Docker. Restaura o dump num Postgres temporário e compara a contagem de linhas de cada tabela.
set -euo pipefail
: "${DATABASE_URL:?defina DATABASE_URL}"
pasta="${1:-$HOME/Backups/estoquecerto}"
arquivo="estoquecerto-$(date -u +%Y-%m-%d-%H%M).dump"
# O endereço direto do Neon (sem -pooler) é o indicado para pg_dump.
url="${DATABASE_URL/-pooler./.}"
conferencia="select 'usuarios', count(*) from usuarios union all select 'categorias', count(*) from categorias union all select 'produtos', count(*) from produtos union all select 'movimentacoes', count(*) from movimentacoes union all select 'alertas', count(*) from alertas union all select 'configuracoes', count(*) from configuracoes order by 1"

umask 077
mkdir -p "$pasta"
container="estoquecerto-restore-$$"
trap 'docker rm -f "$container" >/dev/null 2>&1 || true' EXIT

URL="$url" docker run --rm -e URL postgres:17 sh -c 'pg_dump --format=custom --no-owner --no-acl --dbname="$URL"' >"$pasta/$arquivo.parcial"
mv "$pasta/$arquivo.parcial" "$pasta/$arquivo"
echo "Dump: $pasta/$arquivo ($(du -h "$pasta/$arquivo" | cut -f1))"

docker run -d --name "$container" -e POSTGRES_PASSWORD=local postgres:17 >/dev/null
until docker exec "$container" pg_isready -q -h 127.0.0.1 -U postgres; do sleep 1; done
docker exec -i "$container" pg_restore --exit-on-error --no-owner --no-acl -h 127.0.0.1 -U postgres -d postgres <"$pasta/$arquivo"

origem="$(URL="$url" SQL="$conferencia" docker run --rm -e URL -e SQL postgres:17 sh -c 'psql "$URL" -At -F" " -c "$SQL"')"
copia="$(docker exec "$container" psql -h 127.0.0.1 -U postgres -At -F' ' -c "$conferencia")"
printf '%s\n' "$copia" | sed 's/^/  restaurado: /'
if [ "$origem" != "$copia" ]; then
  printf 'FALHOU: a cópia restaurada difere da origem.\n%s\n' "$origem" >&2
  exit 1
fi
echo "Restauração conferida: contagens iguais às da origem."
