"""
独立认证微服务（部署在服务器上）

功能：
- POST /login           用户登录（供主应用调用）
- GET  /users           用户列表（供主应用查询）
- GET  /health          健康检查
- GET  /admin           管理后台入口
- GET  /admin/login     管理员登录页
- GET  /admin/dashboard 管理面板页
- POST /admin/login     管理员登录
- POST /admin/logout    管理员退出
- GET  /admin/api/me    当前管理员信息
- GET  /admin/api/users 用户管理列表
- POST /admin/api/users 新增用户
- PUT  /admin/api/users/{username}        编辑用户
- PUT  /admin/api/users/{username}/password 重置密码
- DELETE /admin/api/users/{username}       删除用户

配置文件: data/auth_config.json
"""
import os
import sys
import json
import time
import hashlib
import secrets
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles


# ===================== 路径工具 =====================

def _base_dir() -> str:
    """可写数据目录"""
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            appdata = os.environ.get("APPDATA")
            base = os.path.join(appdata, "ExcelMerger") if appdata else os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(sys.executable)
        os.makedirs(base, exist_ok=True)
        return base
    return os.path.dirname(os.path.abspath(__file__))


def _resource_path(relative: str) -> str:
    """打包后资源路径（PyInstaller _MEIPASS）"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


DATA_DIR = os.path.join(_base_dir(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

AUTH_CONFIG_FILE = os.environ.get("AUTH_CONFIG_PATH", os.path.join(DATA_DIR, "auth_config.json"))

PASSWORD_SALT = os.environ.get("PASSWORD_SALT", "excel-merger-salt")

DEFAULT_USERS = [
    {"username": "admin", "password": "admin123", "name": "管理员", "role": "admin", "enabled": True},
    {"username": "user1", "password": "user123", "name": "用户一", "role": "user", "enabled": True},
    {"username": "user2", "password": "user123", "name": "用户二", "role": "user", "enabled": True},
]

CORS_ORIGINS = [
    o.strip() for o in os.environ.get("AUTH_CORS_ORIGINS", "*").split(",")
    if o.strip()
]

# Admin session 过期时间（秒）：2 小时
ADMIN_SESSION_MAX_AGE = 7200

# Admin session: token → {"username": str, "expires": float}
ADMIN_SESSIONS: Dict[str, dict] = {}

ADMIN_COOKIE = "lx_admin_session"


# ===================== 配置加载 =====================

def load_config(path: str = None) -> dict:
    path = path or AUTH_CONFIG_FILE
    if not os.path.exists(path):
        cfg = {"users": [dict(u) for u in DEFAULT_USERS]}
        save_config(cfg, path)
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "users" not in cfg:
            cfg = {"users": [dict(u) for u in DEFAULT_USERS]}
            save_config(cfg, path)
        # 自动补全 enabled 字段
        for u in cfg["users"]:
            if "enabled" not in u:
                u["enabled"] = True
        return cfg
    except (json.JSONDecodeError, IOError):
        return {"users": [dict(u) for u in DEFAULT_USERS]}


def save_config(cfg: dict, path: str = None) -> None:
    path = path or AUTH_CONFIG_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def hash_password(pw: str) -> str:
    return hashlib.sha256((PASSWORD_SALT + pw).encode()).hexdigest()


def find_user(username: str, cfg: dict) -> Optional[dict]:
    for u in cfg.get("users", []):
        if u.get("username") == username:
            return u
    return None


def verify_password(user: dict, password: str) -> bool:
    stored = user.get("password", "")
    if len(stored) == 64 and all(c in "0123456789abcdef" for c in stored):
        return stored == hash_password(password)
    return stored == password


def public_user(u: dict) -> dict:
    """返回不含密码的用户信息"""
    return {
        "username": u.get("username", ""),
        "name": u.get("name", u.get("username", "")),
        "role": u.get("role", "user"),
        "enabled": u.get("enabled", True),
    }


# ===================== Admin Session =====================

def create_admin_session(username: str) -> str:
    token = secrets.token_hex(16)
    ADMIN_SESSIONS[token] = {
        "username": username,
        "expires": time.time() + ADMIN_SESSION_MAX_AGE,
    }
    return token


def get_admin_user(request: Request) -> Optional[dict]:
    """从请求中解析 admin session，返回用户 dict 或 None"""
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        return None
    session = ADMIN_SESSIONS.get(token)
    if not session:
        return None
    if time.time() > session.get("expires", 0):
        del ADMIN_SESSIONS[token]
        return None
    cfg = load_config()
    user = find_user(session["username"], cfg)
    if not user or not user.get("enabled", True) or user.get("role") != "admin":
        # 用户被降级或禁用，清除 session
        del ADMIN_SESSIONS[token]
        return None
    return user


def require_admin(request: Request) -> dict:
    """FastAPI 依赖：要求 admin session 有效"""
    user = get_admin_user(request)
    if not user:
        raise _json_error("未登录或会话已过期", 401)
    return user


def _json_error(detail: str, status: int) -> Exception:
    return HTTPExceptionLite(status_code=status, detail=detail)


class HTTPExceptionLite(Exception):
    """轻量级异常，直接返回 JSON"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


