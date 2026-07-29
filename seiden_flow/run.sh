#!/usr/bin/with-contenv bashio
set -e
exec gunicorn \
  --bind 0.0.0.0:8100 \
  --workers 1 \
  --threads 4 \
  --timeout 90 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --worker-tmp-dir /dev/shm \
  --access-logfile - \
  --error-logfile - \
  main:app
