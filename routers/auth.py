"""
认证 / 会话相关路由
- 登录、登出、当前用户、同步状态、用户列表、规则列表
- 直接调用 database.py，不再通过 HTTP 调用远程认证服务
"""

import secrets
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import config
import state
import auth
import database
import mail_reader

router = APIRouter()


@router.post("/api/login")
async def login_api(request: Request):
    """用户名 + 密码登录"""
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    if not username or not password:
        return JSONResponse(
            {"status": "error", "detail": "用户名和密码不能为空"},
            status_code=400,
        )

    # 获取用户
    user = database.get_user(username)
    if not user or not database.verify_password(user, password):
        return JSONResponse(
            {"status": "error", "detail": "用户名或密码错误"},
            status_code=401,
        )

    if not user.get("enabled", True):
        return JSONResponse(
            {"status": "error", "detail": "该账号已被禁用"},
            status_code=403,
        )

    # 单设备登录检查
    device_id = body.get("device_id", "").strip()
    # 网页版：前端传浏览器指纹作为 device_id
    browser_fp = body.get("browser_fingerprint", "").strip()
    effective_device_id = browser_fp or device_id

    allow, reason = database.check_device_login(username, effective_device_id)
    if not allow:
        return JSONResponse(
            {"status": "error", "detail": reason},
            status_code=409,
        )

    # 创建 session
    token = secrets.token_hex(16)
    state.SESSIONS[token] = {
        "username": user["username"],
        "name": user.get("name", user["username"]),
        "role": user.get("role", "user"),
        "features": dict(user.get("features", {})),
    }

    # 设置活跃登录
    database.set_active_login(username, token, effective_device_id)

    # 刷新用户缓存
    auth.refresh_users()

    resp = JSONResponse(
        {
            "status": "success",
            "user": {
                "username": user["username"],
                "name": user.get("name", user["username"]),
                "role": user.get("role", "user"),
                "features": user.get("features", {}),
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
        database.clear_active_login(username)
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
    """前端每 5 秒轮调：返回用户状态 + 功能开关 + 邮件配置 + 邮件运行状态。"""
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(
            {"status": "error", "detail": "未登录"},
            status_code=401,
        )
    # 获取最新用户信息
    db_user = database.get_user(user["username"])
    if not db_user or not db_user.get("enabled", True):
        # 用户已被禁用或删除
        token = request.cookies.get(config.SESSION_COOKIE)
        if token and token in state.SESSIONS:
            del state.SESSIONS[token]
        return JSONResponse(
            {"status": "error", "detail": "账号已被禁用"},
            status_code=401,
        )

    # 获取邮件配置（隐藏 auth_code）
    mail_cfg = database.get_mail_config()
    safe_cfg = {k: v for k, v in mail_cfg.items() if k != "auth_code"} if mail_cfg else {}

    # 按用户隔离省份
    username = user["username"]
    user_provinces = database.get_user_provinces(username)

    # 获取用户规则
    rules = auth.get_all_rules(username)

    return JSONResponse({
        "status": "success",
        "user": {
            "username": db_user["username"],
            "name": db_user.get("name", db_user["username"]),
            "role": db_user.get("role", "user"),
            "features": db_user.get("features", {}),
        },
        "features": db_user.get("features", {}),
        "mail_config": safe_cfg,
        "mail_running": mail_reader.is_running(),
        "user_provinces": user_provinces,
        "rules": rules,
    })


@router.get("/api/rules")
async def get_rules(request: Request):
    """获取当前用户的规则列表"""
    user = auth.get_current_user(request)
    username = user.get("username", "") if user else ""
    rules = auth.get_all_rules(username)
    return JSONResponse({"status": "success", "rules": rules})


@router.get("/api/features")
async def get_features(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse({"status": "error", "detail": "未登录"}, status_code=401)
    return JSONResponse(
        content={"status": "success", "features": user.get("features", {})}
    )
