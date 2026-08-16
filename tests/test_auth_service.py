"""
auth_service 单元测试
- POST /login：正确用户名密码 → 返回用户信息；错误密码 → 401；空字段 → 400；不存在用户 → 401；禁用用户 → 403
- GET /health：健康检查
- GET /users：返回用户列表
- Admin 后台：页面路由、登录、用户管理 CRUD、安全约束
"""
import json
import pytest
from fastapi.testclient import TestClient

import auth_service
from auth_service import app, load_config, find_user, verify_password, hash_password, ADMIN_SESSIONS, ADMIN_COOKIE

TEST_CONFIG = {
    "users": [
        {"username": "admin", "password": "admin123", "name": "管理员", "role": "admin", "enabled": True},
        {"username": "user1", "password": "user123", "name": "用户一", "role": "user", "enabled": True},
        {"username": "disabled_user", "password": "pass123", "name": "禁用用户", "role": "user", "enabled": False},
        {"username": "disabled_admin", "password": "pass123", "name": "禁用管理员", "role": "admin", "enabled": False},
    ],
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg_file = tmp_path / "auth_config.json"
    cfg_file.write_text(json.dumps(TEST_CONFIG, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(auth_service, "AUTH_CONFIG_FILE", str(cfg_file))
    # 使用临时目录存放上传文件
    tmp_updates = tmp_path / "updates"
    tmp_updates.mkdir(exist_ok=True)
    monkeypatch.setattr(auth_service, "UPLOAD_DIR", str(tmp_updates))
    monkeypatch.setattr(auth_service, "VERSION_INFO_FILE", str(tmp_updates / "version_info.json"))
    ADMIN_SESSIONS.clear()
    auth_service.ACTIVE_LOGINS.clear()
    return TestClient(app)


# ===================== 纯逻辑测试 =====================

def test_find_user_exists():
    cfg = {"users": [{"username": "admin", "password": "x"}]}
    user = find_user("admin", cfg)
    assert user is not None
    assert user["username"] == "admin"


def test_find_user_not_exists():
    cfg = {"users": [{"username": "admin", "password": "x"}]}
    assert find_user("nobody", cfg) is None


def test_verify_password_plaintext():
    user = {"password": "admin123"}
    assert verify_password(user, "admin123") is True
    assert verify_password(user, "wrong") is False


def test_verify_password_hashed():
    hashed = hash_password("secret123")
    user = {"password": hashed}
    assert verify_password(user, "secret123") is True
    assert verify_password(user, "wrong") is False


def test_hash_password_is_sha256():
    h = hash_password("test")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# ===================== 基础接口测试 =====================

def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_login_success(client):
    resp = client.post("/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["user"]["username"] == "admin"
    assert data["user"]["name"] == "管理员"
    assert data["user"]["role"] == "admin"


def test_login_wrong_password(client):
    resp = client.post("/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    assert "用户名或密码错误" in resp.json()["detail"]


def test_login_nonexistent_user(client):
    resp = client.post("/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401
    assert "用户名或密码错误" in resp.json()["detail"]


def test_login_empty_fields(client):
    resp = client.post("/login", json={"username": "", "password": ""})
    assert resp.status_code == 400


def test_login_missing_fields(client):
    resp = client.post("/login", json={"username": "admin"})
    assert resp.status_code == 400


def test_login_disabled_user_returns_403(client):
    resp = client.post("/login", json={"username": "disabled_user", "password": "pass123"})
    assert resp.status_code == 403
    assert "已被禁用" in resp.json()["detail"]


def test_login_enabled_user_success(client):
    resp = client.post("/login", json={"username": "user1", "password": "user123"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_list_users_requires_service_token(client):
    """没有服务密钥时 /users 返回 401"""
    resp = client.get("/users")
    assert resp.status_code == 401


def test_list_users_with_service_token(client):
    """有服务密钥时 /users 返回用户列表"""
    resp = client.get("/users", headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["users"]) == 4
    assert data["users"][0]["username"] == "admin"
    # 不应返回密码
    for u in data["users"]:
        assert "password" not in u


def test_verify_user_with_service_token(client):
    """verify-user 接口需要服务密钥"""
    # 无密钥
    resp = client.post("/verify-user", json={"username": "admin"})
    assert resp.status_code == 401
    # 有密钥
    resp2 = client.post("/verify-user", json={"username": "admin"}, headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["status"] == "success"
    assert data["user"]["username"] == "admin"
    assert data["user"]["enabled"] is True


def test_verify_user_nonexistent(client):
    """verify-user 对不存在的用户返回 404"""
    resp = client.post("/verify-user", json={"username": "nobody"}, headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 404


def test_verify_user_disabled(client):
    """verify-user 对禁用用户返回 enabled=False"""
    resp = client.post("/verify-user", json={"username": "disabled_user"}, headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200
    assert resp.json()["user"]["enabled"] is False


def test_default_config_created_on_first_run(tmp_path, monkeypatch):
    cfg_file = tmp_path / "auth_config.json"
    monkeypatch.setattr(auth_service, "AUTH_CONFIG_FILE", str(cfg_file))
    cfg = load_config()
    assert "users" in cfg
    assert len(cfg["users"]) >= 3
    assert cfg_file.exists()
    # 所有用户应有 enabled 字段
    for u in cfg["users"]:
        assert "enabled" in u


def test_load_config_auto_fills_enabled(tmp_path, monkeypatch):
    """旧配置无 enabled 字段时自动补全为 True"""
    cfg_file = tmp_path / "auth_config.json"
    old_cfg = {"users": [{"username": "test", "password": "x", "name": "T", "role": "user"}]}
    cfg_file.write_text(json.dumps(old_cfg), encoding="utf-8")
    monkeypatch.setattr(auth_service, "AUTH_CONFIG_FILE", str(cfg_file))
    cfg = load_config()
    assert cfg["users"][0]["enabled"] is True


# ===================== Admin 页面路由测试 =====================

def test_admin_redirects_to_login_when_unauthenticated(client):
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["location"]


def test_admin_login_page_returns_html(client):
    resp = client.get("/admin/login")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_admin_dashboard_page_returns_html(client):
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


# ===================== Admin 登录测试 =====================

def test_admin_login_success(client):
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"
    assert ADMIN_COOKIE in resp.cookies


def test_admin_login_non_admin_returns_403(client):
    resp = client.post("/admin/login", json={"username": "user1", "password": "user123"})
    assert resp.status_code == 403
    assert "无管理员权限" in resp.json()["detail"]


def test_admin_login_wrong_password(client):
    resp = client.post("/admin/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_admin_login_disabled_admin_returns_403(client):
    resp = client.post("/admin/login", json={"username": "disabled_admin", "password": "pass123"})
    assert resp.status_code == 403


def test_admin_logout_clears_session(client):
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    token = resp.cookies.get(ADMIN_COOKIE)
    assert token in ADMIN_SESSIONS

    client.cookies.set(ADMIN_COOKIE, token)
    resp2 = client.post("/admin/logout")
    assert resp2.status_code == 200
    assert token not in ADMIN_SESSIONS


def test_admin_redirects_to_dashboard_when_authenticated(client):
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    token = resp.cookies.get(ADMIN_COOKIE)
    client.cookies.set(ADMIN_COOKIE, token)
    resp2 = client.get("/admin", follow_redirects=False)
    assert resp2.status_code == 302
    assert "/admin/dashboard" in resp2.headers["location"]


# ===================== Admin 用户管理 API 测试 =====================

@pytest.fixture
def admin_client(client):
    """已登录 admin 的 client"""
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    token = resp.cookies.get(ADMIN_COOKIE)
    client.cookies.set(ADMIN_COOKIE, token)
    return client


def test_admin_get_users(admin_client):
    resp = admin_client.get("/admin/api/users")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["users"]) == 4
    for u in data["users"]:
        assert "enabled" in u
        assert "password" not in u


def test_admin_get_me(admin_client):
    resp = admin_client.get("/admin/api/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"


def test_admin_add_user_success(admin_client):
    resp = admin_client.post("/admin/api/users", json={
        "username": "newuser", "password": "newpass", "name": "新用户", "role": "user", "enabled": True
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "success"
    assert data["user"]["username"] == "newuser"


def test_admin_add_duplicate_user_returns_409(admin_client):
    resp = admin_client.post("/admin/api/users", json={
        "username": "admin", "password": "x", "name": "dup", "role": "user"
    })
    assert resp.status_code == 409


def test_admin_edit_user(admin_client):
    resp = admin_client.put("/admin/api/users/user1", json={
        "name": "新名字", "role": "admin", "enabled": False
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["name"] == "新名字"
    assert data["user"]["role"] == "admin"
    assert data["user"]["enabled"] is False


def test_admin_edit_nonexistent_user_returns_404(admin_client):
    resp = admin_client.put("/admin/api/users/nobody", json={"name": "x"})
    assert resp.status_code == 404


def test_admin_reset_password(admin_client):
    resp = admin_client.put("/admin/api/users/user1/password", json={"password": "newpw"})
    assert resp.status_code == 200
    # 验证新密码可以登录
    resp2 = admin_client.post("/login", json={"username": "user1", "password": "newpw"})
    assert resp2.status_code == 200


def test_admin_delete_user(admin_client):
    resp = admin_client.delete("/admin/api/users/user1")
    assert resp.status_code == 200
    # 确认已删除
    resp2 = admin_client.get("/admin/api/users")
    usernames = [u["username"] for u in resp2.json()["users"]]
    assert "user1" not in usernames


def test_admin_cannot_delete_self(admin_client):
    resp = admin_client.delete("/admin/api/users/admin")
    assert resp.status_code == 400
    assert "不能删除自己" in resp.json()["detail"]


def test_admin_cannot_disable_self(admin_client):
    resp = admin_client.put("/admin/api/users/admin", json={"enabled": False})
    assert resp.status_code == 400
    assert "不能禁用自己" in resp.json()["detail"]


def test_admin_cannot_delete_last_admin(admin_client):
    """删除后至少保留一个启用的管理员"""
    # 创建第二个管理员
    admin_client.post("/admin/api/users", json={
        "username": "admin2", "password": "pw", "name": "Admin2", "role": "admin", "enabled": True
    })
    # 用 admin2 登录
    resp = admin_client.post("/admin/login", json={"username": "admin2", "password": "pw"})
    token2 = resp.cookies.get(ADMIN_COOKIE)
    admin_client.cookies.set(ADMIN_COOKIE, token2)
    # admin2 可以删除 admin（admin2 自己仍然是管理员）
    resp2 = admin_client.delete("/admin/api/users/admin")
    assert resp2.status_code == 200
    # 现在 admin2 是唯一的管理员，不能删除自己
    resp3 = admin_client.delete("/admin/api/users/admin2")
    assert resp3.status_code == 400
    assert "不能删除自己" in resp3.json()["detail"]
    # 确认 admin2 仍然存在
    resp4 = admin_client.get("/admin/api/users")
    usernames = [u["username"] for u in resp4.json()["users"]]
    assert "admin2" in usernames


def test_admin_unauthenticated_access_returns_401(client):
    resp = client.get("/admin/api/users")
    assert resp.status_code == 401
    resp2 = client.get("/admin/api/me")
    assert resp2.status_code == 401


def test_admin_unauthenticated_post_returns_401(client):
    resp = client.post("/admin/api/users", json={"username": "x", "password": "y"})
    assert resp.status_code == 401


# ===================== 禁用用户的 admin session 失效测试 =====================

def test_disabled_admin_session_invalidated(client):
    """管理员被禁用后，即使有 session 也无法访问 admin API"""
    # admin 登录，提取 token
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    # 从 set-cookie header 提取 token
    set_cookie = resp.headers.get("set-cookie", "")
    admin_token = set_cookie.split(ADMIN_COOKIE + "=")[1].split(";")[0] if ADMIN_COOKIE + "=" in set_cookie else None
    assert admin_token is not None
    assert admin_token in ADMIN_SESSIONS

    # 创建第二个 admin
    client.cookies.set(ADMIN_COOKIE, admin_token)
    client.post("/admin/api/users", json={
        "username": "admin2", "password": "pw", "name": "Admin2", "role": "admin", "enabled": True
    })
    # 用 admin2 登录
    resp2 = client.post("/admin/login", json={"username": "admin2", "password": "pw"})
    set_cookie2 = resp2.headers.get("set-cookie", "")
    token2 = set_cookie2.split(ADMIN_COOKIE + "=")[1].split(";")[0] if ADMIN_COOKIE + "=" in set_cookie2 else None
    client.cookies.set(ADMIN_COOKIE, token2)

    # admin2 禁用 admin
    resp3 = client.put("/admin/api/users/admin", json={"enabled": False})
    assert resp3.status_code == 200

    # admin 的旧 session 仍然在 ADMIN_SESSIONS 中，但 get_admin_user 会校验 enabled
    # 用 admin 的旧 token 访问 admin API 应该失败
    client.cookies.clear()
    client.cookies.set(ADMIN_COOKIE, admin_token)
    resp4 = client.get("/admin/api/me")
    assert resp4.status_code == 401

    # admin 也无法重新登录
    resp5 = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert resp5.status_code == 403
    assert "已被禁用" in resp5.json()["detail"]


def test_admin_cannot_demote_last_admin(admin_client):
    """不能将最后一个启用的管理员降级为普通用户"""
    # admin 是唯一启用的管理员，降级为 user 应该返回 400
    resp = admin_client.put("/admin/api/users/admin", json={"role": "user"})
    assert resp.status_code == 400
    assert "至少保留一个" in resp.json()["detail"]
    # 确认 admin 仍然是管理员
    resp2 = admin_client.get("/admin/api/users")
    admin_user = [u for u in resp2.json()["users"] if u["username"] == "admin"][0]
    assert admin_user["role"] == "admin"


def test_admin_can_demote_admin_when_multiple_exist(admin_client):
    """有多个管理员时，可以降级其中一个"""
    # 创建第二个管理员
    admin_client.post("/admin/api/users", json={
        "username": "admin2", "password": "pw", "name": "Admin2", "role": "admin", "enabled": True
    })
    # 现在有两个管理员，可以降级 admin2
    resp = admin_client.put("/admin/api/users/admin2", json={"role": "user"})
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "user"


# ===================== 应用配置管理测试 =====================

def test_app_config_requires_service_token(client):
    """无服务密钥不能获取应用配置"""
    resp = client.get("/app-config")
    assert resp.status_code == 401


def test_app_config_with_service_token(client):
    """有服务密钥可获取应用配置"""
    resp = client.get("/app-config", headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "mail_config" in data["config"]
    assert "features" in data["config"]
    assert "rules" in data["config"]


def test_admin_get_app_config(admin_client):
    """管理员可获取应用配置"""
    resp = admin_client.get("/admin/api/app-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "mail_config" in data["config"]
    assert "features" in data["config"]


def test_admin_update_mail_config(admin_client):
    """管理员可更新邮件配置"""
    resp = admin_client.put("/admin/api/mail-config", json={
        "enabled": True,
        "email": "test@example.com",
        "auth_code": "secret123",
        "imap_host": "imap.example.com",
        "subject_keywords": ["test"],
        "provinces": ["北京市"],
        "poll_interval_seconds": 1800,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["config"]["email"] == "test@example.com"


def test_admin_get_features(admin_client):
    """管理员可获取功能开关"""
    resp = admin_client.get("/admin/api/features")
    assert resp.status_code == 200
    data = resp.json()
    assert "file_merge" in data["features"]
    assert "mail_reader" in data["features"]


def test_admin_update_features(admin_client):
    """管理员可更新功能开关"""
    resp = admin_client.put("/admin/api/features", json={
        "file_merge": False,
        "mail_reader": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["features"]["file_merge"] is False
    assert data["features"]["mail_reader"] is True


def test_admin_list_rules(admin_client):
    """管理员可获取规则列表"""
    resp = admin_client.get("/admin/api/rules")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert "rules" in resp.json()


def test_admin_create_rule(admin_client):
    """管理员可创建规则"""
    resp = admin_client.post("/admin/api/rules", json={
        "name": "测试规则",
        "standard_headers": [
            {"name": "列A", "source_columns": ["col_a", "A"]}
        ],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["rule"]["name"] == "测试规则"
    assert len(data["rule"]["standard_headers"]) == 1


def test_admin_create_rule_empty_name(admin_client):
    """规则名不能为空"""
    resp = admin_client.post("/admin/api/rules", json={
        "name": "",
        "standard_headers": [{"name": "a", "source_columns": ["a"]}],
    })
    assert resp.status_code == 400


def test_admin_update_rule(admin_client):
    """管理员可编辑规则"""
    # 先创建
    create_resp = admin_client.post("/admin/api/rules", json={
        "name": "原规则",
        "standard_headers": [{"name": "列A", "source_columns": ["a"]}],
    })
    rule_id = create_resp.json()["rule"]["id"]
    # 再编辑
    resp = admin_client.put(f"/admin/api/rules/{rule_id}", json={
        "name": "改后规则",
        "standard_headers": [{"name": "列B", "source_columns": ["b"]}],
    })
    assert resp.status_code == 200
    assert resp.json()["rule"]["name"] == "改后规则"


def test_admin_delete_rule(admin_client):
    """管理员可删除规则"""
    create_resp = admin_client.post("/admin/api/rules", json={
        "name": "待删规则",
        "standard_headers": [{"name": "a", "source_columns": ["a"]}],
    })
    rule_id = create_resp.json()["rule"]["id"]
    resp = admin_client.delete(f"/admin/api/rules/{rule_id}")
    assert resp.status_code == 200
    # 确认已删除
    rules = admin_client.get("/admin/api/rules").json()["rules"]
    assert rule_id not in [r["id"] for r in rules]


def test_admin_delete_nonexistent_rule(admin_client):
    """删除不存在的规则返回 404"""
    resp = admin_client.delete("/admin/api/rules/nonexistent-id")
    assert resp.status_code == 404


def test_app_config_unauthenticated_admin_api(client):
    """无 admin session 不能访问应用配置管理 API"""
    assert client.get("/admin/api/app-config").status_code == 401
    assert client.put("/admin/api/mail-config", json={}).status_code == 401
    assert client.get("/admin/api/features").status_code == 401
    assert client.put("/admin/api/features", json={}).status_code == 401
    assert client.get("/admin/api/rules").status_code == 401
    assert client.post("/admin/api/rules", json={}).status_code == 401


# ===================== 用户功能权限测试 =====================

def test_login_returns_features(client):
    """登录响应包含 features 字段"""
    resp = client.post("/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "features" in data["user"]
    assert "file_merge" in data["user"]["features"]
    assert "mail_reader" in data["user"]["features"]
    assert "rule_management" in data["user"]["features"]


def test_verify_user_returns_features(client):
    """verify-user 响应包含 features"""
    resp = client.post("/verify-user", json={"username": "admin"}, headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert "features" in data["user"]
    assert data["user"]["features"]["file_merge"] is True


def test_load_config_auto_fills_features(tmp_path, monkeypatch):
    """旧配置无 features 字段时自动补全默认值"""
    cfg_file = tmp_path / "auth_config.json"
    old_cfg = {"users": [{"username": "test", "password": "x", "name": "T", "role": "user", "enabled": True}]}
    cfg_file.write_text(json.dumps(old_cfg), encoding="utf-8")
    monkeypatch.setattr(auth_service, "AUTH_CONFIG_FILE", str(cfg_file))
    cfg = load_config()
    assert "features" in cfg["users"][0]
    assert cfg["users"][0]["features"]["file_merge"] is True
    assert cfg["users"][0]["features"]["mail_reader"] is True
    assert cfg["users"][0]["features"]["rule_management"] is True


def test_admin_create_user_with_features(admin_client):
    """创建用户时指定功能权限"""
    resp = admin_client.post("/admin/api/users", json={
        "username": "limited", "password": "pw", "name": "受限用户",
        "role": "user", "enabled": True,
        "features": {"file_merge": True, "mail_reader": False, "rule_management": False}
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["features"]["file_merge"] is True
    assert data["user"]["features"]["mail_reader"] is False
    assert data["user"]["features"]["rule_management"] is False


def test_admin_create_user_default_features(admin_client):
    """创建用户时不指定 features，默认全部开启"""
    resp = admin_client.post("/admin/api/users", json={
        "username": "default_feat", "password": "pw", "name": "默认权限",
        "role": "user", "enabled": True
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["features"]["file_merge"] is True
    assert data["user"]["features"]["mail_reader"] is True


def test_admin_update_user_features(admin_client):
    """编辑用户功能权限"""
    resp = admin_client.put("/admin/api/users/user1", json={
        "features": {"file_merge": False, "mail_reader": False, "rule_management": True}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["features"]["file_merge"] is False
    assert data["user"]["features"]["mail_reader"] is False
    assert data["user"]["features"]["rule_management"] is True


def test_admin_get_user_features(admin_client):
    """获取指定用户的功能权限"""
    resp = admin_client.get("/admin/api/users/user1/features")
    assert resp.status_code == 200
    data = resp.json()
    assert "features" in data
    assert "file_merge" in data["features"]


def test_admin_update_features_standalone(admin_client):
    """通过独立接口更新用户功能权限"""
    resp = admin_client.put("/admin/api/users/user1/features", json={
        "file_merge": False, "mail_reader": True
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["features"]["file_merge"] is False
    assert data["features"]["mail_reader"] is True
    assert data["features"]["rule_management"] is True  # 未传的保持默认


def test_admin_get_features_nonexistent_user(admin_client):
    """获取不存在用户的功能权限返回 404"""
    resp = admin_client.get("/admin/api/users/nobody/features")
    assert resp.status_code == 404


def test_admin_update_features_nonexistent_user(admin_client):
    """更新不存在用户的功能权限返回 404"""
    resp = admin_client.put("/admin/api/users/nobody/features", json={"file_merge": False})
    assert resp.status_code == 404


def test_features_unauthenticated_admin_api(client):
    """未登录访问用户功能权限 API 返回 401"""
    assert client.get("/admin/api/users/user1/features").status_code == 401
    assert client.put("/admin/api/users/user1/features", json={"file_merge": False}).status_code == 401


def test_public_user_includes_features(client):
    """用户列表包含 features 字段"""
    resp = client.get("/users", headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200
    for u in resp.json()["users"]:
        assert "features" in u
        assert "file_merge" in u["features"]


# ===================== 单设备登录测试 =====================

def test_login_returns_login_token(client):
    """登录响应包含 login_token，且认证服务记录了设备绑定"""
    from auth_service import ACTIVE_LOGINS
    ACTIVE_LOGINS.clear()
    resp = client.post("/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "login_token" in data["user"]
    assert data["user"]["login_token"]
    # 认证服务记录了活跃登录（dict 含 token + login_time）
    assert "admin" in ACTIVE_LOGINS
    assert ACTIVE_LOGINS["admin"]["token"] == data["user"]["login_token"]


def test_second_login_refused_returns_409(client):
    """同一用户第二次登录被拒绝（不踢旧设备），返回 409"""
    from auth_service import ACTIVE_LOGINS
    ACTIVE_LOGINS.clear()
    # 第一次登录成功
    resp1 = client.post("/login", json={"username": "admin", "password": "admin123"})
    assert resp1.status_code == 200
    token1 = resp1.json()["user"]["login_token"]
    # 第二次登录应被拒绝
    resp2 = client.post("/login", json={"username": "admin", "password": "admin123"})
    assert resp2.status_code == 409
    assert "其他设备" in resp2.json()["detail"]
    # 旧设备 token 仍然保留（未被覆盖）
    assert ACTIVE_LOGINS["admin"]["token"] == token1


def test_logout_clears_device_binding(client):
    """用户退出后清除设备绑定，之后可以重新登录"""
    from auth_service import ACTIVE_LOGINS
    ACTIVE_LOGINS.clear()
    # 登录
    client.post("/login", json={"username": "admin", "password": "admin123"})
    assert "admin" in ACTIVE_LOGINS
    # 退出（调用服务间 /logout）
    resp = client.post("/logout", json={"username": "admin"},
                       headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200
    # 绑定已清除
    assert "admin" not in ACTIVE_LOGINS
    # 再次登录应成功
    resp2 = client.post("/login", json={"username": "admin", "password": "admin123"})
    assert resp2.status_code == 200


def test_logout_requires_service_token(client):
    """退出接口需要服务密钥"""
    resp = client.post("/logout", json={"username": "admin"})
    assert resp.status_code == 401


def test_logout_nonexistent_user_ok(client):
    """退出不存在的用户绑定也返回成功"""
    from auth_service import ACTIVE_LOGINS
    ACTIVE_LOGINS.clear()
    resp = client.post("/logout", json={"username": "nobody"},
                       headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200


def test_admin_unbind_device(admin_client):
    """管理员强制解绑后，用户可重新登录"""
    from auth_service import ACTIVE_LOGINS
    ACTIVE_LOGINS.clear()
    # 用户登录
    client = admin_client
    client.post("/login", json={"username": "user1", "password": "user123"})
    assert "user1" in ACTIVE_LOGINS
    # 管理员解绑
    resp = client.post("/admin/api/users/user1/unbind-device")
    assert resp.status_code == 200
    assert "user1" not in ACTIVE_LOGINS
    # 现在可以重新登录
    resp2 = client.post("/login", json={"username": "user1", "password": "user123"})
    assert resp2.status_code == 200


def test_admin_device_status_bound(admin_client):
    """查看已绑定设备的用户状态"""
    from auth_service import ACTIVE_LOGINS
    ACTIVE_LOGINS.clear()
    client = admin_client
    client.post("/login", json={"username": "user1", "password": "user123"})
    resp = client.get("/admin/api/users/user1/device-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["bound"] is True
    assert data["remaining_seconds"] > 0


def test_admin_device_status_free(admin_client):
    """查看未绑定设备的用户状态"""
    from auth_service import ACTIVE_LOGINS
    ACTIVE_LOGINS.clear()
    resp = admin_client.get("/admin/api/users/user1/device-status")
    assert resp.status_code == 200
    assert resp.json()["bound"] is False


def test_verify_user_no_login_token_check(client):
    """verify-user 不再校验 login_token，仅返回用户启用状态"""
    from auth_service import ACTIVE_LOGINS
    ACTIVE_LOGINS.clear()
    resp = client.post("/verify-user", json={"username": "admin"},
                       headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200
    assert resp.json()["user"]["enabled"] is True


def test_verify_user_ignores_login_token_field(client):
    """verify-user 即使传了 login_token 也不做设备校验（向后兼容）"""
    from auth_service import ACTIVE_LOGINS
    ACTIVE_LOGINS.clear()
    client.post("/login", json={"username": "admin", "password": "admin123"})
    # 传任意 token，不返回 409
    resp = client.post("/verify-user", json={"username": "admin", "login_token": "wrong"},
                       headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200


# ===================== 软件升级管理测试 =====================

def test_update_check_no_version_set(client):
    """未设置版本时返回空版本号"""
    import auth_service; UPLOAD_DIR = auth_service.UPLOAD_DIR; VERSION_INFO_FILE = auth_service.VERSION_INFO_FILE
    # 清理
    if os.path.exists(VERSION_INFO_FILE):
        os.remove(VERSION_INFO_FILE)
    resp = client.get("/update/check", headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["version"] == ""
    assert data["has_file"] is False


def test_update_check_requires_service_token(client):
    """检查更新需要服务密钥"""
    resp = client.get("/update/check")
    assert resp.status_code == 401


def test_update_download_no_file(client):
    """无文件时下载返回 404"""
    from auth_service import VERSION_INFO_FILE
    if os.path.exists(VERSION_INFO_FILE):
        os.remove(VERSION_INFO_FILE)
    resp = client.get("/update/download", headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 404


def test_update_download_requires_service_token(client):
    """下载需要服务密钥"""
    resp = client.get("/update/download")
    assert resp.status_code == 401


def test_admin_upload_exe_success(admin_client):
    """管理员上传 exe 成功"""
    import auth_service; UPLOAD_DIR = auth_service.UPLOAD_DIR; VERSION_INFO_FILE = auth_service.VERSION_INFO_FILE
    # 准备一个假 exe（>1MB）
    fake_exe = b"MZ" + b"\x00" * 1100000
    resp = admin_client.post(
        "/admin/api/upload-exe",
        data={"version": "v9.9.9", "notes": "测试版本"},
        files={"file": ("test_update.exe", fake_exe, "application/octet-stream")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["info"]["version"] == "v9.9.9"
    assert data["info"]["filename"] == "test_update.exe"
    assert data["info"]["size"] == len(fake_exe)
    # 文件已保存
    assert os.path.exists(os.path.join(UPLOAD_DIR, "test_update.exe"))
    # 版本信息已写入
    # 清理
    if os.path.exists(os.path.join(UPLOAD_DIR, "test_update.exe")):
        os.remove(os.path.join(UPLOAD_DIR, "test_update.exe"))
    if os.path.exists(VERSION_INFO_FILE):
        os.remove(VERSION_INFO_FILE)


def test_admin_upload_exe_no_version(admin_client):
    """上传不填版本号返回 400"""
    fake_exe = b"MZ" + b"\x00" * 1100000
    resp = admin_client.post(
        "/admin/api/upload-exe",
        data={"version": "", "notes": ""},
        files={"file": ("test.exe", fake_exe, "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_admin_upload_exe_too_small(admin_client):
    """上传过小文件返回 400"""
    fake_exe = b"MZ" + b"\x00" * 100
    resp = admin_client.post(
        "/admin/api/upload-exe",
        data={"version": "v1.0.0", "notes": ""},
        files={"file": ("small.exe", fake_exe, "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_admin_upload_then_check_and_download(admin_client, client):
    """完整流程：上传 → 检查 → 下载"""
    import auth_service; UPLOAD_DIR = auth_service.UPLOAD_DIR; VERSION_INFO_FILE = auth_service.VERSION_INFO_FILE
    fake_exe = b"MZ" + b"\x00" * 1100000
    # 上传
    admin_client.post(
        "/admin/api/upload-exe",
        data={"version": "v2.0.0", "notes": "完整流程测试"},
        files={"file": ("flow_test.exe", fake_exe, "application/octet-stream")},
    )
    # 检查
    resp = client.get("/update/check", headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "v2.0.0"
    assert data["has_file"] is True
    assert data["notes"] == "完整流程测试"
    # 下载
    resp2 = client.get("/update/download", headers={"X-Service-Token": "lx-internal-service-token"})
    assert resp2.status_code == 200
    assert resp2.content == fake_exe
    # 清理
    if os.path.exists(os.path.join(UPLOAD_DIR, "flow_test.exe")):
        os.remove(os.path.join(UPLOAD_DIR, "flow_test.exe"))
    if os.path.exists(VERSION_INFO_FILE):
        os.remove(VERSION_INFO_FILE)


def test_admin_get_update_info(admin_client):
    """管理员获取版本信息"""
    from auth_service import VERSION_INFO_FILE
    if os.path.exists(VERSION_INFO_FILE):
        os.remove(VERSION_INFO_FILE)
    resp = admin_client.get("/admin/api/update-info")
    assert resp.status_code == 200
    data = resp.json()
    assert "current" in data
    assert "files" in data


def test_admin_delete_update_info(admin_client):
    """管理员清除版本信息"""
    from auth_service import VERSION_INFO_FILE
    # 先设置一个
    admin_client.post(
        "/admin/api/upload-exe",
        data={"version": "v3.0.0", "notes": "test"},
        files={"file": ("del_test.exe", b"MZ" + b"\x00" * 1100000, "application/octet-stream")},
    )
    # 清除
    resp = admin_client.delete("/admin/api/update-info")
    assert resp.status_code == 200
    # 验证已清除
    info = json.loads(open(VERSION_INFO_FILE).read()) if os.path.exists(VERSION_INFO_FILE) else {}
    assert info.get("version", "") == ""
    # 清理文件
    import auth_service; UPLOAD_DIR = auth_service.UPLOAD_DIR
    fp = os.path.join(UPLOAD_DIR, "del_test.exe")
    if os.path.exists(fp):
        os.remove(fp)


def test_admin_delete_update_file(admin_client):
    """管理员删除指定更新文件"""
    import auth_service; UPLOAD_DIR = auth_service.UPLOAD_DIR
    fake_exe = b"MZ" + b"\x00" * 1100000
    admin_client.post(
        "/admin/api/upload-exe",
        data={"version": "v4.0.0", "notes": ""},
        files={"file": ("delfile.exe", fake_exe, "application/octet-stream")},
    )
    assert os.path.exists(os.path.join(UPLOAD_DIR, "delfile.exe"))
    resp = admin_client.delete("/admin/api/update-file/delfile.exe")
    assert resp.status_code == 200
    assert not os.path.exists(os.path.join(UPLOAD_DIR, "delfile.exe"))


def test_update_api_unauthenticated(client):
    """未登录访问上传接口返回 401"""
    resp = client.post(
        "/admin/api/upload-exe",
        data={"version": "v1.0.0", "notes": ""},
        files={"file": ("test.exe", b"MZ" + b"\x00" * 1100000, "application/octet-stream")},
    )
    assert resp.status_code == 401


import os