# ===================== FastAPI 应用 =====================

app = FastAPI(title="LX捞数据 - 认证服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 挂载静态文件（如需外部 CSS/JS）
_static_dir = _resource_path("templates/static")
if os.path.isdir(_static_dir):
    app.mount("/admin/static", StaticFiles(directory=_static_dir), name="admin_static")


@app.exception_handler(HTTPExceptionLite)
async def http_exception_handler(request: Request, exc: HTTPExceptionLite):
    return JSONResponse(
        {"status": "error", "detail": exc.detail},
        status_code=exc.status_code,
    )


# ===================== 基础接口（供主应用调用） =====================

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    if not username or not password:
        return JSONResponse({"status": "error", "detail": "用户名和密码不能为空"}, status_code=400)

    cfg = load_config()
    user = find_user(username, cfg)
    if not user or not verify_password(user, password):
        return JSONResponse({"status": "error", "detail": "用户名或密码错误"}, status_code=401)

    if not user.get("enabled", True):
        return JSONResponse({"status": "error", "detail": "该账号已被禁用"}, status_code=403)

    return JSONResponse({
        "status": "success",
        "user": {
            "username": user["username"],
            "name": user.get("name", user["username"]),
            "role": user.get("role", "user"),
        },
    })


# 服务间通信密钥（通过环境变量 SERVICE_TOKEN 配置，桌面应用和认证服务需一致）
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "lx-internal-service-token")


def verify_service_token(request: Request) -> bool:
    """校验服务间通信密钥（用于主应用 ↔ 认证服务的内部接口）"""
    token = request.headers.get("X-Service-Token", "")
    return token == SERVICE_TOKEN


@app.get("/users")
async def list_users(request: Request):
    """供主应用查询用户列表 — 需要服务间通信密钥"""
    if not verify_service_token(request):
        return JSONResponse({"status": "error", "detail": "未授权"}, status_code=401)
    cfg = load_config()
    users = [public_user(u) for u in cfg.get("users", [])]
    return JSONResponse({"status": "success", "users": users})




@app.post("/verify-user")
async def verify_user(request: Request):
    """
    供主应用内部调用的用户状态验证接口。
    接收 {username}，返回该用户当前是否启用及角色信息。
    需要服务间通信密钥。
    """
    if not verify_service_token(request):
        return JSONResponse({"status": "error", "detail": "未授权"}, status_code=401)

    body = await request.json()
    username = body.get("username", "").strip()
    if not username:
        return JSONResponse({"status": "error", "detail": "用户名不能为空"}, status_code=400)

    cfg = load_config()
    user = find_user(username, cfg)
    if not user:
        return JSONResponse({"status": "error", "detail": "用户不存在"}, status_code=404)

    return JSONResponse({
        "status": "success",
        "user": {
            "username": user["username"],
            "name": user.get("name", user["username"]),
            "role": user.get("role", "user"),
            "enabled": user.get("enabled", True),
        }
    })


# ===================== 管理后台页面路由 =====================

