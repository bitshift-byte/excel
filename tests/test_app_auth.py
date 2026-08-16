"""
app.py 认证流程测试
- POST /api/login：正确用户名密码 → 创建 session + set cookie；错误 → 401
- AuthMiddleware：未登录访问 → 重定向 /login；有 session → 正常通过
- POST /api/logout：清除 session
"""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

import app as app_module
from app import app, SESSIONS, SESSION_COOKIE


def _mock_auth_response(status_code=200, json_body=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_body or {"status": "success"}
    return mock_resp


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "USERS", {
        "admin": {"username": "admin", "name": "管理员", "role": "admin"},
        "user1": {"username": "user1", "name": "用户一", "role": "user"},
    })
    SESSIONS.clear()
    return TestClient(app)


def test_login_success_creates_session(client):
    mock_resp = _mock_auth_response(200, {
        "status": "success",
        "user": {"username": "admin", "name": "管理员", "role": "admin", "login_token": "lt-001", "features": {}},
    })
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        resp = client.post("/api/login", json={"username": "admin", "password": "admin123"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["user"]["username"] == "admin"
    assert SESSION_COOKIE in resp.cookies


def test_login_wrong_password_returns_401(client):
    mock_resp = _mock_auth_response(401, {"status": "error", "detail": "用户名或密码错误"})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        resp = client.post("/api/login", json={"username": "admin", "password": "wrong"})

    assert resp.status_code == 401
    assert "用户名或密码错误" in resp.json()["detail"]


def test_login_empty_fields(client):
    resp = client.post("/api/login", json={"username": "", "password": ""})
    assert resp.status_code == 400


def test_logout_clears_session(client):
    SESSIONS["test-token"] = {"username": "admin", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "test-token")
    resp = client.post("/api/logout")
    assert resp.status_code == 200
    assert "test-token" not in SESSIONS


def test_auth_middleware_unauthenticated_redirects(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


def test_auth_middleware_unauthenticated_api_returns_401(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401


def test_auth_middleware_authenticated_passes(client):
    SESSIONS["test-token"] = {"username": "admin", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "test-token")
    resp = client.get("/api/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["user"]["username"] == "admin"


def test_login_page_accessible_without_auth(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_send_code_endpoint_removed(client):
    """确认 /api/send-code 已被移除"""
    resp = client.post("/api/send-code", json={"phone": "123"})
    assert resp.status_code == 401


# ===================== 越权防护测试 =====================

def test_rules_crud_removed_from_app(client):
    """规则 CRUD 已移至认证服务，桌面应用不应有 POST/PUT/DELETE /api/rules"""
    SESSIONS["admin-token"] = {"username": "admin", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "admin-token")
    # POST should return 405 (method not allowed, endpoint removed)
    resp = client.post("/api/rules", json={"name": "test", "standard_headers": []})
    assert resp.status_code == 405
    # PUT should return 404 or 405 (endpoint removed)
    resp2 = client.put("/api/rules/some-id", json={"name": "test", "standard_headers": []})
    assert resp2.status_code in (404, 405)
    # DELETE should return 404 or 405 (endpoint removed)
    resp3 = client.delete("/api/rules/some-id")
    assert resp3.status_code in (404, 405)


def test_mail_config_put_removed_from_app(client):
    """邮件配置 PUT 已移至认证服务，桌面应用不应有 PUT /api/mail/config"""
    SESSIONS["admin-token"] = {"username": "admin", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "admin-token")
    resp = client.put("/api/mail/config", json={"enabled": False})
    assert resp.status_code == 405


def test_mail_start_requires_admin(client):
    """普通用户不能启动邮件后台"""
    SESSIONS["user-token"] = {"username": "user1", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "user-token")
    resp = client.post("/api/mail/start")
    assert resp.status_code == 403


def test_mail_stop_requires_admin(client):
    """普通用户不能停止邮件后台"""
    SESSIONS["user-token"] = {"username": "user1", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "user-token")
    resp = client.post("/api/mail/stop")
    assert resp.status_code == 403


def test_mail_run_requires_admin(client):
    """普通用户不能手动运行邮件"""
    SESSIONS["user-token"] = {"username": "user1", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "user-token")
    resp = client.post("/api/mail/run", json={})
    assert resp.status_code == 403


def test_rules_view_allowed_for_user(client):
    """普通用户可以查看规则列表"""
    SESSIONS["user-token"] = {"username": "user1", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "user-token")
    resp = client.get("/api/rules")
    assert resp.status_code == 200


def test_users_list_requires_admin(client):
    """普通用户不能查看用户列表"""
    SESSIONS["user-token"] = {"username": "user1", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "user-token")
    resp = client.get("/api/users")
    assert resp.status_code == 403


def test_users_list_admin_ok(client):
    """管理员可以查看用户列表"""
    SESSIONS["admin-token"] = {"username": "admin", "login_token": "test-token"}
    client.cookies.set(SESSION_COOKIE, "admin-token")
    resp = client.get("/api/users")
    assert resp.status_code == 200
