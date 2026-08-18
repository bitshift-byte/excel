"""
配置常量模块
- 数据目录、服务间密钥
- Session 常量
- Vue 前端配置
"""

import os
import uuid as _uuid

# ===================== 路径配置 =====================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===================== Vue 前端构建产物 =====================

VUE_DIST_DIR = os.path.join(BASE_DIR, "dist_vue")
USE_VUE_FRONTEND = os.path.isdir(VUE_DIST_DIR)


def serve_vue_index() -> str:
    """返回 Vue SPA 的 index.html"""
    index_path = os.path.join(VUE_DIST_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


# ===================== 服务间密钥 =====================


def get_service_token() -> str:
    """获取服务间通信密钥"""
    return os.environ.get("SERVICE_TOKEN", "lx-internal-service-token")


def get_device_id() -> str:
    """获取本机唯一设备标识（网页版改用浏览器指纹，此处保留兼容）。
    前端会传入浏览器指纹作为 device_id。"""
    return os.environ.get("DEVICE_ID", "")


# ===================== Session 常量 =====================

SESSION_COOKIE = "nebula_session"
SESSION_MAX_AGE = 86400  # 24h
SESSION_STATUS_CHECK_INTERVAL = 5  # 5 秒
