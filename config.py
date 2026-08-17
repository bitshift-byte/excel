"""
配置常量模块
- 认证服务地址、服务间密钥、设备ID
- 目录路径
- Session 常量
- Vue 前端配置
"""

import os
import sys
import uuid as _uuid

from merger import _base_dir, _resource_path

# ===================== 路径配置 =====================

DATA_DIR = os.path.join(_base_dir(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

MAIL_CONFIG_FILE = os.path.join(DATA_DIR, "mail_config.json")  # 保留用于向后兼容

UPLOAD_DIR = os.path.join(_base_dir(), "uploads")
OUTPUT_DIR = os.path.join(_base_dir(), "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===================== Vue 前端构建产物 =====================

VUE_DIST_DIR = os.path.join(_base_dir(), "dist_vue")
USE_VUE_FRONTEND = os.path.isdir(VUE_DIST_DIR)


def serve_vue_index() -> str:
    """返回 Vue SPA 的 index.html"""
    index_path = os.path.join(VUE_DIST_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


# ===================== 认证服务配置 =====================


def load_auth_service_url() -> str:
    """
    读取认证服务地址。
    优先级：环境变量 > data/auth_service_url.txt > 默认值
    桌面应用通过编辑 data/auth_service_url.txt 配置服务器地址。
    """
    # 1. 环境变量
    url = os.environ.get("AUTH_SERVICE_URL")
    if url:
        return url.rstrip("/")
    # 2. 配置文件
    url_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "auth_service_url.txt")
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            appdata = os.environ.get("APPDATA")
            base = os.path.join(appdata, "ExcelMerger") if appdata else os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(sys.executable)
        url_file = os.path.join(base, "data", "auth_service_url.txt")
    try:
        if os.path.exists(url_file):
            with open(url_file, "r", encoding="utf-8") as f:
                url = f.read().strip()
                if url:
                    return url.rstrip("/")
    except Exception:
        pass
    # 3. 默认值
    return "http://18.177.82.156:8001"


AUTH_SERVICE_URL = load_auth_service_url()


def get_service_token() -> str:
    """获取服务间通信密钥"""
    return os.environ.get("SERVICE_TOKEN", "lx-internal-service-token")


def get_device_id() -> str:
    """获取本机唯一设备标识（持久化存储在 data 目录）。
    首次调用时生成 UUID 并写入文件，后续读取同一值。"""
    device_file = os.path.join(DATA_DIR, "device_id.txt")
    try:
        if os.path.exists(device_file):
            with open(device_file, "r", encoding="utf-8") as f:
                did = f.read().strip()
                if did:
                    return did
    except Exception:
        pass
    # 生成新的设备 ID
    did = _uuid.uuid4().hex
    try:
        with open(device_file, "w", encoding="utf-8") as f:
            f.write(did)
    except Exception:
        pass
    return did


# ===================== Session 常量 =====================

SESSION_COOKIE = "nebula_session"
SESSION_MAX_AGE = 86400  # 24h
SESSION_STATUS_CHECK_INTERVAL = 5  # 5 秒
