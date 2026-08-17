"""
省份隔离测试
- auth_service.py: POST /user-config, GET/PUT /admin/api/users/{username}/provinces
- auth.py: get_user_provinces(username)
- routers/mail.py: GET /api/mail/config 返回用户省份
- routers/auth.py: GET /api/sync 返回用户省份
"""
import json
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ===================== auth_service.py 测试 =====================

import auth_service
from auth_service import app as auth_app, ADMIN_SESSIONS, ADMIN_COOKIE

TEST_CONFIG = {
    "users": [
        {"username": "admin", "password": "admin123", "name": "管理员", "role": "admin", "enabled": True},
        {"username": "user1", "password": "user123", "name": "用户一", "role": "user", "enabled": True},
        {"username": "user2", "password": "user123", "name": "用户二", "role": "user", "enabled": True},
    ],
}

SERVICE_HEADER = {"X-Service-Token": "lx-internal-service-token"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg_file = tmp_path / "auth_config.json"
    cfg_file.write_text(json.dumps(TEST_CONFIG, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(auth_service, "AUTH_CONFIG_FILE", str(cfg_file))
    app_cfg_file = tmp_path / "app_config.json"
    monkeypatch.setattr(auth_service, "APP_CONFIG_FILE", str(app_cfg_file))
    tmp_updates = tmp_path / "updates"
    tmp_updates.mkdir(exist_ok=True)
    monkeypatch.setattr(auth_service, "UPLOAD_DIR", str(tmp_updates))
    monkeypatch.setattr(auth_service, "VERSION_INFO_FILE", str(tmp_updates / "version_info.json"))
    ADMIN_SESSIONS.clear()
    auth_service.ACTIVE_LOGINS.clear()
    return TestClient(auth_app)


@pytest.fixture
def admin_client(client):
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    token = resp.cookies.get(ADMIN_COOKIE)
    client.cookies.set(ADMIN_COOKIE, token)
    return client


# --- POST /user-config ---

def test_user_config_requires_service_token(client):
    """POST /user-config 无服务密钥 → 401"""
    resp = client.post("/user-config", json={"username": "user1"})
    assert resp.status_code == 401


def test_user_config_empty_username(client):
    """POST /user-config 空用户名 → 400"""
    resp = client.post("/user-config", json={"username": ""}, headers=SERVICE_HEADER)
    assert resp.status_code == 400


def test_user_config_returns_empty_for_user_without_assignment(client):
    """未分配省份的用户 → 空列表"""
    resp = client.post("/user-config", json={"username": "user1"}, headers=SERVICE_HEADER)
    assert resp.status_code == 200
    assert resp.json()["provinces"] == []


def test_user_config_returns_assigned_provinces(client, admin_client):
    """已分配省份的用户 → 返回省份列表"""
    admin_client.put("/admin/api/users/user1/provinces", json={"provinces": ["上海", "杭州"]})
    resp = client.post("/user-config", json={"username": "user1"}, headers=SERVICE_HEADER)
    assert resp.status_code == 200
    assert resp.json()["provinces"] == ["上海", "杭州"]


def test_user_config_isolation(client, admin_client):
    """user1 和 user2 分配不同省份，互不影响"""
    admin_client.put("/admin/api/users/user1/provinces", json={"provinces": ["上海"]})
    admin_client.put("/admin/api/users/user2/provinces", json={"provinces": ["杭州", "南京"]})

    resp1 = client.post("/user-config", json={"username": "user1"}, headers=SERVICE_HEADER)
    resp2 = client.post("/user-config", json={"username": "user2"}, headers=SERVICE_HEADER)
    assert resp1.json()["provinces"] == ["上海"]
    assert resp2.json()["provinces"] == ["杭州", "南京"]


# --- GET /admin/api/users/{username}/provinces ---

def test_admin_get_user_provinces(admin_client):
    """管理员获取用户省份 → 200"""
    resp = admin_client.get("/admin/api/users/user1/provinces")
    assert resp.status_code == 200
    assert resp.json()["provinces"] == []


def test_get_user_provinces_unauthenticated(client):
    """非管理员 → 401"""
    resp = client.get("/admin/api/users/user1/provinces")
    assert resp.status_code == 401


# --- PUT /admin/api/users/{username}/provinces ---

def test_admin_assign_user_provinces(admin_client):
    """管理员分配省份 → 200，持久化"""
    resp = admin_client.put("/admin/api/users/user1/provinces", json={"provinces": ["上海", "杭州"]})
    assert resp.status_code == 200
    assert resp.json()["provinces"] == ["上海", "杭州"]
    # 确认持久化
    resp2 = admin_client.get("/admin/api/users/user1/provinces")
    assert resp2.json()["provinces"] == ["上海", "杭州"]


def test_assign_user_provinces_unauthenticated(client):
    """非管理员 → 401"""
    resp = client.put("/admin/api/users/user1/provinces", json={"provinces": ["上海"]})
    assert resp.status_code == 401


def test_assign_user_provinces_nonexistent_user(admin_client):
    """不存在的用户 → 404"""
    resp = admin_client.put("/admin/api/users/nobody/provinces", json={"provinces": ["上海"]})
    assert resp.status_code == 404


def test_assign_user_provinces_empty_list(admin_client):
    """空列表 → 清空用户省份"""
    admin_client.put("/admin/api/users/user1/provinces", json={"provinces": ["上海"]})
    resp = admin_client.put("/admin/api/users/user1/provinces", json={"provinces": []})
    assert resp.status_code == 200
    assert resp.json()["provinces"] == []


# ===================== auth.py 测试 =====================

import app as app_module
from app import app
import state
import config
import auth
from state import SESSIONS
from config import SESSION_COOKIE


@pytest.fixture
def desktop_client(tmp_path, monkeypatch):
    """TestClient for desktop app"""
    monkeypatch.setattr(state, "USERS", {
        "admin": {"username": "admin", "name": "管理员", "role": "admin", "features": {}},
        "user1": {"username": "user1", "name": "用户一", "role": "user", "features": {}},
        "user2": {"username": "user2", "name": "用户二", "role": "user", "features": {}},
    })
    SESSIONS.clear()
    state.SESSION_LAST_CHECK.clear()
    monkeypatch.setattr(auth, "verify_user_status_with_auth_service", lambda username: (True, None))
    return TestClient(app)


def _login_as(client, username):
    token = f"test-token-{username}"
    SESSIONS[token] = {"username": username}
    state.SESSION_LAST_CHECK[token] = time.time()
    client.cookies.set(SESSION_COOKIE, token)
    return token


def test_get_user_provinces_sends_username():
    """get_user_provinces 应在 POST body 中带上 username"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "provinces": ["上海", "杭州"]}
    with patch("auth.httpx.post", return_value=mock_resp) as mock_post:
        result = auth.get_user_provinces("user1")
    call_kwargs = mock_post.call_args
    sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert sent_json["username"] == "user1"
    assert result == ["上海", "杭州"]


def test_get_user_provinces_returns_empty_on_failure():
    """网络异常 → 空列表"""
    with patch("auth.httpx.post", side_effect=Exception("connection refused")):
        result = auth.get_user_provinces("user1")
    assert result == []


def test_get_user_provinces_returns_empty_on_non_200():
    """非 200 → 空列表"""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.json.return_value = {"status": "error"}
    with patch("auth.httpx.post", return_value=mock_resp):
        result = auth.get_user_provinces("user1")
    assert result == []


# --- GET /api/mail/config ---

def test_mail_config_returns_user_provinces(desktop_client):
    """GET /api/mail/config 应返回用户分配的省份"""
    _login_as(desktop_client, "user1")
    with patch("auth.get_user_provinces", return_value=["上海", "杭州"]):
        resp = desktop_client.get("/api/mail/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["config"]["provinces"] == ["上海", "杭州"]


def test_mail_config_user2_gets_different_provinces(desktop_client):
    """user2 获取不同的省份"""
    _login_as(desktop_client, "user2")
    with patch("auth.get_user_provinces", return_value=["南京"]):
        resp = desktop_client.get("/api/mail/config")
    assert resp.status_code == 200
    assert resp.json()["config"]["provinces"] == ["南京"]


def test_mail_config_unauthenticated_returns_401(desktop_client):
    """未登录 → 401"""
    resp = desktop_client.get("/api/mail/config")
    assert resp.status_code == 401


# --- GET /api/sync ---

def test_sync_returns_user_provinces(desktop_client):
    """GET /api/sync 应返回用户省份"""
    _login_as(desktop_client, "user1")
    with patch("auth.get_mail_config", return_value={"enabled": False, "provinces": []}), \
         patch("auth.get_user_provinces", return_value=["上海"]):
        resp = desktop_client.get("/api/sync")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mail_config"]["provinces"] == ["上海"]
