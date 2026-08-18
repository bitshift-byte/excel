"""
管理后台路由
- 直接调用 database.py，不再通过 HTTP 代理到远程认证服务
- 所有 /api/admin/* 路由在此实现
"""

import json
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse

import config
import state
import auth
import database

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ===================== 中间件/依赖 =====================


def require_admin(request: Request) -> dict:
    """要求当前用户是管理员"""
    user = auth.get_current_user(request)
    if not user:
        raise _json_error("未登录或会话已过期", 401)
    if user["role"] != "admin":
        raise _json_error("仅管理员可操作", 403)
    return user


class AdminError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def _json_error(detail: str, status: int):
    return AdminError(status, detail)


# Note: AdminError is caught by the app-level exception handler registered in app.py


# ===================== 用户管理 =====================


@router.get("/users")
async def admin_list_users(request: Request):
    require_admin(request)
    users = database.get_all_users()
    return JSONResponse({"status": "success", "users": users})


@router.post("/users")
async def admin_add_user(request: Request):
    require_admin(request)
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    name = body.get("name", username).strip()
    role = body.get("role", "user").strip()
    enabled = body.get("enabled", True)

    if not username or not password:
        raise AdminError(400, "用户名和密码不能为空")
    if role not in ("admin", "user"):
        raise AdminError(400, "角色只能是 admin 或 user")

    if database.get_user(username):
        raise AdminError(409, "用户名已存在")

    features = body.get("features", {})
    user = database.create_user(username, password, name, role, enabled, features)
    auth.refresh_users()
    return JSONResponse({"status": "success", "user": user}, status_code=201)


@router.put("/users/{username}")
async def admin_edit_user(username: str, request: Request):
    require_admin(request)
    body = await request.json()
    name = body.get("name")
    role = body.get("role")
    enabled = body.get("enabled")
    features = body.get("features")

    # 不允许禁用最后一个管理员
    if enabled is False and role != "user":
        existing = database.get_user(username)
        if existing and existing.get("role") == "admin":
            if database.count_admins() <= 1:
                raise AdminError(400, "至少保留一个启用的管理员账号")

    # 不允许降级最后一个管理员
    if role == "user":
        existing = database.get_user(username)
        if existing and existing.get("role") == "admin":
            if database.count_admins() <= 1:
                raise AdminError(400, "至少保留一个管理员账号")

    user = database.update_user(username, name=name, role=role, enabled=enabled, features=features)
    if not user:
        raise AdminError(404, "用户不存在")
    auth.refresh_users()
    return JSONResponse({"status": "success", "user": user})


@router.put("/users/{username}/password")
async def admin_reset_password(username: str, request: Request):
    require_admin(request)
    body = await request.json()
    new_password = body.get("password", "").strip()
    if not new_password:
        raise AdminError(400, "密码不能为空")
    if not database.update_user_password(username, new_password):
        raise AdminError(404, "用户不存在")
    return JSONResponse({"status": "success"})


@router.delete("/users/{username}")
async def admin_delete_user(username: str, request: Request):
    admin = require_admin(request)
    if username == admin["username"]:
        raise AdminError(400, "不能删除自己")

    existing = database.get_user(username)
    if not existing:
        raise AdminError(404, "用户不存在")

    if existing.get("role") == "admin" and database.count_admins() <= 1:
        raise AdminError(400, "至少保留一个管理员账号")

    database.delete_user(username)
    auth.refresh_users()
    return JSONResponse({"status": "success"})


# ===================== 设备管理 =====================


@router.post("/users/{username}/unbind-device")
async def admin_unbind_device(username: str, request: Request):
    require_admin(request)
    database.unbind_device(username)
    return JSONResponse({"status": "success"})


@router.get("/users/{username}/device-status")
async def admin_device_status(username: str, request: Request):
    require_admin(request)
    status = database.get_device_status(username)
    return JSONResponse({"status": "success", **status})


# ===================== 应用配置 =====================


@router.get("/app-config")
async def admin_get_app_config(request: Request):
    require_admin(request)
    cfg = database.get_full_app_config()
    return JSONResponse({"status": "success", "config": cfg})


@router.put("/mail-config")
async def admin_update_mail_config(request: Request):
    require_admin(request)
    body = await request.json()
    cfg = database.set_mail_config(body)
    # 重启邮件后台
    _restart_mail_if_needed(cfg)
    return JSONResponse({"status": "success", "config": cfg})


