"""
认证模块
- AuthMiddleware 中间件
- 用户管理（加载、验证、获取当前用户）
- 应用配置获取（邮件配置、功能开关、规则）
- 所有数据直接从 SQLite (database.py) 读取，不再通过 HTTP 调用远程认证服务
"""

import time
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from merger import BUILTIN_RULE, BUILTIN_RULE_ID
import config
import state
import database


# ===================== 用户管理 =====================


def load_users_from_db() -> dict:
    """从数据库加载用户列表"""
    users = database.get_all_users()
    return {u["username"]: u for u in users}


def refresh_users():
    """刷新用户缓存"""
    state.USERS = load_users_from_db()


def verify_user_status(username: str) -> tuple:
    """校验用户是否仍启用，返回 (is_valid, reason)"""
    user = database.get_user(username)
    if not user:
        return False, "用户不存在"
    if not user.get("enabled", True):
        return False, "账号已被禁用"
    return True, None


# ===================== 配置获取 =====================


def fetch_app_config() -> dict:
    """从数据库获取应用配置"""
    return database.get_full_app_config()


def get_app_config() -> dict:
    """获取缓存的应用配置，超过 60 秒重新拉取"""
    now = time.time()
    if state.APP_CONFIG_CACHE and (now - state.APP_CONFIG_CACHE_TIME) < 60:
        return state.APP_CONFIG_CACHE
    cfg = fetch_app_config()
    state.APP_CONFIG_CACHE = cfg
    state.APP_CONFIG_CACHE_TIME = now
    return cfg


def get_mail_config() -> dict:
    return database.get_mail_config()


def get_features() -> dict:
    return database.get_features()


def get_remote_rules(username: str = "") -> list:
    """获取分配给用户的规则 + 内置规则"""
    return database.get_rules_for_user(username, BUILTIN_RULE)


def get_all_rules(username: str = "") -> list:
    """获取所有规则：内置规则 + 分配给该用户的规则"""
    return get_remote_rules(username)


def get_user_provinces(username: str = "") -> list:
    """获取用户分配的省份列表"""
    return database.get_user_provinces(username)


# ===================== 用户信息 =====================


def _restore_session_from_db(token: str) -> bool:
    """从 SQLite 恢复 session 到内存（服务器重启后自动恢复）"""
    db_session = database.get_session(token)
    if not db_session:
        return False
    username = db_session["username"]
    # 从数据库获取最新用户信息
    user = database.get_user(username)
    if not user or not user.get("enabled", True):
        database.delete_session(token)
        return False
    state.SESSIONS[token] = {
        "username": username,
        "name": user.get("name", username),
        "role": user.get("role", "user"),
        "features": dict(user.get("features", {})),
    }
    state.SESSION_LAST_CHECK[token] = 0
    # 确保 USERS 缓存中有该用户
    if username not in state.USERS:
        state.USERS[username] = user
    return True


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(config.SESSION_COOKIE)
    if not token:
        return None

    # 内存中有 session
    if token in state.SESSIONS:
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
        # 回退：使用 session 中存储的用户信息
        return {
            "username": username,
            "name": session.get("name", username),
            "role": session.get("role", "user"),
            "features": dict(session.get("features", {})),
        }

    # 内存中没有，尝试从 SQLite 恢复（服务器重启后）
    if _restore_session_from_db(token):
        session = state.SESSIONS[token]
        return {
            "username": session["username"],
            "name": session.get("name", session["username"]),
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
    """认证中间件 — 仅保护 /api/* 接口，SPA 页面由 Vue Router 处理认证"""

    # SPA 页面路径：服务器直接返回 index.html，Vue Router 在前端处理登录跳转
    SPA_PAGE_PATHS = {"/", "/login", "/mail", "/mail/results", "/admin", "/rules"}
    PUBLIC_API_PATHS = {"/api/login", "/favicon.ico", "/health"}
    PUBLIC_PREFIXES = ("/static", "/assets", "/docs", "/openapi.json", "/redoc")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # SPA 页面直接放行（pages.py 路由会处理重定向或返回 index.html）
        if path in self.SPA_PAGE_PATHS:
            return await call_next(request)

        # 公开 API 和静态资源
        if path in self.PUBLIC_API_PATHS or any(path.startswith(p) for p in self.PUBLIC_PREFIXES):
            return await call_next(request)

        # 已登录用户（内存命中或从 SQLite 恢复）
        token = request.cookies.get(config.SESSION_COOKIE)
        if token and token in state.SESSIONS:
            username = state.SESSIONS[token]["username"]
            request.state.username = username

            # 定期校验用户是否仍启用
            now = time.time()
            last_check = state.SESSION_LAST_CHECK.get(token, 0)
            if now - last_check > config.SESSION_STATUS_CHECK_INTERVAL:
                is_valid, reason = verify_user_status(username)
                if not is_valid:
                    del state.SESSIONS[token]
                    state.SESSION_LAST_CHECK.pop(token, None)
                    if path.startswith("/api/"):
                        return JSONResponse(
                            {"status": "error", "detail": reason or "账号已被禁用"},
                            status_code=403,
                        )
                    # SPA 页面：让 Vue 自己处理（跳转到登录页）
                    return await call_next(request)
                # 发送心跳（刷新设备绑定活跃时间）
                database.heartbeat(username)
                state.SESSION_LAST_CHECK[token] = now

            return await call_next(request)

        # 内存没有 session，尝试从 SQLite 恢复（服务器重启后自动恢复登录状态）
        if token:
            if _restore_session_from_db(token):
                username = state.SESSIONS[token]["username"]
                request.state.username = username
                # 恢复后走正常校验流程
                now = time.time()
                last_check = state.SESSION_LAST_CHECK.get(token, 0)
                if now - last_check > config.SESSION_STATUS_CHECK_INTERVAL:
                    is_valid, reason = verify_user_status(username)
                    if not is_valid:
                        del state.SESSIONS[token]
                        state.SESSION_LAST_CHECK.pop(token, None)
                        database.delete_session(token)
                        if path.startswith("/api/"):
                            return JSONResponse(
                                {"status": "error", "detail": reason or "账号已被禁用"},
                                status_code=403,
                            )
                        return await call_next(request)
                    database.heartbeat(username)
                    state.SESSION_LAST_CHECK[token] = now
                return await call_next(request)

        # 未登录：API 返回 401 JSON，其他路径交给 pages.py（返回 SPA）
        if path.startswith("/api/"):
            return JSONResponse({"status": "error", "detail": "未登录或会话已过期"}, status_code=401)

        # 非API路径未登录：让请求通过到 pages.py，Vue Router 会处理重定向到登录页
        return await call_next(request)
