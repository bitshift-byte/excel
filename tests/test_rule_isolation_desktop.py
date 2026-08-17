"""
桌面端后端规则隔离测试
- auth.get_remote_rules(username): 发送 username 到 POST /rules
- auth.get_all_rules(username): 内置规则 + 用户分配规则
- routers/auth.py GET /api/rules: 按 session 用户隔离
- routers/merge.py POST /api/analyze: 传递 username 给 get_all_rules
"""
import io
import time
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import app as app_module
from app import app
import state
import config
import auth
from state import SESSIONS
from config import SESSION_COOKIE


BUILTIN_RULE = {
    "id": "_builtin_default",
    "name": "联合利华标准34列",
    "builtin": True,
    "standard_headers": [{"name": "订单号", "source_columns": ["订单号", "order_no"]}],
}


def _mock_remote_rules_response(rules, status_code=200):
    """构造 httpx.post 的 mock response"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {"status": "success", "rules": rules}
    return mock_resp


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with monkeypatched state.
    Mocks verify_user_status_with_auth_service to avoid network calls."""
    monkeypatch.setattr(state, "USERS", {
        "admin": {"username": "admin", "name": "管理员", "role": "admin", "features": {}},
        "user1": {"username": "user1", "name": "用户一", "role": "user", "features": {}},
        "user2": {"username": "user2", "name": "用户二", "role": "user", "features": {}},
    })
    SESSIONS.clear()
    state.SESSION_LAST_CHECK.clear()
    # Mock verify_user_status_with_auth_service to avoid remote auth service calls
    monkeypatch.setattr(auth, "verify_user_status_with_auth_service", lambda username: (True, None))
    return TestClient(app)


def _login_as(client, username):
    """Helper: set session cookie for a user"""
    token = f"test-token-{username}"
    SESSIONS[token] = {"username": username}
    # Set last check to now so middleware skips the verify call
    state.SESSION_LAST_CHECK[token] = time.time()
    client.cookies.set(SESSION_COOKIE, token)
    return token


# ===================== auth.get_remote_rules 测试 =====================

def test_get_remote_rules_sends_username():
    """get_remote_rules 应在 POST body 中带上 username"""
    mock_resp = _mock_remote_rules_response([BUILTIN_RULE])
    with patch("auth.httpx.post", return_value=mock_resp) as mock_post:
        result = auth.get_remote_rules("user1")
    call_kwargs = mock_post.call_args
    sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert sent_json["username"] == "user1"
    assert result == [BUILTIN_RULE]


def test_get_remote_rules_empty_username():
    """get_remote_rules 空用户名 → 服务端返回 400，本地返回 []"""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"status": "error", "detail": "用户名不能为空"}
    with patch("auth.httpx.post", return_value=mock_resp):
        result = auth.get_remote_rules("")
    assert result == []


def test_get_remote_rules_returns_empty_on_network_error():
    """网络异常时返回空列表"""
    with patch("auth.httpx.post", side_effect=Exception("connection refused")):
        result = auth.get_remote_rules("user1")
    assert result == []


def test_get_remote_rules_returns_empty_on_non_200():
    """非 200 状态码返回空列表"""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.json.return_value = {"status": "error"}
    with patch("auth.httpx.post", return_value=mock_resp):
        result = auth.get_remote_rules("user1")
    assert result == []


# ===================== auth.get_all_rules 测试 =====================

def test_get_all_rules_with_builtin_from_remote():
    """远程已包含内置规则 → 直接返回远程列表"""
    rules_with_builtin = [
        BUILTIN_RULE,
        {"id": "r_abc", "name": "自定义规则", "standard_headers": []},
    ]
    with patch("auth.get_remote_rules", return_value=rules_with_builtin):
        result = auth.get_all_rules("user1")
    assert result == rules_with_builtin
    assert result[0]["id"] == "_builtin_default"
    assert len(result) == 2


def test_get_all_rules_without_builtin_from_remote():
    """远程不含内置规则 → 前置注入内置规则"""
    rules_without_builtin = [
        {"id": "r_abc", "name": "自定义规则", "standard_headers": []},
    ]
    with patch("auth.get_remote_rules", return_value=rules_without_builtin):
        result = auth.get_all_rules("user1")
    assert result[0]["id"] == "_builtin_default"
    assert len(result) == 2
    assert result[1]["id"] == "r_abc"


def test_get_all_rules_empty_remote():
    """远程返回空 → 只有内置规则"""
    with patch("auth.get_remote_rules", return_value=[]):
        result = auth.get_all_rules("user1")
    assert len(result) == 1
    assert result[0]["id"] == "_builtin_default"


def test_get_all_rules_different_users():
    """不同用户获取不同规则（隔离验证）"""
    user1_rules = [
        BUILTIN_RULE,
        {"id": "r_a", "name": "规则A", "standard_headers": []},
    ]
    user2_rules = [BUILTIN_RULE]

    def mock_remote(username):
        if username == "user1":
            return user1_rules
        return user2_rules

    with patch("auth.get_remote_rules", side_effect=mock_remote):
        result_user1 = auth.get_all_rules("user1")
        result_user2 = auth.get_all_rules("user2")

    assert len(result_user1) == 2
    assert result_user1[1]["id"] == "r_a"
    assert len(result_user2) == 1
    assert result_user2[0]["id"] == "_builtin_default"


# ===================== routers/auth.py GET /api/rules 测试 =====================

def test_api_rules_passes_username(client):
    """GET /api/rules 应传递当前用户 username 给 get_all_rules"""
    _login_as(client, "user1")
    mock_rules = [
        BUILTIN_RULE,
        {"id": "r_abc", "name": "用户1的规则", "standard_headers": []},
    ]
    with patch("auth.get_all_rules", return_value=mock_rules) as mock_fn:
        resp = client.get("/api/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["rules"]) == 2
    mock_fn.assert_called_once_with("user1")


def test_api_rules_unauthenticated_returns_401(client):
    """未登录 → 401"""
    resp = client.get("/api/rules")
    assert resp.status_code == 401


def test_api_rules_user2_gets_different_rules(client):
    """user2 登录 → 只看到内置规则（隔离验证）"""
    _login_as(client, "user2")
    mock_rules = [BUILTIN_RULE]
    with patch("auth.get_all_rules", return_value=mock_rules) as mock_fn:
        resp = client.get("/api/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rules"]) == 1
    assert data["rules"][0]["id"] == "_builtin_default"
    mock_fn.assert_called_once_with("user2")


def test_api_rules_admin_gets_all_rules(client):
    """admin 登录 → 获取管理员分配的规则"""
    _login_as(client, "admin")
    mock_rules = [
        BUILTIN_RULE,
        {"id": "r_admin", "name": "管理员规则", "standard_headers": []},
    ]
    with patch("auth.get_all_rules", return_value=mock_rules) as mock_fn:
        resp = client.get("/api/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rules"]) == 2
    mock_fn.assert_called_once_with("admin")
