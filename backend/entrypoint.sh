#!/usr/bin/env bash
set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL database to be reachable..."
DB_HOST=${POSTGRES_HOST:-db}
DB_PORT=${POSTGRES_PORT:-5432}
DB_USER=${POSTGRES_USER:-jate_admin}
DB_NAME=${POSTGRES_DB:-jate_db}

until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"; do
  echo "Postgres is unavailable - sleeping 2s"
  sleep 2
done

echo "PostgreSQL is up and accepting connections."

# Ensure storage directory exists
mkdir -p /app/storage/pdfs

# Execute container command
exec "$@"
