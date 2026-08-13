#!/usr/bin/env sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo_root"
./scripts/setup.sh
./scripts/docker-preflight.sh
if [ "${SOUNDDEBUG_OFFLINE:-0}" = "1" ]; then
  docker compose build --pull=false "$@"
else
  docker compose build --pull "$@"
fi
docker compose up -d --force-recreate
./scripts/smoke-test.sh

migration_id="$(docker compose ps -a -q db-migrate)"
[ -n "$migration_id" ] || { echo "db-migrate container was not created" >&2; exit 1; }
[ "$(docker inspect --format '{{.State.ExitCode}}' "$migration_id")" = "0" ] || {
  docker compose logs --tail 200 db-migrate
  echo "Database migration failed. Preserve the .env associated with the existing postgres_data volume." >&2
  exit 1
}

docker compose run --rm --no-deps \
  -v "$repo_root/tests:/verification/tests:ro" \
  dsp-worker python -m unittest discover -s /verification/tests -p 'test_*.py' -v
docker compose run --rm --no-deps \
  -e PYTHONPATH=/app \
  -v "$repo_root/experiments:/verification/experiments:ro" \
  dsp-worker python /verification/experiments/run_p1_temporal_synthetic.py
docker compose run --rm --no-deps \
  -e SOUNDDEBUG_API_URL=http://gateway:8000 \
  -v "$repo_root/tests:/verification/tests:ro" \
  dsp-worker python /verification/tests/test_api.py
echo "P1 Docker build, services, migration, unit tests, synthetic checks and public API E2E passed."
