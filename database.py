"""
SQLite 数据库模块
- 用户管理、应用配置、规则管理、用户规则/省份分配、会话管理
- 替代原有的 JSON 文件存储（auth_config.json / app_config.json）
"""

import os
import json
import time
import hashlib
import secrets
import sqlite3
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# ===================== 路径配置 =====================

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(_BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "app.db")

PASSWORD_SALT = os.environ.get("PASSWORD_SALT", "excel-merger-salt")

# ===================== 内置默认数据 =====================

DEFAULT_USER_FEATURES = {
    "file_merge": True,
    "mail_reader": True,
    "rule_management": True,
}

DEFAULT_USERS = [
    {
        "username": "admin",
        "password": "admin123",
        "name": "管理员",
        "role": "admin",
        "enabled": True,
        "features": dict(DEFAULT_USER_FEATURES),
    },
    {
        "username": "user1",
        "password": "user123",
        "name": "用户一",
        "role": "user",
        "enabled": True,
        "features": dict(DEFAULT_USER_FEATURES),
    },
    {
        "username": "user2",
        "password": "user123",
        "name": "用户二",
        "role": "user",
        "enabled": True,
        "features": dict(DEFAULT_USER_FEATURES),
    },
]

DEFAULT_MAIL_CONFIG = {
    "enabled": False,
    "imap_host": "imap.126.com",
    "email": "",
    "auth_code": "",
    "subject_keywords": [],
    "provinces": [],
    "poll_interval_seconds": 3600,
    "output_prefix": "邮件合并",
    "rule_id": "",
}

DEFAULT_FEATURES = {
    "file_merge": True,
    "mail_reader": True,
    "rule_management": True,
}


# ===================== 数据库连接 =====================

