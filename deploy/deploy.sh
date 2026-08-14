#!/bin/bash
set -e

echo "===== Excel 合并筛选系统 - 服务器部署 ====="

APP_DIR="/opt/excel-merger"
SERVICE_NAME="excel-merger"

# 1. 创建目录
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# 2. 复制项目文件
cp -r app.py templates requirements.txt $APP_DIR/
mkdir -p $APP_DIR/uploads $APP_DIR/output

# 3. 创建虚拟环境 & 安装依赖
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 安装 systemd 服务
sudo cp deploy/excel-merger.service /etc/systemd/system/$SERVICE_NAME.service
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

# 5. 检查状态
sleep 2
sudo systemctl status $SERVICE_NAME --no-pager

echo ""
echo "部署完成！"
echo "   服务地址: http://localhost:8000"
echo "   查看日志: sudo journalctl -u $SERVICE_NAME -f"
