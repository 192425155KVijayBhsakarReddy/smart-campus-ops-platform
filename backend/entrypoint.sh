#!/bin/sh
set -e

echo "Waiting for PostgreSQL database at ${DB_HOST}:${DB_PORT}..."
while ! nc -z ${DB_HOST} ${DB_PORT}; do
  sleep 0.5
done
echo "PostgreSQL database is available!"

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Seeding initial campus rooms and sample data..."
python seed_data.py

echo "Starting Gunicorn WSGI server..."
exec gunicorn campus_project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --access-logfile - \
    --error-logfile -