@app.get("/admin")
async def admin_entry(request: Request):
    user = get_admin_user(request)
    if user:
        return RedirectResponse("/admin/dashboard", status_code=302)
    return RedirectResponse("/admin/login", status_code=302)


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page():
    html_path = _resource_path("templates/auth_admin.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page():
    html_path = _resource_path("templates/auth_admin.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# ===================== 管理后台 API =====================

@app.post("/admin/login")
async def admin_login(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    if not username or not password:
        return JSONResponse({"status": "error", "detail": "用户名和密码不能为空"}, status_code=400)

    cfg = load_config()
    user = find_user(username, cfg)
    if not user or not verify_password(user, password):
        return JSONResponse({"status": "error", "detail": "用户名或密码错误"}, status_code=401)

    if user.get("role") != "admin":
        return JSONResponse({"status": "error", "detail": "无管理员权限"}, status_code=403)

    if not user.get("enabled", True):
        return JSONResponse({"status": "error", "detail": "该账号已被禁用"}, status_code=403)

    token = create_admin_session(username)
    resp = JSONResponse({"status": "success", "user": public_user(user)})
    resp.set_cookie(
        ADMIN_COOKIE, token,
        max_age=ADMIN_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@app.post("/admin/logout")
async def admin_logout(request: Request):
    token = request.cookies.get(ADMIN_COOKIE)
    if token and token in ADMIN_SESSIONS:
        del ADMIN_SESSIONS[token]
    resp = JSONResponse({"status": "success"})
    resp.delete_cookie(ADMIN_COOKIE)
    return resp


@app.get("/admin/api/me")
async def admin_me(admin: dict = Depends(require_admin)):
    return JSONResponse({"status": "success", "user": public_user(admin)})


@app.get("/admin/api/users")
async def admin_list_users(admin: dict = Depends(require_admin)):
    cfg = load_config()
    users = [public_user(u) for u in cfg.get("users", [])]
    return JSONResponse({"status": "success", "users": users})


@app.post("/admin/api/users")
async def admin_add_user(request: Request, admin: dict = Depends(require_admin)):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    name = body.get("name", username).strip()
    role = body.get("role", "user").strip()
    enabled = body.get("enabled", True)

    if not username or not password:
        raise HTTPExceptionLite(400, "用户名和密码不能为空")
    if role not in ("admin", "user"):
        raise HTTPExceptionLite(400, "角色只能是 admin 或 user")

    cfg = load_config()
    if find_user(username, cfg):
        raise HTTPExceptionLite(409, "用户名已存在")

    cfg["users"].append({
        "username": username,
        "password": password,
        "name": name,
        "role": role,
        "enabled": enabled,
    })
    save_config(cfg)
    return JSONResponse(
        {"status": "success", "user": {"username": username, "name": name, "role": role, "enabled": enabled}},
        status_code=201,
    )


@app.put("/admin/api/users/{username}")
async def admin_edit_user(username: str, request: Request, admin: dict = Depends(require_admin)):
    body = await request.json()
    name = body.get("name")
    role = body.get("role")
    enabled = body.get("enabled")

    if role is not None and role not in ("admin", "user"):
        raise HTTPExceptionLite(400, "角色只能是 admin 或 user")

    cfg = load_config()
    user = find_user(username, cfg)
    if not user:
        raise HTTPExceptionLite(404, "用户不存在")

    # 不允许禁用自己
    if enabled is False and username == admin["username"]:
        raise HTTPExceptionLite(400, "不能禁用自己的账号")

    # 不允许将最后一个管理员降级为普通用户
    if role is not None and role == "user" and user.get("role") == "admin":
        admin_count = sum(1 for u in cfg["users"] if u.get("role") == "admin" and u.get("enabled", True))
        if admin_count <= 1:
            raise HTTPExceptionLite(400, "至少保留一个启用的管理员账号")

    if name is not None:
        user["name"] = name.strip()
    if role is not None:
        user["role"] = role
    if enabled is not None:
        user["enabled"] = enabled

    save_config(cfg)
    return JSONResponse({"status": "success", "user": public_user(user)})


@app.put("/admin/api/users/{username}/password")
async def admin_reset_password(username: str, request: Request, admin: dict = Depends(require_admin)):
    body = await request.json()
    new_password = body.get("password", "").strip()
    if not new_password:
        raise HTTPExceptionLite(400, "密码不能为空")

    cfg = load_config()
    user = find_user(username, cfg)
    if not user:
        raise HTTPExceptionLite(404, "用户不存在")

    user["password"] = new_password
    save_config(cfg)
    return JSONResponse({"status": "success"})


@app.delete("/admin/api/users/{username}")
async def admin_delete_user(username: str, admin: dict = Depends(require_admin)):
    if username == admin["username"]:
        raise HTTPExceptionLite(400, "不能删除自己")

    cfg = load_config()
    user = find_user(username, cfg)
    if not user:
        raise HTTPExceptionLite(404, "用户不存在")

    # 不允许删除最后一个 admin
    admin_count = sum(1 for u in cfg["users"] if u.get("role") == "admin")
    if user.get("role") == "admin" and admin_count <= 1:
        raise HTTPExceptionLite(400, "至少保留一个管理员账号")

    cfg["users"] = [u for u in cfg["users"] if u.get("username") != username]
    save_config(cfg)
    return JSONResponse({"status": "success"})


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("AUTH_HOST", "0.0.0.0")
    port = int(os.environ.get("AUTH_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)
