#!/usr/bin/env sh
set -eu
port="$(sed -n 's/^PUBLIC_PORT=//p' .env)"
base="http://localhost:${port:-8080}"

# The HTTP stack can be healthy while Celery is down, leaving jobs pending.
worker_id="$(docker compose ps -q dsp-worker)"
if [ -z "$worker_id" ]; then
  docker compose logs --tail 100 dsp-worker
  echo "DSP worker container does not exist. Rebuild with: docker compose up -d --build dsp-worker" >&2
  exit 1
fi
worker_state="$(docker inspect --format '{{.State.Status}}' "$worker_id")"
if [ "$worker_state" != "running" ]; then
  docker compose logs --tail 100 dsp-worker
  echo "DSP worker is not running (state: $worker_state)." >&2
  exit 1
fi
if ! docker compose exec -T dsp-worker \
  celery -A services.workers.dsp_worker.worker.celery_app inspect ping \
  --destination celery@dsp-worker --timeout 10 >/dev/null; then
  docker compose logs --tail 100 dsp-worker
  echo "DSP worker did not answer Celery ping." >&2
  exit 1
fi

i=0
while [ "$i" -lt 30 ]; do
  if curl -fsS "$base/healthz" >/dev/null && curl -fsS "$base/api/health" | grep -q '"status"'; then
    echo "Smoke test passed: $base"
    exit 0
  fi
  i=$((i + 1))
  sleep 2
done
docker compose ps
docker compose logs --tail 100 gateway
echo "Smoke test failed after 60 seconds." >&2
exit 1
