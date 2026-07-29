#!/usr/bin/with-contenv bashio
set -e
exec gunicorn --bind 0.0.0.0:8100 --workers 1 --threads 8 --timeout 120 --access-logfile - --error-logfile - main:app