@router.get("/features")
async def admin_get_features(request: Request):
    require_admin(request)
    features = database.get_features()
    return JSONResponse({"status": "success", "features": features})


@router.put("/features")
async def admin_update_features(request: Request):
    require_admin(request)
    body = await request.json()
    features = database.set_features(body)
    return JSONResponse({"status": "success", "features": features})


# ===================== 用户功能权限 =====================


@router.get("/users/{username}/features")
async def admin_get_user_features(username: str, request: Request):
    require_admin(request)
    if not database.get_user(username):
        raise AdminError(404, "用户不存在")
    features = database.get_user_features(username)
    return JSONResponse({"status": "success", "features": features})


@router.put("/users/{username}/features")
async def admin_update_user_features(username: str, request: Request):
    require_admin(request)
    body = await request.json()
    result = database.set_user_features(username, body)
    if not result:
        raise AdminError(404, "用户不存在")
    auth.refresh_users()
    return JSONResponse({"status": "success", "features": result.get("features", {})})


# ===================== 用户规则分配 =====================


@router.get("/users/{username}/rules")
async def admin_get_user_rules(username: str, request: Request):
    require_admin(request)
    rule_ids = database.get_user_rule_ids(username)
    return JSONResponse({"status": "success", "rule_ids": rule_ids})


@router.put("/users/{username}/rules")
async def admin_assign_user_rules(username: str, request: Request):
    require_admin(request)
    if not database.get_user(username):
        raise AdminError(404, "用户不存在")
    body = await request.json()
    rule_ids = body.get("rule_ids", [])
    database.set_user_rules(username, rule_ids)
    return JSONResponse({"status": "success", "rule_ids": rule_ids})


# ===================== 用户省份分配 =====================


@router.get("/users/{username}/provinces")
async def admin_get_user_provinces(username: str, request: Request):
    require_admin(request)
    provinces = database.get_user_provinces(username)
    return JSONResponse({"status": "success", "provinces": provinces})


@router.put("/users/{username}/provinces")
async def admin_assign_user_provinces(username: str, request: Request):
    require_admin(request)
    if not database.get_user(username):
        raise AdminError(404, "用户不存在")
    body = await request.json()
    provinces = body.get("provinces", [])
    database.set_user_provinces(username, provinces)
    return JSONResponse({"status": "success", "provinces": provinces})


# ===================== 规则管理 =====================


@router.get("/rules")
async def admin_list_rules(request: Request):
    require_admin(request)
    rules = database.get_all_rules()
    return JSONResponse({"status": "success", "rules": rules})


@router.post("/rules")
async def admin_create_rule(request: Request):
    require_admin(request)
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise AdminError(400, "规则名称不能为空")
    standard_headers = body.get("standard_headers", [])
    if not standard_headers:
        raise AdminError(400, "请至少添加一个标准表头")
    rule = database.create_rule(name, standard_headers)
    return JSONResponse({"status": "success", "rule": rule}, status_code=201)


@router.put("/rules/{rule_id}")
async def admin_update_rule(rule_id: str, request: Request):
    require_admin(request)
    if rule_id == "_builtin_default":
        raise AdminError(400, "内置规则不可编辑")
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise AdminError(400, "规则名称不能为空")
    standard_headers = body.get("standard_headers", [])
    rule = database.update_rule(rule_id, name, standard_headers)
    if not rule:
        raise AdminError(404, "规则不存在")
    return JSONResponse({"status": "success", "rule": rule})


@router.delete("/rules/{rule_id}")
async def admin_delete_rule(rule_id: str, request: Request):
    require_admin(request)
    if rule_id == "_builtin_default":
        raise AdminError(400, "内置规则不可删除")
    if not database.delete_rule(rule_id):
        raise AdminError(404, "规则不存在")
    return JSONResponse({"status": "success"})


# ===================== 辅助函数 =====================


def _restart_mail_if_needed(mail_cfg: dict):
    """如果邮件配置已启用，重启邮件后台"""
    import config as _config
    mail_reader.stop_background()
    if mail_cfg.get("enabled"):
        mail_cfg["output_dir"] = _config.OUTPUT_DIR
        mail_cfg["processed_uids_file"] = None
        mail_reader.start_background(mail_cfg)
        # 更新缓存
    state.APP_CONFIG_CACHE = database.get_full_app_config()
    import time as _time
    state.APP_CONFIG_CACHE_TIME = _time.time()
