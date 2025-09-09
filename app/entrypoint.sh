#!/usr/bin/env sh
set -e

DB_HOST=${MYSQL_HOST:-db}
DB_PORT=${MYSQL_PORT:-3306}

WAIT_COMMAND="import socket,sys;s=socket.socket();s.settimeout(2);sys.exit(0) if s.connect_ex(('$DB_HOST', int('$DB_PORT'))) == 0 else sys.exit(1)"

echo "Waiting for database to be ready at $DB_HOST:$DB_PORT..."
while ! python -c "$WAIT_COMMAND"; do
  echo "Database is unavailable. Sleeping for 1s"
  sleep 1
done
echo "Database is up. Continuing..."

cd /app

echo "Applying database migrations..."
alembic upgrade head

echo "Starting MotoTwist..."
exec "$@"