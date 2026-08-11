#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  cp .env.example .env
  postgres_secret="$(openssl rand -hex 32)"
  minio_secret="$(openssl rand -hex 32)"
  jwt_secret="$(openssl rand -hex 32)"
  service_secret="$(openssl rand -hex 32)"
  sed -i.bak \
    -e "s/change-me-postgres/$postgres_secret/" \
    -e "s/change-me-minio/$minio_secret/" \
    -e "s/change-me-use-at-least-32-random-characters/$jwt_secret/" \
    -e "s/change-me-use-another-random-secret/$service_secret/" .env
  rm -f .env.bak
  echo "Created .env with random local secrets."
fi
docker compose config --quiet
echo "Configuration is valid."
