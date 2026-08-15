#!/bin/sh
set -e

# 挂载不存在的文件路径时 Docker 会创建目录，这里兜底：目录或缺失都重建为文件
if [ ! -f /app/mail_config.json ]; then
    rm -rf /app/mail_config.json
    echo '{"enabled": false}' > /app/mail_config.json
fi
if [ ! -f /app/processed_uids.json ]; then
    rm -rf /app/processed_uids.json
    echo '[]' > /app/processed_uids.json
fi

exec uvicorn app:app --host 0.0.0.0 --port 8000
