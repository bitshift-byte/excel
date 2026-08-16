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
    ADMIN_SESSIONS.clear()
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


def test_list_users(client):
    resp = client.get("/users")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["users"]) == 4
    assert data["users"][0]["username"] == "admin"
    # 不应返回密码
    for u in data["users"]:
        assert "password" not in u


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