@contextmanager
def get_db():
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'user',
                enabled INTEGER NOT NULL DEFAULT 1,
                features TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                standard_headers TEXT NOT NULL DEFAULT '[]',
                builtin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS user_rules (
                username TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                PRIMARY KEY (username, rule_id)
            );

            CREATE TABLE IF NOT EXISTS user_provinces (
                username TEXT NOT NULL,
                province TEXT NOT NULL,
                PRIMARY KEY (username, province)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                browser_fingerprint TEXT NOT NULL DEFAULT '',
                login_time REAL NOT NULL,
                last_check REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS active_logins (
                username TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                login_time REAL NOT NULL,
                device_id TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS admin_sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                expires REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mail_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                mails TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS processed_uids (
                uid_key TEXT PRIMARY KEY
            );
        """)
    # Seed default data if empty
    _seed_defaults()


def _seed_defaults():
    """如果数据库为空，注入默认数据"""
    with get_db() as conn:
        # Check if users table is empty
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            now = _now()
            for u in DEFAULT_USERS:
                conn.execute(
                    "INSERT INTO users (username, password, name, role, enabled, features, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (u["username"], u["password"], u["name"], u["role"],
                     1 if u["enabled"] else 0, json.dumps(u["features"]), now)
                )

        # Check if app_config has mail_config
        row = conn.execute("SELECT value FROM app_config WHERE key = 'mail_config'").fetchone()
        if not row:
            conn.execute(
                "INSERT INTO app_config (key, value) VALUES (?, ?)",
                ("mail_config", json.dumps(DEFAULT_MAIL_CONFIG))
            )
            conn.execute(
                "INSERT OR IGNORE INTO app_config (key, value) VALUES (?, ?)",
                ("features", json.dumps(DEFAULT_FEATURES))
            )


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


# ===================== 用户 CRUD =====================

def get_all_users() -> List[dict]:
    """返回所有用户（不含密码）"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    return [_row_to_public_user(r) for r in rows]


def get_user(username: str) -> Optional[dict]:
    """获取单个用户（含密码，内部用）"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return None
    return _row_to_user(row)


def get_user_public(username: str) -> Optional[dict]:
    """获取单个用户（不含密码）"""
    u = get_user(username)
    if not u:
        return None
    return _public_user(u)


def create_user(username: str, password: str, name: str = "", role: str = "user",
                 enabled: bool = True, features: dict = None) -> dict:
    """创建用户"""
    now = _now()
    feat = dict(DEFAULT_USER_FEATURES)
    if features:
        for k in DEFAULT_USER_FEATURES:
            if k in features:
                feat[k] = bool(features[k])
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (username, password, name, role, enabled, features, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (username, password, name or username, role, 1 if enabled else 0, json.dumps(feat), now)
        )
    return {"username": username, "name": name or username, "role": role, "enabled": enabled, "features": feat}


def update_user(username: str, name: str = None, role: str = None,
                enabled: bool = None, features: dict = None) -> Optional[dict]:
    """更新用户信息"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return None
        user = _row_to_user(row)

        if name is not None:
            user["name"] = name.strip()
        if role is not None:
            user["role"] = role
        if enabled is not None:
            user["enabled"] = enabled
        if features is not None:
            feat = user.get("features", dict(DEFAULT_USER_FEATURES))
            for k in DEFAULT_USER_FEATURES:
                if k in features:
                    feat[k] = bool(features[k])
            user["features"] = feat

        conn.execute(
            "UPDATE users SET name = ?, role = ?, enabled = ?, features = ? WHERE username = ?",
            (user["name"], user["role"], 1 if user["enabled"] else 0, json.dumps(user["features"]), username)
        )
    return _public_user(user)


def update_user_password(username: str, password: str) -> bool:
    """更新用户密码"""
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return False
        conn.execute("UPDATE users SET password = ? WHERE username = ?", (password, username))
    return True


def delete_user(username: str) -> bool:
    """删除用户及其关联数据"""
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.execute("DELETE FROM user_rules WHERE username = ?", (username,))
        conn.execute("DELETE FROM user_provinces WHERE username = ?", (username,))
        conn.execute("DELETE FROM active_logins WHERE username = ?", (username,))
        conn.execute("DELETE FROM sessions WHERE username = ?", (username,))
    return True


def count_admins() -> int:
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND enabled = 1").fetchone()[0]


# ===================== 应用配置 =====================

def get_app_config_value(key: str, default=None):
    """获取 app_config 中的值"""
    with get_db() as conn:
        row = conn.execute("SELECT value FROM app_config WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return default


def set_app_config_value(key: str, value):
    """设置 app_config 中的值"""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )


def get_mail_config() -> dict:
    cfg = get_app_config_value("mail_config", {})
    if not cfg:
        cfg = dict(DEFAULT_MAIL_CONFIG)
        set_app_config_value("mail_config", cfg)
    # 补全缺失字段
    for k, v in DEFAULT_MAIL_CONFIG.items():
        if k not in cfg:
            cfg[k] = v
    return cfg


def set_mail_config(cfg: dict) -> dict:
    """更新邮件配置（合并而非替换）"""
    existing = get_mail_config()
    for field in ("enabled", "imap_host", "email", "auth_code",
                  "subject_keywords", "provinces", "poll_interval_seconds",
                  "output_prefix", "rule_id"):
        if field in cfg:
            existing[field] = cfg[field]
    set_app_config_value("mail_config", existing)
    return existing


def get_features() -> dict:
    feat = get_app_config_value("features", {})
    if not feat:
        feat = dict(DEFAULT_FEATURES)
        set_app_config_value("features", feat)
    for k, v in DEFAULT_FEATURES.items():
        if k not in feat:
            feat[k] = v
    return feat


def set_features(features: dict) -> dict:
    existing = get_features()
    for field in ("file_merge", "mail_reader", "rule_management"):
        if field in features:
            existing[field] = bool(features[field])
    set_app_config_value("features", existing)
    return existing


def get_full_app_config() -> dict:
    """获取完整应用配置（邮件配置 + 功能开关 + 规则）"""
    return {
        "mail_config": get_mail_config(),
        "features": get_features(),
        "rules": get_all_rules(),
    }


# ===================== 规则 CRUD =====================

def get_all_rules() -> List[dict]:
    """获取所有规则（不含内置规则）"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM rules WHERE builtin = 0 ORDER BY created_at").fetchall()
    return [_row_to_rule(r) for r in rows]


def get_rule(rule_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
    if not row:
        return None
    return _row_to_rule(row)


def create_rule(name: str, standard_headers: list) -> dict:
    import uuid as _uuid
    now = _now()
    rule_id = "r" + _uuid.uuid4().hex[:8]
    headers = [
        {
            "name": sh.get("name", "").strip(),
            "source_columns": [sc.strip() for sc in sh.get("source_columns", []) if sc.strip()],
            **({"value_mappings": sh["value_mappings"]} if sh.get("value_mappings") else {}),
        }
        for sh in standard_headers
        if sh.get("name", "").strip()
    ]
    with get_db() as conn:
        conn.execute(
            "INSERT INTO rules (id, name, standard_headers, builtin, created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
            (rule_id, name, json.dumps(headers, ensure_ascii=False), now, now)
        )
    return {"id": rule_id, "name": name, "standard_headers": headers, "builtin": False, "created_at": now, "updated_at": now}


def update_rule(rule_id: str, name: str, standard_headers: list) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM rules WHERE id = ? AND builtin = 0", (rule_id,)).fetchone()
        if not row:
            return None
        now = _now()
        headers = [
            {
                "name": sh.get("name", "").strip(),
                "source_columns": [sc.strip() for sc in sh.get("source_columns", []) if sc.strip()],
                **({"value_mappings": sh["value_mappings"]} if sh.get("value_mappings") else {}),
            }
            for sh in standard_headers
            if sh.get("name", "").strip()
        ]
        conn.execute(
            "UPDATE rules SET name = ?, standard_headers = ?, updated_at = ? WHERE id = ?",
            (name, json.dumps(headers, ensure_ascii=False), now, rule_id)
        )
    return {"id": rule_id, "name": name, "standard_headers": headers, "builtin": False, "created_at": row["created_at"], "updated_at": now}


def delete_rule(rule_id: str) -> bool:
    """删除规则，同时从所有用户的分配中移除"""
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM rules WHERE id = ? AND builtin = 0", (rule_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        conn.execute("DELETE FROM user_rules WHERE rule_id = ?", (rule_id,))
    return True


# ===================== 用户规则分配 =====================

def get_user_rule_ids(username: str) -> List[str]:
    with get_db() as conn:
        rows = conn.execute("SELECT rule_id FROM user_rules WHERE username = ?", (username,)).fetchall()
    return [r["rule_id"] for r in rows]


def set_user_rules(username: str, rule_ids: List[str]):
    """设置用户的规则分配（替换）"""
    rule_ids = [rid for rid in rule_ids if rid != "_builtin_default"]
    with get_db() as conn:
        conn.execute("DELETE FROM user_rules WHERE username = ?", (username,))
        for rid in rule_ids:
            conn.execute(
                "INSERT OR IGNORE INTO user_rules (username, rule_id) VALUES (?, ?)",
                (username, rid)
            )


def get_rules_for_user(username: str, builtin_rule: dict) -> List[dict]:
    """获取分配给用户的规则 + 内置规则"""
    rule_ids = set(get_user_rule_ids(username))
    all_rules = get_all_rules()
    user_rules = [r for r in all_rules if r["id"] in rule_ids]
    return [builtin_rule] + user_rules


# ===================== 用户省份分配 =====================

def get_user_provinces(username: str) -> List[str]:
    with get_db() as conn:
        rows = conn.execute("SELECT province FROM user_provinces WHERE username = ?", (username,)).fetchall()
    return [r["province"] for r in rows]


def set_user_provinces(username: str, provinces: List[str]):
    with get_db() as conn:
        conn.execute("DELETE FROM user_provinces WHERE username = ?", (username,))
        for prov in provinces:
            conn.execute(
                "INSERT OR IGNORE INTO user_provinces (username, province) VALUES (?, ?)",
                (username, prov)
            )


# ===================== 用户功能权限 =====================

def get_user_features(username: str) -> dict:
    user = get_user(username)
    if not user:
        return dict(DEFAULT_USER_FEATURES)
    return user.get("features", dict(DEFAULT_USER_FEATURES))


def set_user_features(username: str, features: dict) -> Optional[dict]:
    return update_user(username, features=features)


# ===================== 密码验证 =====================

def hash_password(pw: str) -> str:
    return hashlib.sha256((PASSWORD_SALT + pw).encode()).hexdigest()


def verify_password(user: dict, password: str) -> bool:
    stored = user.get("password", "")
    if len(stored) == 64 and all(c in "0123456789abcdef" for c in stored):
        return stored == hash_password(password)
    return stored == password


# ===================== 会话管理 =====================

def create_session(token: str, username: str, browser_fingerprint: str = ""):
    now = time.time()
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (token, username, browser_fingerprint, login_time, last_check) VALUES (?, ?, ?, ?, ?)",
            (token, username, browser_fingerprint, now, 0)
        )


def get_session(token: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    if not row:
        return None
    return {"token": row["token"], "username": row["username"],
            "browser_fingerprint": row["browser_fingerprint"],
            "login_time": row["login_time"], "last_check": row["last_check"]}


def delete_session(token: str):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def update_session_check(token: str):
    with get_db() as conn:
        conn.execute("UPDATE sessions SET last_check = ? WHERE token = ?", (time.time(), token))


def delete_sessions_for_user(username: str):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE username = ?", (username,))


# ===================== 单设备登录 =====================

DEVICE_LOGIN_TIMEOUT = 1800  # 30 分钟


def check_device_login(username: str, device_id: str) -> tuple:
    """检查单设备登录。返回 (allow, reason)"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM active_logins WHERE username = ?", (username,)).fetchone()
    if not row:
        return True, None
    elapsed = time.time() - row["login_time"]
    if elapsed >= DEVICE_LOGIN_TIMEOUT:
        # 超时自动释放
        with get_db() as conn:
            conn.execute("DELETE FROM active_logins WHERE username = ?", (username,))
        return True, None
    # 同一设备允许
    if device_id and row["device_id"] == device_id:
        return True, None
    return False, "该账号已在其他设备登录，请先在该设备退出登录，或联系管理员解绑"


def set_active_login(username: str, token: str, device_id: str = ""):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO active_logins (username, token, login_time, device_id) VALUES (?, ?, ?, ?)",
            (username, token, time.time(), device_id)
        )


