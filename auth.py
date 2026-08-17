"""
认证模块
- AuthMiddleware 中间件
- 用户管理（加载、验证、获取当前用户）
- 应用配置获取（邮件配置、功能开关、规则）
"""

import os
import time
import httpx
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from merger import BUILTIN_RULE, BUILTIN_RULE_ID
import config
import state


# ===================== 用户管理 =====================


def load_users_from_auth_service() -> dict:
    """从远程认证服务加载用户列表"""
    try:
        resp = httpx.post(
            f"{config.AUTH_SERVICE_URL}/users",
            headers={"X-Service-Token": config.get_service_token()},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {u["username"]: u for u in data.get("users", [])}
    except Exception as e:
        print(f"[auth] 无法连接认证服务 ({config.AUTH_SERVICE_URL}): {e}")
    return {}


def refresh_users():
    """刷新用户缓存"""
    state.USERS = load_users_from_auth_service()


def verify_user_status_with_auth_service(username: str) -> tuple:
    """向认证服务校验用户是否仍启用，返回 (is_valid, reason)"""
    try:
        resp = httpx.post(
            f"{config.AUTH_SERVICE_URL}/verify-user",
            json={"username": username},
            headers={"X-Service-Token": config.get_service_token()},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("enabled", True):
                return True, None
            return False, data.get("reason", "账号已被禁用")
        return False, "认证服务不可用"
    except Exception:
        # 认证服务不可用时，不阻断已有 session
        return True, None


# ===================== 配置获取 =====================


def fetch_app_config_from_auth_service() -> dict:
    """从认证服务获取应用配置"""
    try:
        resp = httpx.post(
            f"{config.AUTH_SERVICE_URL}/app-config",
            headers={"X-Service-Token": config.get_service_token()},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[auth] 获取应用配置失败: {e}")
    return {}


def get_app_config() -> dict:
    """获取缓存的应用配置，超过 60 秒重新拉取"""
    now = time.time()
    if state.APP_CONFIG_CACHE and (now - state.APP_CONFIG_CACHE_TIME) < 60:
        return state.APP_CONFIG_CACHE
    # 重新拉取
    cfg = fetch_app_config_from_auth_service()
    state.APP_CONFIG_CACHE = cfg
    state.APP_CONFIG_CACHE_TIME = now
    return cfg


def get_mail_config() -> dict:
    """获取邮件配置"""
    return get_app_config().get("mail_config", {})


def get_features() -> dict:
    return get_app_config().get("features", {})


def get_remote_rules(username: str = "") -> list:
    """从认证服务获取规则列表（按用户隔离）"""
    try:
        resp = httpx.post(
            f"{config.AUTH_SERVICE_URL}/rules",
            json={"username": username},
            headers={"X-Service-Token": config.get_service_token()},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("rules", [])
    except Exception as e:
        print(f"[auth] 获取规则失败: {e}")
    return []


def get_all_rules(username: str = "") -> list:
    """获取所有规则：内置规则 + 分配给该用户的远程规则"""
    remote = get_remote_rules(username)
    has_builtin = any(r.get("id") == "_builtin_default" or r.get("builtin") for r in remote)
    if has_builtin:
        return remote
    return [BUILTIN_RULE] + remote



def get_user_provinces(username: str = "") -> list:
    """从认证服务获取用户分配的省份列表（按用户隔离）"""
    try:
        resp = httpx.post(
            f"{config.AUTH_SERVICE_URL}/user-config",
            json={"username": username},
            headers={"X-Service-Token": config.get_service_token()},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("provinces", [])
    except Exception as e:
        print(f"[auth] 获取用户省份失败: {e}")
    return []

# ===================== 用户信息 =====================


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(config.SESSION_COOKIE)
    if token and token in state.SESSIONS:
        session = state.SESSIONS[token]
        username = session["username"]
        # 优先从 USERS 缓存获取最新信息，回退到 session 中存储的信息
        user_info = state.USERS.get(username)
        if user_info:
            return {
                "username": username,
                "name": user_info.get("name", username),
                "role": user_info.get("role", "user"),
                "features": dict(user_info.get("features", {})),
            }
        # 回退：使用 session 中存储的用户信息（认证服务不可达时）
        return {
            "username": username,
            "name": session.get("name", username),
            "role": session.get("role", "user"),
            "features": dict(session.get("features", {})),
        }
    return None


def require_admin_user(request: Request) -> dict:
    """要求当前用户是管理员，否则抛出 403"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    return user


# ===================== 认证中间件 =====================


class AuthMiddleware(BaseHTTPMiddleware):
    """拦截需要认证的路由，未登录重定向到 /login"""

    PUBLIC_PATHS = {"/login", "/api/login", "/favicon.ico"}
    PUBLIC_PREFIXES = ("/static", "/assets")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in self.PUBLIC_PATHS or any(path.startswith(p) for p in self.PUBLIC_PREFIXES):
            return await call_next(request)

        token = request.cookies.get(config.SESSION_COOKIE)
        if token and token in state.SESSIONS:
            username = state.SESSIONS[token]["username"]
            request.state.username = username

            # 定期向认证服务校验用户是否仍启用
            now = time.time()
            last_check = state.SESSION_LAST_CHECK.get(token, 0)
            if now - last_check > config.SESSION_STATUS_CHECK_INTERVAL:
                is_valid, reason = verify_user_status_with_auth_service(username)
                if not is_valid:
                    del state.SESSIONS[token]
                    state.SESSION_LAST_CHECK.pop(token, None)
                    if path.startswith("/api/"):
                        return JSONResponse(
                            {"status": "error", "detail": reason or "账号已被禁用"},
                            status_code=403,
                        )
                    return RedirectResponse("/login", status_code=302)
                # 发送心跳
                try:
                    httpx.post(
                        f"{config.AUTH_SERVICE_URL}/heartbeat",
                        json={"username": username, "device_id": config.get_device_id()},
                        headers={"X-Service-Token": config.get_service_token()},
                        timeout=5,
                    )
                except Exception:
                    pass
                state.SESSION_LAST_CHECK[token] = now

            return await call_next(request)

        if path.startswith("/api/"):
            return JSONResponse({"status": "error", "detail": "未登录或会话已过期"}, status_code=401)

        return RedirectResponse("/login", status_code=302)
