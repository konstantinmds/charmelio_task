#!/bin/bash
set -e

# Only run migrations for the API service (not for worker)
if [[ "$1" == "uvicorn" ]]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

echo "Starting application..."
exec "$@"