def clear_active_login(username: str):
    with get_db() as conn:
        conn.execute("DELETE FROM active_logins WHERE username = ?", (username,))


def heartbeat(username: str):
    with get_db() as conn:
        conn.execute("UPDATE active_logins SET login_time = ? WHERE username = ?", (time.time(), username))


def get_device_status(username: str) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM active_logins WHERE username = ?", (username,)).fetchone()
    if not row:
        return {"bound": False}
    elapsed = time.time() - row["login_time"]
    remaining = max(0, DEVICE_LOGIN_TIMEOUT - elapsed)
    return {
        "bound": True,
        "login_time": row["login_time"],
        "elapsed_seconds": int(elapsed),
        "remaining_seconds": int(remaining),
    }


def unbind_device(username: str):
    clear_active_login(username)


# ===================== Admin 会话 =====================

ADMIN_SESSION_MAX_AGE = 7200  # 2 小时


def create_admin_session(username: str) -> str:
    token = secrets.token_hex(16)
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO admin_sessions (token, username, expires) VALUES (?, ?, ?)",
            (token, username, time.time() + ADMIN_SESSION_MAX_AGE)
        )
    return token


def get_admin_session(token: str) -> Optional[dict]:
    if not token:
        return None
    with get_db() as conn:
        row = conn.execute("SELECT * FROM admin_sessions WHERE token = ?", (token,)).fetchone()
    if not row:
        return None
    if time.time() > row["expires"]:
        with get_db() as conn:
            conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
        return None
    return {"username": row["username"], "expires": row["expires"]}


