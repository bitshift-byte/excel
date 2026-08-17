"""
共享可变状态模块
- session 存储
- 用户缓存
- 应用配置缓存
"""

import time
from typing import Dict

# session token → {username} 映射（内存存储，重启失效）
SESSIONS: Dict[str, dict] = {}

# session → 上次校验用户状态的时间戳
SESSION_LAST_CHECK: Dict[str, float] = {}

# 用户列表缓存（从认证服务加载）
USERS: dict = {}

# 应用配置缓存（从认证服务获取）
APP_CONFIG_CACHE: dict = {}
APP_CONFIG_CACHE_TIME: float = 0.0

# 管理员 session cookie 缓存（用于 admin proxy）
_admin_session_cookie: str | None = None
_admin_session_expiry: float = 0
