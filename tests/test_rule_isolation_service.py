"""
auth_service 规则隔离（rule isolation）单元测试

覆盖云侧认证服务的规则分配与按用户隔离逻辑：
- POST /rules                      供桌面应用按用户获取规则列表（需服务密钥）
- GET  /admin/api/users/{u}/rules  管理员查看用户已分配规则
- PUT  /admin/api/users/{u}/rules  管理员分配规则给用户
- POST /admin/api/rules            管理员新增规则
- DELETE /admin/api/rules/{id}     管理员删除规则（并清理用户映射）

测试模式与 test_auth_service.py 保持一致。
"""
import json
import pytest
from fastapi.testclient import TestClient

import auth_service
from auth_service import app, ADMIN_SESSIONS, ADMIN_COOKIE

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
    # IMPORTANT: Also monkeypatch APP_CONFIG_FILE to a temp file for rule isolation tests
    app_cfg_file = tmp_path / "app_config.json"
    monkeypatch.setattr(auth_service, "APP_CONFIG_FILE", str(app_cfg_file))
    tmp_updates = tmp_path / "updates"
    tmp_updates.mkdir(exist_ok=True)
    monkeypatch.setattr(auth_service, "UPLOAD_DIR", str(tmp_updates))
    monkeypatch.setattr(auth_service, "VERSION_INFO_FILE", str(tmp_updates / "version_info.json"))
    ADMIN_SESSIONS.clear()
    auth_service.ACTIVE_LOGINS.clear()
    return TestClient(app)


@pytest.fixture
def admin_client(client):
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    token = resp.cookies.get(ADMIN_COOKIE)
    client.cookies.set(ADMIN_COOKIE, token)
    return client


# ===================== 辅助函数 =====================

def _create_rule(admin_client, name="测试规则"):
    """创建一条自定义规则，返回 rule_id。"""
    resp = admin_client.post("/admin/api/rules", json={
        "name": name,
        "standard_headers": [{"name": "列A", "source_columns": ["col_a"]}],
    })
    assert resp.status_code == 201
    return resp.json()["rule"]["id"]


def _rule_ids(rules):
    """从规则列表中提取 id 集合。"""
    return {r["id"] for r in rules}


# ===================== POST /rules（服务端按用户取规则） =====================

def test_post_rules_requires_service_token(client):
    """没有 X-Service-Token 时 POST /rules 返回 401。"""
    resp = client.post("/rules", json={"username": "user1"})
    assert resp.status_code == 401


def test_post_rules_empty_username(client):
    """空用户名 POST /rules 返回 400。"""
    resp = client.post("/rules", json={"username": ""}, headers=SERVICE_HEADER)
    assert resp.status_code == 400


