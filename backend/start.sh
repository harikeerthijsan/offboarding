#!/usr/bin/env bash
set -e
python manage.py collectstatic --noinput
python manage.py migrate --noinput
# Load your existing data on the first deploy (no-op once the DB already has data).
python manage.py seed_initial_data
gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 3 --timeout 120
