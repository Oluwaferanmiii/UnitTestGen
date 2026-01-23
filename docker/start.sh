#!/bin/sh
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static..."
python manage.py collectstatic --noinput || true

echo "Starting gunicorn..."
gunicorn ai_test_generator.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --timeout 180