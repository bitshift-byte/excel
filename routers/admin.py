"""
管理后台代理路由
- 将 /api/admin/* 请求代理到远程认证服务的 /admin/*
- 使用管理员 session cookie（缓存 1 小时）
"""

import time
import httpx
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import config
import state
import auth

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_admin_session_cookie() -> Optional[str]:
    """获取认证服务的管理员 session cookie，带缓存（有效期 1 小时）。"""
    now = time.time()
    if state._admin_session_cookie and now < state._admin_session_expiry:
        return state._admin_session_cookie
    # 登录获取 admin session cookie
    try:
        resp = httpx.post(
            f"{config.AUTH_SERVICE_URL}/admin/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10,
        )
        if resp.status_code == 200:
            cookie = resp.cookies.get("lx_admin_session")
            if cookie:
                state._admin_session_cookie = cookie
                state._admin_session_expiry = now + 3600  # 缓存 1 小时
                return cookie
        print(f"[admin-proxy] 登录失败: {resp.status_code}")
    except Exception as e:
        print(f"[admin-proxy] 获取管理员 session 失败: {e}")
    return None


def _proxy_response(resp) -> JSONResponse:
    """将 httpx 响应转换为 FastAPI JSONResponse"""
    try:
        data = resp.json()
        return JSONResponse(data, status_code=resp.status_code)
    except Exception:
        return JSONResponse({"status": "error", "detail": resp.text}, status_code=resp.status_code)


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def admin_proxy(path: str, request: Request):
    auth.require_admin_user(request)

    cookie = _get_admin_session_cookie()
    if not cookie:
        return JSONResponse(
            {"status": "error", "detail": "无法连接管理后台"},
            status_code=503,
        )

    # 构建目标 URL
    url = f"{config.AUTH_SERVICE_URL}/admin/api/{path}"

    # 转发 headers
    fwd_headers = {
        "X-Service-Token": config.get_service_token(),
        "Cookie": f"lx_admin_session={cookie}",
    }
    if request.method in ("POST", "PUT"):
        fwd_headers["Content-Type"] = request.headers.get("content-type", "application/json")

    # 转发请求体
    body = await request.body() if request.method in ("POST", "PUT") else None

    # 转发 query params
    params = dict(request.query_params)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                request.method,
                url,
                headers=fwd_headers,
                params=params,
                content=body,
                timeout=30,
            )
    except httpx.ConnectError:
        return JSONResponse(
            {"status": "error", "detail": "认证服务不可用"},
            status_code=503,
        )
    except Exception as e:
        return JSONResponse(
            {"status": "error", "detail": f"代理请求失败: {e}"},
            status_code=502,
        )

    return _proxy_response(resp)
