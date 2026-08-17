"""
认证 / 会话相关路由
- 登录、登出、当前用户、同步状态、用户列表、规则列表
逻辑从原 app.py 中拆分而来，使用 config / state / auth 模块共享状态。
"""

import secrets
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import config
import state
import auth
import mail_reader

router = APIRouter()


@router.post("/api/login")
async def login_api(request: Request):
    """用户名 + 密码登录：调用认证服务校验"""
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    if not username or not password:
        return JSONResponse(
            {"status": "error", "detail": "用户名和密码不能为空"},
            status_code=400,
        )

    # 登录前先清除该用户的旧设备绑定（解决同一台电脑重复登录被拒的问题）
    # 这使得"最后登录者获胜"：新登录会替换旧会话，同时保持单设备在线
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{config.AUTH_SERVICE_URL}/logout",
                json={"username": username},
                headers={"X-Service-Token": config.get_service_token()},
                timeout=5,
            )
    except Exception:
        pass  # 如果清除失败，继续尝试登录

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{config.AUTH_SERVICE_URL}/login",
                json={
                    "username": username,
                    "password": password,
                    "device_id": config.get_device_id(),
                },
                timeout=15,
            )
    except httpx.ConnectError:
        return JSONResponse(
            {"status": "error", "detail": "认证服务不可用"},
            status_code=503,
        )

    data = resp.json()
    if resp.status_code != 200 or data.get("status") != "success":
        return JSONResponse(content=data, status_code=resp.status_code)

    user_info = data["user"]

    # 刷新用户表
    state.USERS = auth.load_users_from_auth_service()

    # 将用户信息存入 session
    token = secrets.token_hex(16)
    state.SESSIONS[token] = {
        "username": user_info["username"],
        "name": user_info.get("name", user_info["username"]),
        "role": user_info.get("role", "user"),
        "features": dict(user_info.get("features", {})),
    }

    resp = JSONResponse(
        {
            "status": "success",
            "user": {
                "username": user_info["username"],
                "name": user_info["name"],
                "role": user_info["role"],
                "features": user_info.get("features", {}),
            },
        }
    )
    resp.set_cookie(
        config.SESSION_COOKIE,
        token,
        max_age=config.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@router.post("/api/logout")
async def logout_api(request: Request):
    token = request.cookies.get(config.SESSION_COOKIE)
    if token and token in state.SESSIONS:
        username = state.SESSIONS[token]["username"]
        # 通知认证服务清除设备绑定
        try:
            httpx.post(
                f"{config.AUTH_SERVICE_URL}/logout",
                json={"username": username},
                headers={"X-Service-Token": config.get_service_token()},
                timeout=5,
            )
        except Exception:
            pass
        del state.SESSIONS[token]
    state.SESSION_LAST_CHECK.pop(token, None)
    resp = JSONResponse({"status": "success"})
    resp.delete_cookie(config.SESSION_COOKIE)
    return resp


@router.get("/api/me")
async def get_me(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(
            {"status": "error", "detail": "未登录"},
            status_code=401,
        )
    return JSONResponse(
        {
            "status": "success",
            "user": {
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "features": user.get("features", {}),
            },
        }
    )


@router.get("/api/sync")
async def sync_status(request: Request):
    """前端每 5 秒轮调：返回用户状态 + 功能开关 + 邮件配置 + 邮件运行状态。
    如果用户已被禁用或踢下线，返回 401 让前端跳转登录。"""
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(
            {"status": "error", "detail": "未登录"},
            status_code=401,
        )
    # 强制刷新 USERS 缓存，确保拿到最新的用户信息
    cfg = auth.get_mail_config()
    safe_cfg = {k: v for k, v in cfg.items() if k != "auth_code"} if cfg else {}
    # 按用户隔离省份
    username = user["username"]
    user_provinces = auth.get_user_provinces(username)
    if user_provinces:
        safe_cfg["provinces"] = user_provinces
    elif "provinces" not in safe_cfg:
        safe_cfg["provinces"] = []
    return JSONResponse(
        {
            "status": "success",
            "user": {
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "features": user.get("features", {}),
            },
            "mail_config": safe_cfg,
            "mail_running": mail_reader.is_running(),
        }
    )


@router.get("/api/users")
async def list_users(request: Request):
    """仅管理员可查看用户列表"""
    auth.require_admin_user(request)
    users = [
        {
            "username": u.get("username", ""),
            "name": u.get("name", ""),
            "role": u.get("role", "user"),
        }
        for u in state.USERS.values()
    ]
    return JSONResponse(content={"status": "success", "users": users})


@router.get("/api/rules")
async def list_rules(request: Request):
    user = auth.get_current_user(request)
    username = user.get("username", "") if user else ""
    return JSONResponse(content={"status": "success", "rules": auth.get_all_rules(username)})
