#!/bin/sh
set -e

mkdir -p /app/data

if [ ! -f /app/data/mail_config.json ]; then
    echo '{"enabled": false}' > /app/data/mail_config.json
fi
if [ ! -f /app/data/processed_uids.json ]; then
    echo '[]' > /app/data/processed_uids.json
fi

exec uvicorn app:app --host 0.0.0.0 --port 8000
