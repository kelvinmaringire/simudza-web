#!/bin/sh
set -e

echo "Starting simudza..."

python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Single worker: the box is memory-tight and every worker is a separate process.
if [ "$DJANGO_ENV" = "production" ]; then
    echo "Running Uvicorn (production)..."
    exec uvicorn simudza.asgi:application --host 0.0.0.0 --port "${PORT:-8000}"
else
    echo "Running Uvicorn (development, autoreload)..."
    exec uvicorn simudza.asgi:application --host 0.0.0.0 --port "${PORT:-8000}" --reload
fi
