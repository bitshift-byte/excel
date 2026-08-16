#!/bin/bash
# 认证服务部署脚本
# 在服务器上执行：bash deploy.sh
# 或在本地执行（需要 SSH 访问）：ssh user@server "cd /path/to/project && bash deploy/deploy.sh"

set -e

echo "=== LX 认证服务部署 ==="

# 确保在项目根目录
cd "$(dirname "$0")/.."
echo "工作目录: $(pwd)"

# 拉取最新代码
echo ">>> 拉取最新代码..."
git pull origin main

# 确保 data/updates 目录存在
mkdir -p data/updates

# 重建并重启 Docker 容器
echo ">>> 重建 Docker 容器..."
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 等待服务启动
echo ">>> 等待服务启动..."
sleep 3

# 验证
echo ">>> 验证服务..."
HEALTH=$(curl -s http://localhost:8001/health 2>/dev/null || echo "FAILED")
echo "Health: $HEALTH"

UPDATE_CHECK=$(curl -s -H "X-Service-Token: lx-internal-service-token" http://localhost:8001/update/check?platform=windows 2>/dev/null || echo "FAILED")
echo "Update check: $UPDATE_CHECK"

HEARTBEAT=$(curl -s -X POST -H "X-Service-Token: lx-internal-service-token" -H "Content-Type: application/json" -d '{"username":"test"}' http://localhost:8001/heartbeat 2>/dev/null || echo "FAILED")
echo "Heartbeat: $HEARTBEAT"

echo ""
echo "=== 部署完成 ==="
echo "管理后台: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'server-ip'):8001/admin"
