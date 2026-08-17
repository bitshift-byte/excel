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

配置文件:
  - data/auth_config.json     用户配置
  - data/app_config.json      应用配置（邮件/功能开关/规则）
"""
import os
import sys
import json
import time
import hashlib
import secrets
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse, FileResponse, StreamingResponse
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

# 应用配置文件（邮件配置、功能开关、合并规则）
APP_CONFIG_FILE = os.path.join(DATA_DIR, "app_config.json")

# 更新文件目录（存放上传的 exe 安装包）
UPLOAD_DIR = os.path.join(DATA_DIR, "updates")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 版本信息文件
VERSION_INFO_FILE = os.path.join(UPLOAD_DIR, "version_info.json")


# ===================== 内置默认规则 =====================
# 联合利华标准34列 + 列名变体映射 + 值转换规则
# 此规则是系统核心规则，不可删除、不可编辑，始终位于规则列表首位
BUILTIN_RULE = {
    "id": "_builtin_default",
    "name": "联合利华标准34列（内置）",
    "builtin": True,
    "standard_headers": [
        {"name": "交货", "source_columns": ["交货", "交货号"]},
        {"name": "DlvTy", "source_columns": ["DlvTy", "交货类型"]},
        {"name": "项目", "source_columns": ["项目", "    项目"]},
        {"name": "物料", "source_columns": ["物料", "物料号"]},
        {"name": "描述", "source_columns": ["描述", "物料描述"]},
        {"name": "存储位置", "source_columns": ["存储位置", "位置"]},
        {"name": "销售凭证", "source_columns": ["销售凭证", "销售订单"]},
        {"name": "运达方", "source_columns": ["运达方", "送达方"]},
        {"name": "运达方的名字", "source_columns": ["运达方的名字", "运达方名称"]},
        {"name": "送达方地点", "source_columns": ["送达方地点", "城市"]},
        {"name": "名称 3", "source_columns": ["名称 3", "名称3"]},
        {
            "name": "工厂",
            "source_columns": ["工厂", "Plant"],
            "value_mappings": [
                {"source_file_contains": "分销-下单量", "source_value": "8136", "target_value": "701"},
                {"source_file_contains": "分销-下单量", "source_value": "8137", "target_value": "701"},
                {"source_file_contains": "分销报表", "source_value": "8136", "target_value": "901"},
                {"source_file_contains": "分销报表", "source_value": "8137", "target_value": "901"},
                {"source_file_contains": "分销报表", "source_value": "8205", "target_value": "901"},
                {"source_file_contains": "跑单明细", "source_value": "8136", "target_value": "801"},
                {"source_file_contains": "跑单明细", "source_value": "8137", "target_value": "801"},
                {"source_file_contains": "跑单明细", "source_value": "8205", "target_value": "801"},
            ],
        },
        {"name": "路线", "source_columns": ["路线", "Route"]},
        {"name": "OPS", "source_columns": ["OPS", "全部拣配状态"]},
        {"name": "WhN", "source_columns": ["WhN", "仓库号"]},
        {"name": "批次", "source_columns": ["批次", "Batch"]},
        {"name": "仓位", "source_columns": ["仓位"]},
        {"name": "GM", "source_columns": ["GM", "GS", "货物移动状态"]},
        {"name": "销售组织", "source_columns": ["销售组织", "SOrg.", "SOrg"]},
        {"name": "售达方", "source_columns": ["售达方", "售达方代码"]},
        {"name": "售达方的名字", "source_columns": ["售达方的名字", "售达方名称"]},
        {
            "name": "街道",
            "source_columns": ["街道", "街道地址"],
            "value_mappings": [
                {"when_column": "工厂", "equals": "901", "use_column": "送达方地点"},
            ],
        },
        {"name": "街道2", "source_columns": ["街道2", "街道 2"]},
        {"name": "街道 3", "source_columns": ["街道 3", "街道3"]},
        {"name": "交货量", "source_columns": ["交货量", "交货数量", "    交货量"]},
        {"name": "SU", "source_columns": ["SU", "销售单位"]},
        {"name": "数量(库存单位)", "source_columns": ["数量(库存单位)", "库存数量"]},
        {"name": "计", "source_columns": ["计", "计数", "基本计量单位"]},
        {"name": "总重量", "source_columns": ["总重量", "         总重量"]},
        {"name": "WUn", "source_columns": ["WUn", "重量单位"]},
        {"name": "业务量", "source_columns": ["业务量", "          业务量"]},
        {"name": "VUn", "source_columns": ["VUn", "体积单位"]},
        {"name": "交货日期", "source_columns": ["交货日期", "交货日期(从/到)"]},
        {"name": "发货日期", "source_columns": ["发货日期", "实际发货日", "实际货物移动日期"]},
    ],
}

# 默认应用配置
DEFAULT_APP_CONFIG = {
    "mail_config": {
        "enabled": False,
        "imap_host": "imap.126.com",
        "email": "",
        "auth_code": "",
        "subject_keywords": [],
        "provinces": [],
        "poll_interval_seconds": 3600,
        "output_prefix": "邮件合并",
    },
    "features": {
        "file_merge": True,      # 文件合并功能
        "mail_reader": True,     # 邮件自动读取
        "rule_management": True, # 规则管理（桌面端是否可查看规则）
    },
    "rules": [],  # 内置规则在 load_app_config() 中自动注入，不写入默认配置
}

PASSWORD_SALT = os.environ.get("PASSWORD_SALT", "excel-merger-salt")

# 用户默认功能权限（新用户创建时继承此配置）
DEFAULT_USER_FEATURES = {
    "file_merge": True,       # 文件合并功能
    "mail_reader": True,      # 邮件自动读取
    "rule_management": True,  # 规则查看
}

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

# 用户单设备登录：username → {"token": str, "login_time": float, "device_id": str}
# 登录时检查是否已有活跃会话：
#   - 如果旧会话超过 DEVICE_LOGIN_TIMEOUT 自动释放，允许新登录
#   - 如果旧会话仍在有效期内，且是同一设备再次登录，允许（替换旧会话）
#   - 如果旧会话仍在有效期内，且是不同设备登录，拒绝（防止多设备同时使用）
# 用户退出时清除绑定，超时后自动释放
DEVICE_LOGIN_TIMEOUT = 1800  # 30 分钟后自动释放绑定
ACTIVE_LOGINS: Dict[str, dict] = {}


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
        # 自动补全 enabled 字段和 features 字段
        for u in cfg["users"]:
            if "enabled" not in u:
                u["enabled"] = True
            if "features" not in u:
                u["features"] = json.loads(json.dumps(DEFAULT_USER_FEATURES))
            else:
                # 补全缺失的功能项
                for fk, fv in DEFAULT_USER_FEATURES.items():
                    if fk not in u["features"]:
                        u["features"][fk] = fv
        return cfg
    except (json.JSONDecodeError, IOError):
        return {"users": [dict(u) for u in DEFAULT_USERS]}


def save_config(cfg: dict, path: str = None) -> None:
    path = path or AUTH_CONFIG_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ===================== 应用配置 =====================

def load_app_config() -> dict:
    """加载应用配置（邮件、功能开关、规则），自动补全缺失字段。
    内置规则（_builtin_default）始终注入到 rules 列表首位，不持久化到文件。"""
    if not os.path.exists(APP_CONFIG_FILE):
        cfg = json.loads(json.dumps(DEFAULT_APP_CONFIG))  # deep copy
        save_app_config(cfg)
        return _inject_builtin_rule(cfg)
    try:
        with open(APP_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 补全缺失字段
        for key in DEFAULT_APP_CONFIG:
            if key not in cfg:
                cfg[key] = json.loads(json.dumps(DEFAULT_APP_CONFIG[key]))
            elif isinstance(DEFAULT_APP_CONFIG[key], dict):
                for sub_key in DEFAULT_APP_CONFIG[key]:
                    if sub_key not in cfg[key]:
                        cfg[key][sub_key] = DEFAULT_APP_CONFIG[key][sub_key]
        return _inject_builtin_rule(cfg)
    except (json.JSONDecodeError, IOError):
        return _inject_builtin_rule(json.loads(json.dumps(DEFAULT_APP_CONFIG)))


def _inject_builtin_rule(cfg: dict) -> dict:
    """确保内置规则始终在 rules 列表首位（内存注入，不写入文件）"""
    rules = cfg.get("rules", [])
    # 过滤掉可能已存在的内置规则（防止重复）
    rules = [r for r in rules if not r.get("builtin") and r.get("id") != "_builtin_default"]
    cfg["rules"] = [json.loads(json.dumps(BUILTIN_RULE))] + rules
    return cfg


def save_app_config(cfg: dict) -> None:
    """保存应用配置，自动过滤内置规则（不写入文件）"""
    cfg_to_save = json.loads(json.dumps(cfg))
    if "rules" in cfg_to_save:
        cfg_to_save["rules"] = [r for r in cfg_to_save["rules"] if not r.get("builtin")]
    with open(APP_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg_to_save, f, ensure_ascii=False, indent=2)


def public_mail_config(cfg: dict) -> dict:
    """返回不含敏感信息的邮件配置（供桌面应用使用，但需要 auth_code 来连接邮箱）"""
    mc = cfg.get("mail_config", {})
    # 桌面应用需要 auth_code 来连接邮箱，所以全部返回
    return dict(mc)


def public_app_config(cfg: dict) -> dict:
    """返回供桌面应用使用的完整应用配置"""
    return {
        "mail_config": public_mail_config(cfg),
        "features": dict(cfg.get("features", DEFAULT_APP_CONFIG["features"])),
        "rules": list(cfg.get("rules", [])),
    }


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
        "features": dict(u.get("features", DEFAULT_USER_FEATURES)),
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

    # 单设备登录：检查是否已在其他设备登录
    device_id = body.get("device_id", "").strip()
    existing = ACTIVE_LOGINS.get(user["username"])
    if existing:
        elapsed = time.time() - existing.get("login_time", 0)
        if elapsed < DEVICE_LOGIN_TIMEOUT:
            # 同一设备再次登录：允许（替换旧会话）
            if device_id and existing.get("device_id") == device_id:
                pass  # 继续走下面的登录流程，替换旧会话
            else:
                return JSONResponse({
                    "status": "error",
                    "detail": "该账号已在其他设备登录，请先在该设备退出登录，或联系管理员解绑",
                }, status_code=409)
        else:
            # 超时自动释放
            del ACTIVE_LOGINS[user["username"]]

    # 生成登录令牌，绑定当前设备
    login_token = secrets.token_hex(16)
    ACTIVE_LOGINS[user["username"]] = {
        "token": login_token,
        "login_time": time.time(),
        "device_id": device_id,
    }

    return JSONResponse({
        "status": "success",
        "user": {
            "username": user["username"],
            "name": user.get("name", user["username"]),
            "role": user.get("role", "user"),
            "features": dict(user.get("features", DEFAULT_USER_FEATURES)),
            "login_token": login_token,
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
            "features": dict(user.get("features", DEFAULT_USER_FEATURES)),
        }
    })


# ===================== 服务间接口（供桌面应用调用） =====================

@app.post("/logout")
async def service_logout(request: Request):
    """供主应用调用的退出登录接口，清除设备绑定。
    接收 {username}，需要服务间通信密钥。"""
    if not verify_service_token(request):
        return JSONResponse({"status": "error", "detail": "未授权"}, status_code=401)

    body = await request.json()
    username = body.get("username", "").strip()
    if username and username in ACTIVE_LOGINS:
        del ACTIVE_LOGINS[username]
    return JSONResponse({"status": "success"})


@app.post("/heartbeat")
async def heartbeat(request: Request):
    """供主应用定期调用的心跳接口，刷新设备绑定的活跃时间。
    接收 {username}，需要服务间通信密钥。"""
    if not verify_service_token(request):
        return JSONResponse({"status": "error", "detail": "未授权"}, status_code=401)

    body = await request.json()
    username = body.get("username", "").strip()
    if username and username in ACTIVE_LOGINS:
        ACTIVE_LOGINS[username]["login_time"] = time.time()
    return JSONResponse({"status": "success"})


@app.post("/admin/api/users/{username}/unbind-device")
async def admin_unbind_device(username: str, admin: dict = Depends(require_admin)):
    """管理员强制解绑用户设备"""
    if username in ACTIVE_LOGINS:
        del ACTIVE_LOGINS[username]
    return JSONResponse({"status": "success"})


@app.get("/admin/api/users/{username}/device-status")
async def admin_device_status(username: str, admin: dict = Depends(require_admin)):
    """查看用户设备绑定状态"""
    active = ACTIVE_LOGINS.get(username)
    if active:
        elapsed = time.time() - active.get("login_time", 0)
        remaining = max(0, DEVICE_LOGIN_TIMEOUT - elapsed)
        return JSONResponse({
            "status": "success",
            "bound": True,
            "login_time": active.get("login_time"),
            "elapsed_seconds": int(elapsed),
            "remaining_seconds": int(remaining),
        })
    return JSONResponse({"status": "success", "bound": False})


@app.get("/app-config")
async def get_app_config(request: Request):
    """供桌面应用获取完整配置（邮件、功能开关、规则）— 需要服务密钥"""
    if not verify_service_token(request):
        return JSONResponse({"status": "error", "detail": "未授权"}, status_code=401)
    cfg = load_app_config()
    return JSONResponse({"status": "success", "config": public_app_config(cfg)})


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

    # 功能权限：从请求体获取，缺失的用默认值补全
    features = body.get("features", {})
    user_features = json.loads(json.dumps(DEFAULT_USER_FEATURES))
    for fk in DEFAULT_USER_FEATURES:
        if fk in features:
            user_features[fk] = bool(features[fk])

    cfg["users"].append({
        "username": username,
        "password": password,
        "name": name,
        "role": role,
        "enabled": enabled,
        "features": user_features,
    })
    save_config(cfg)
    return JSONResponse(
        {"status": "success", "user": {"username": username, "name": name, "role": role, "enabled": enabled, "features": user_features}},
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
    # 更新功能权限
    features = body.get("features")
    if features is not None:
        user_features = user.get("features", json.loads(json.dumps(DEFAULT_USER_FEATURES)))
        for fk in DEFAULT_USER_FEATURES:
            if fk in features:
                user_features[fk] = bool(features[fk])
        user["features"] = user_features

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



# ===================== 管理后台 API — 应用配置 =====================

@app.get("/admin/api/app-config")
async def admin_get_app_config(admin: dict = Depends(require_admin)):
    """获取完整应用配置"""
    cfg = load_app_config()
    return JSONResponse({"status": "success", "config": public_app_config(cfg)})


@app.put("/admin/api/mail-config")
async def admin_update_mail_config(request: Request, admin: dict = Depends(require_admin)):
    """更新邮件配置"""
    body = await request.json()
    cfg = load_app_config()
    mc = cfg.get("mail_config", {})

    # 更新字段
    for field in ("enabled", "imap_host", "email", "auth_code",
                  "subject_keywords", "provinces", "poll_interval_seconds",
                  "output_prefix"):
        if field in body:
            mc[field] = body[field]

    cfg["mail_config"] = mc
    save_app_config(cfg)
    return JSONResponse({"status": "success", "config": public_mail_config(cfg)})


@app.get("/admin/api/features")
async def admin_get_features(admin: dict = Depends(require_admin)):
    """获取功能开关"""
    cfg = load_app_config()
    return JSONResponse({"status": "success", "features": cfg.get("features", {})})


@app.put("/admin/api/features")
async def admin_update_features(request: Request, admin: dict = Depends(require_admin)):
    """更新功能开关"""
    body = await request.json()
    cfg = load_app_config()
    features = cfg.get("features", {})

    for field in ("file_merge", "mail_reader", "rule_management"):
        if field in body:
            features[field] = bool(body[field])

    cfg["features"] = features
    save_app_config(cfg)
    return JSONResponse({"status": "success", "features": features})


# ===================== 管理后台 API — 用户功能权限 =====================

@app.get("/admin/api/users/{username}/features")
async def admin_get_user_features(username: str, admin: dict = Depends(require_admin)):
    """获取指定用户的功能权限"""
    cfg = load_config()
    user = find_user(username, cfg)
    if not user:
        raise HTTPExceptionLite(404, "用户不存在")
    return JSONResponse({"status": "success", "features": dict(user.get("features", DEFAULT_USER_FEATURES))})


@app.put("/admin/api/users/{username}/features")
async def admin_update_user_features(username: str, request: Request, admin: dict = Depends(require_admin)):
    """更新指定用户的功能权限"""
    body = await request.json()
    cfg = load_config()
    user = find_user(username, cfg)
    if not user:
        raise HTTPExceptionLite(404, "用户不存在")

    user_features = user.get("features", json.loads(json.dumps(DEFAULT_USER_FEATURES)))
    for fk in DEFAULT_USER_FEATURES:
        if fk in body:
            user_features[fk] = bool(body[fk])
    user["features"] = user_features
    save_config(cfg)
    return JSONResponse({"status": "success", "features": user_features})


# ===================== 管理后台 API — 规则管理 =====================

@app.get("/admin/api/rules")
async def admin_list_rules(admin: dict = Depends(require_admin)):
    """获取规则列表"""
    cfg = load_app_config()
    return JSONResponse({"status": "success", "rules": cfg.get("rules", [])})


@app.post("/admin/api/rules")
async def admin_create_rule(request: Request, admin: dict = Depends(require_admin)):
    """新增规则"""
    import uuid as _uuid
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPExceptionLite(400, "规则名称不能为空")
    standard_headers = body.get("standard_headers", [])
    if not standard_headers:
        raise HTTPExceptionLite(400, "请至少添加一个标准表头")

    cfg = load_app_config()
    now = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    rule = {
        "id": "r" + _uuid.uuid4().hex[:8],
        "name": name,
        "standard_headers": [
            {
                "name": sh.get("name", "").strip(),
                "source_columns": [sc.strip() for sc in sh.get("source_columns", []) if sc.strip()],
                **({"value_mappings": sh["value_mappings"]} if sh.get("value_mappings") else {}),
            }
            for sh in standard_headers
            if sh.get("name", "").strip()
        ],
        "created_at": now,
        "updated_at": now,
    }
    cfg.setdefault("rules", []).append(rule)
    save_app_config(cfg)
    return JSONResponse({"status": "success", "rule": rule}, status_code=201)


@app.put("/admin/api/rules/{rule_id}")
async def admin_update_rule(rule_id: str, request: Request, admin: dict = Depends(require_admin)):
    """编辑规则"""
    # 内置规则不可编辑
    if rule_id == "_builtin_default":
        raise HTTPExceptionLite(400, "内置规则不可编辑")
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPExceptionLite(400, "规则名称不能为空")

    cfg = load_app_config()
    rules = cfg.get("rules", [])
    found = None
    for r in rules:
        if r["id"] == rule_id:
            found = r
            break
    if not found:
        raise HTTPExceptionLite(404, "规则不存在")
    if found.get("builtin"):
        raise HTTPExceptionLite(400, "内置规则不可编辑")

    standard_headers = body.get("standard_headers", [])
    found["name"] = name
    found["standard_headers"] = [
        {
            "name": sh.get("name", "").strip(),
            "source_columns": [sc.strip() for sc in sh.get("source_columns", []) if sc.strip()],
            **({"value_mappings": sh["value_mappings"]} if sh.get("value_mappings") else {}),
        }
        for sh in standard_headers
        if sh.get("name", "").strip()
    ]
    found["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    save_app_config(cfg)
    return JSONResponse({"status": "success", "rule": found})


@app.delete("/admin/api/rules/{rule_id}")
async def admin_delete_rule(rule_id: str, admin: dict = Depends(require_admin)):
    """删除规则"""
    # 内置规则不可删除
    if rule_id == "_builtin_default":
        raise HTTPExceptionLite(400, "内置规则不可删除")
    cfg = load_app_config()
    rules = cfg.get("rules", [])
    # 检查是否为内置规则
    for r in rules:
        if r["id"] == rule_id and r.get("builtin"):
            raise HTTPExceptionLite(400, "内置规则不可删除")
    new_rules = [r for r in rules if r["id"] != rule_id]
    if len(new_rules) == len(rules):
        raise HTTPExceptionLite(404, "规则不存在")
    cfg["rules"] = new_rules
    save_app_config(cfg)
    return JSONResponse({"status": "success"})



# ===================== 软件升级管理 =====================

# 版本信息结构（支持多平台）:
# {
#   "version": "v1.2.0",
#   "notes": "更新说明",
#   "platforms": {
#     "windows": {"filename": "xxx.exe", "size": 12345, "uploaded_at": "2024-01-01 12:00:00"},
#     "macos":   {"filename": "xxx.zip", "size": 12345, "uploaded_at": "2024-01-01 12:00:00"}
#   }
# }
# 向后兼容：如果没有 platforms 键，按旧格式解析（filename 视为 windows）。


def _load_version_info() -> dict:
    """读取当前版本信息"""
    try:
        if os.path.exists(VERSION_INFO_FILE):
            with open(VERSION_INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"version": "", "notes": "", "platforms": {}}


def _save_version_info(info: dict):
    with open(VERSION_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


def _get_platform_file(info: dict, platform: str) -> dict:
    """从版本信息中取出指定平台的文件信息。
    向后兼容旧格式（无 platforms 键时，filename 视为 windows）。"""
    if "platforms" in info:
        return info["platforms"].get(platform, {})
    # 旧格式兼容
    if platform == "windows":
        return {
            "filename": info.get("filename", ""),
            "size": info.get("size", 0),
            "uploaded_at": info.get("uploaded_at", ""),
        }
    return {}


@app.get("/update/check")
async def update_check(request: Request):
    """供桌面应用检查更新（需服务密钥）。
    查询参数 platform=windows|macos，返回对应平台的版本信息。"""
    if not verify_service_token(request):
        return JSONResponse({"status": "error", "detail": "未授权"}, status_code=401)
    platform = request.query_params.get("platform", "windows")
    if platform not in ("windows", "macos"):
        platform = "windows"
    info = _load_version_info()
    pf = _get_platform_file(info, platform)
    filename = pf.get("filename", "")
    has_file = bool(filename and os.path.exists(os.path.join(UPLOAD_DIR, filename)))
    return JSONResponse({
        "status": "success",
        "version": info.get("version", ""),
        "filename": filename,
        "notes": info.get("notes", ""),
        "uploaded_at": pf.get("uploaded_at", ""),
        "size": pf.get("size", 0),
        "sha256": pf.get("sha256", ""),
        "platform": platform,
        "has_file": has_file,
    })


@app.get("/update/download")
async def update_download(request: Request):
    """供桌面应用下载更新文件（需服务密钥）。
    查询参数 platform=windows|macos。"""
    if not verify_service_token(request):
        return JSONResponse({"status": "error", "detail": "未授权"}, status_code=401)
    platform = request.query_params.get("platform", "windows")
    if platform not in ("windows", "macos"):
        platform = "windows"
    info = _load_version_info()
    pf = _get_platform_file(info, platform)
    filename = pf.get("filename", "")
    if not filename:
        return JSONResponse({"status": "error", "detail": "暂无可用的更新文件"}, status_code=404)
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return JSONResponse({"status": "error", "detail": "更新文件不存在"}, status_code=404)
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=filename,
    )


@app.get("/admin/api/update-info")
async def admin_get_update_info(admin: dict = Depends(require_admin)):
    """管理员获取当前版本信息"""
    info = _load_version_info()
    # 列出已上传的文件
    files = []
    for f in os.listdir(UPLOAD_DIR):
        fp = os.path.join(UPLOAD_DIR, f)
        if os.path.isfile(fp) and not f.endswith(".json"):
            files.append({
                "filename": f,
                "size": os.path.getsize(fp),
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(fp))),
            })
    # 组装各平台信息（兼容旧格式）
    win_info = _get_platform_file(info, "windows")
    mac_info = _get_platform_file(info, "macos")
    return JSONResponse({
        "status": "success",
        "version": info.get("version", ""),
        "notes": info.get("notes", ""),
        "windows": win_info,
        "macos": mac_info,
        "files": files,
    })



def _save_uploaded_exe(contents: bytes, filename: str, version: str, notes: str, platform: str) -> dict:
    """保存上传的安装包并更新版本信息（供管理员上传和 CI 服务令牌上传复用）。"""
    if not version:
        return {"status": "error", "detail": "版本号不能为空", "code": 400}
    if platform not in ("windows", "macos"):
        platform = "windows"

    safe_name = os.path.basename(filename or "update")
    if platform == "windows":
        if not safe_name.lower().endswith(".exe"):
            safe_name += ".exe"
    else:
        if not safe_name.lower().endswith(".zip"):
            safe_name += ".zip"

    if len(contents) > 200 * 1024 * 1024:
        return {"status": "error", "detail": "文件大小超过 200MB 限制", "code": 400}
    if len(contents) < 1_000_000:
        return {"status": "error", "detail": "文件过小，可能不是有效的安装包", "code": 400}

    sha256_hash = hashlib.sha256(contents).hexdigest()

    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    info = _load_version_info()
    info["version"] = version
    info["notes"] = notes
    if "platforms" not in info:
        info["platforms"] = {}
    info["platforms"][platform] = {
        "filename": safe_name,
        "size": len(contents),
        "sha256": sha256_hash,
        "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_version_info(info)
    return {"status": "success", "info": info, "sha256": sha256_hash}


@app.post("/admin/api/upload-exe")
async def admin_upload_exe(
    admin: dict = Depends(require_admin),
    version: str = Form(""),
    notes: str = Form(""),
    platform: str = Form("windows"),
    file: UploadFile = File(...),
):
    """管理员上传新版本安装包（支持 Windows .exe 和 macOS .zip）"""
    contents = await file.read()
    result = _save_uploaded_exe(contents, file.filename or "update", version, notes, platform)
    code = result.pop("code", 200)
    return JSONResponse(result, status_code=code)


@app.post("/api/upload-update")
async def ci_upload_update(
    request: Request,
    version: str = Form(""),
    notes: str = Form(""),
    platform: str = Form("windows"),
    file: UploadFile = File(...),
):
    """CI/CD 服务令牌上传新版本安装包（无需管理员登录，仅需 X-Service-Token）。
    供 GitHub Actions 在构建完成后自动上传产物到云端。"""
    if not verify_service_token(request):
        return JSONResponse({"status": "error", "detail": "未授权：缺少或错误的 X-Service-Token"}, status_code=401)
    contents = await file.read()
    result = _save_uploaded_exe(contents, file.filename or "update", version, notes, platform)
    code = result.pop("code", 200)
    return JSONResponse(result, status_code=code)


@app.delete("/admin/api/update-info")
async def admin_delete_update(admin: dict = Depends(require_admin)):
    """管理员清除当前版本信息（不删文件）"""
    _save_version_info({"version": "", "notes": "", "platforms": {}})
    return JSONResponse({"status": "success"})


@app.delete("/admin/api/update-file/{filename}")
async def admin_delete_update_file(filename: str, admin: dict = Depends(require_admin)):
    """管理员删除指定的更新文件"""
    safe_name = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    if not os.path.exists(file_path):
        return JSONResponse({"status": "error", "detail": "文件不存在"}, status_code=404)
    os.remove(file_path)
    # 如果删除的是当前版本文件，清空对应平台信息
    info = _load_version_info()
    changed = False
    if "platforms" in info:
        for plat, pf in list(info["platforms"].items()):
            if pf.get("filename") == safe_name:
                del info["platforms"][plat]
                changed = True
    # 旧格式兼容
    if info.get("filename") == safe_name:
        info["filename"] = ""
        info["size"] = 0
        info["uploaded_at"] = ""
        changed = True
    if changed:
        _save_version_info(info)
    return JSONResponse({"status": "success"})


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("AUTH_HOST", "0.0.0.0")
    port = int(os.environ.get("AUTH_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)