def delete_admin_session(token: str):
    with get_db() as conn:
        conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))


# ===================== 邮件任务历史 =====================

MAX_TASKS = 50


def save_mail_task(mails: list):
    now = _now()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO mail_tasks (time, mails) VALUES (?, ?)",
            (now, json.dumps(mails, ensure_ascii=False))
        )
        # 保留最近 MAX_TASKS 条
        count = conn.execute("SELECT COUNT(*) FROM mail_tasks").fetchone()[0]
        if count > MAX_TASKS:
            conn.execute(
                "DELETE FROM mail_tasks WHERE id NOT IN (SELECT id FROM mail_tasks ORDER BY id DESC LIMIT ?)",
                (MAX_TASKS,)
            )


def get_mail_tasks() -> List[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM mail_tasks ORDER BY id DESC LIMIT ?", (MAX_TASKS,)).fetchall()
    return [{"time": r["time"], "mails": json.loads(r["mails"])} for r in rows]


# ===================== 邮件已处理 UID =====================

def get_processed_uids() -> set:
    with get_db() as conn:
        rows = conn.execute("SELECT uid_key FROM processed_uids").fetchall()
    return {r["uid_key"] for r in rows}


def add_processed_uids(uid_keys: set):
    with get_db() as conn:
        for key in uid_keys:
            conn.execute("INSERT OR IGNORE INTO processed_uids (uid_key) VALUES (?)", (key,))


def clear_processed_uids():
    with get_db() as conn:
        conn.execute("DELETE FROM processed_uids")


# ===================== 辅助函数 =====================

def _row_to_user(row: sqlite3.Row) -> dict:
    return {
        "username": row["username"],
        "password": row["password"],
        "name": row["name"],
        "role": row["role"],
        "enabled": bool(row["enabled"]),
        "features": json.loads(row["features"]) if row["features"] else dict(DEFAULT_USER_FEATURES),
    }


def _row_to_public_user(row: sqlite3.Row) -> dict:
    return {
        "username": row["username"],
        "name": row["name"],
        "role": row["role"],
        "enabled": bool(row["enabled"]),
        "features": json.loads(row["features"]) if row["features"] else dict(DEFAULT_USER_FEATURES),
    }


def _row_to_rule(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "standard_headers": json.loads(row["standard_headers"]) if row["standard_headers"] else [],
        "builtin": bool(row["builtin"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _public_user(u: dict) -> dict:
    return {
        "username": u["username"],
        "name": u.get("name", u["username"]),
        "role": u.get("role", "user"),
        "enabled": u.get("enabled", True),
        "features": dict(u.get("features", DEFAULT_USER_FEATURES)),
    }