def test_post_rules_returns_builtin_only_for_user_without_assignments(admin_client, client):
    """user1 被分配了自定义规则，但 user2 未被分配 → user2 仅拿到内置规则。"""
    rule_a = _create_rule(admin_client, name="规则A")
    # 把 rule_a 分配给 user1
    resp = admin_client.put("/admin/api/users/user1/rules", json={"rule_ids": [rule_a]})
    assert resp.status_code == 200

    # user2 没有 assignment
    resp = client.post("/rules", json={"username": "user2"}, headers=SERVICE_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    ids = _rule_ids(data["rules"])
    assert ids == {"_builtin_default"}
    # 内置规则确实在内且标记 builtin
    assert data["rules"][0]["builtin"] is True


def test_post_rules_returns_builtin_plus_assigned(admin_client, client):
    """user1 被分配两条自定义规则 → 返回 内置 + A + B。"""
    rule_a = _create_rule(admin_client, name="规则A")
    rule_b = _create_rule(admin_client, name="规则B")
    resp = admin_client.put("/admin/api/users/user1/rules", json={"rule_ids": [rule_a, rule_b]})
    assert resp.status_code == 200

    resp = client.post("/rules", json={"username": "user1"}, headers=SERVICE_HEADER)
    assert resp.status_code == 200
    ids = _rule_ids(resp.json()["rules"])
    assert ids == {"_builtin_default", rule_a, rule_b}


def test_post_rules_unknown_user(client):
    """未知用户 POST /rules 仅返回内置规则。"""
    resp = client.post("/rules", json={"username": "nobody"}, headers=SERVICE_HEADER)
    assert resp.status_code == 200
    ids = _rule_ids(resp.json()["rules"])
    assert ids == {"_builtin_default"}


# ===================== GET /admin/api/users/{username}/rules =====================

def test_get_user_rules_admin_ok(admin_client):
    """管理员查看用户规则分配，未分配时返回空列表。"""
    resp = admin_client.get("/admin/api/users/user1/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["rule_ids"] == []


def test_get_user_rules_unauthenticated(client):
    """未登录访问用户规则接口返回 401。"""
    resp = client.get("/admin/api/users/user1/rules")
    assert resp.status_code == 401


# ===================== PUT /admin/api/users/{username}/rules =====================

def test_assign_user_rules_admin_ok(admin_client):
    """管理员分配规则后 GET 确认。"""
    rule_abc = _create_rule(admin_client, name="规则ABC")
    resp = admin_client.put("/admin/api/users/user1/rules", json={"rule_ids": [rule_abc]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["rule_ids"] == [rule_abc]

    # GET 确认持久化
    resp = admin_client.get("/admin/api/users/user1/rules")
    assert resp.status_code == 200
    assert resp.json()["rule_ids"] == [rule_abc]


def test_assign_user_rules_unauthenticated(client):
    """未登录分配规则返回 401。"""
    resp = client.put("/admin/api/users/user1/rules", json={"rule_ids": ["r_abc"]})
    assert resp.status_code == 401


def test_assign_user_rules_nonexistent_user(admin_client):
    """给不存在的用户分配规则返回 404。"""
    resp = admin_client.put("/admin/api/users/nobody/rules", json={"rule_ids": ["r_abc"]})
    assert resp.status_code == 404


def test_assign_user_rules_filters_builtin(admin_client):
    """分配时混入 _builtin_default → 内置规则被过滤，仅保存自定义规则。"""
    rule_abc = _create_rule(admin_client, name="规则ABC")
    resp = admin_client.put(
        "/admin/api/users/user1/rules",
        json={"rule_ids": [rule_abc, "_builtin_default"]},
    )
    assert resp.status_code == 200
    assert resp.json()["rule_ids"] == [rule_abc]

    # GET 确认 _builtin_default 未被写入
    resp = admin_client.get("/admin/api/users/user1/rules")
    assert resp.status_code == 200
    assert resp.json()["rule_ids"] == [rule_abc]


# ===================== DELETE /admin/api/rules/{rule_id} 清理用户映射 =====================

def test_delete_rule_cleans_user_rules(admin_client, client):
    """删除规则后，用户已分配的 rule_id 应被清除。"""
    rule_id = _create_rule(admin_client, name="待删除规则")
    # 分配给 user1
    admin_client.put("/admin/api/users/user1/rules", json={"rule_ids": [rule_id]})

    # 确认分配生效
    resp = admin_client.get("/admin/api/users/user1/rules")
    assert resp.json()["rule_ids"] == [rule_id]

    # 删除规则
    resp = admin_client.delete(f"/admin/api/rules/{rule_id}")
    assert resp.status_code == 200

    # 用户规则映射中该 rule_id 应已清除
    resp = admin_client.get("/admin/api/users/user1/rules")
    assert resp.status_code == 200
    assert rule_id not in resp.json()["rule_ids"]
    assert resp.json()["rule_ids"] == []

    # POST /rules 也不再返回该规则（仅剩内置）
    resp = client.post("/rules", json={"username": "user1"}, headers=SERVICE_HEADER)
    assert resp.status_code == 200
    assert _rule_ids(resp.json()["rules"]) == {"_builtin_default"}
