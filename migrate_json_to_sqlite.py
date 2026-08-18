"""
JSON → SQLite 迁移脚本
读取 data/auth_config.json 和 data/app_config.json，导入到 SQLite (data/app.db)

使用方法：
  python migrate_json_to_sqlite.py          # 迁移（跳过已有数据）
  python migrate_json_to_sqlite.py --force   # 强制重新迁移（清空后导入）
"""

import os
import sys
import json

# 确保能 import database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database


def migrate(force: bool = False):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")

    auth_config_path = os.path.join(data_dir, "auth_config.json")
    app_config_path = os.path.join(data_dir, "app_config.json")
    users_path = os.path.join(data_dir, "users.json")
    tasks_path = os.path.join(data_dir, "tasks.json")
    processed_uids_path = os.path.join(data_dir, "processed_uids.json")

    # 初始化数据库表
    database.init_db()
    print("[migrate] 数据库表已初始化")

    if force:
        print("[migrate] 强制模式：清空现有数据...")
        with database.get_db() as conn:
            for table in ("users", "app_config", "rules", "user_rules",
                         "user_provinces", "sessions", "active_logins",
                         "admin_sessions", "mail_tasks", "processed_uids"):
                conn.execute(f"DELETE FROM {table}")
        database._seed_defaults()
        print("[migrate] 默认数据已重新注入")

    # 1. 迁移用户
    users_data = None
    if os.path.exists(auth_config_path):
        with open(auth_config_path, "r", encoding="utf-8") as f:
            auth_cfg = json.load(f)
        users_data = auth_cfg.get("users", [])
        print(f"[migrate] 从 auth_config.json 读取到 {len(users_data)} 个用户")
    elif os.path.exists(users_path):
        with open(users_path, "r", encoding="utf-8") as f:
            users_data = json.load(f)
        print(f"[migrate] 从 users.json 读取到 {len(users_data)} 个用户")

    if users_data:
        existing = {u["username"] for u in database.get_all_users()}
        migrated = 0
        for u in users_data:
            username = u.get("username", "")
            if not username or username in existing:
                continue
            database.create_user(
                username=username,
                password=u.get("password", ""),
                name=u.get("name", username),
                role=u.get("role", "user"),
                enabled=u.get("enabled", True),
                features=u.get("features", {}),
            )
            existing.add(username)
            migrated += 1
        print(f"[migrate] 迁移用户: {migrated} 个新增")

    # 2. 迁移应用配置
    if os.path.exists(app_config_path):
        with open(app_config_path, "r", encoding="utf-8") as f:
            app_cfg = json.load(f)
        print(f"[migrate] 从 app_config.json 读取配置，keys: {list(app_cfg.keys())}")

        # 邮件配置
        mail_cfg = app_cfg.get("mail_config", {})
        if mail_cfg:
            database.set_mail_config(mail_cfg)
            print(f"[migrate] 邮件配置已迁移 (email={mail_cfg.get('email', 'N/A')})")

        # 功能开关
        features = app_cfg.get("features", {})
        if features:
            database.set_features(features)
            print(f"[migrate] 功能开关已迁移: {features}")

        # 规则
        rules = app_cfg.get("rules", [])
        migrated_rules = 0
        for r in rules:
            if r.get("builtin") or r.get("id") == "_builtin_default":
                continue
            existing_rule = database.get_rule(r["id"])
            if existing_rule:
                continue
            with database.get_db() as conn:
                conn.execute(
                    "INSERT INTO rules (id, name, standard_headers, builtin, created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
                    (r["id"], r.get("name", ""),
                     json.dumps(r.get("standard_headers", []), ensure_ascii=False),
                     r.get("created_at", ""), r.get("updated_at", ""))
                )
            migrated_rules += 1
        print(f"[migrate] 规则迁移: {migrated_rules} 个新增")

        # 用户规则分配
        user_rules = app_cfg.get("user_rules", {})
        migrated_ur = 0
        for username, rule_ids in user_rules.items():
            database.set_user_rules(username, rule_ids)
            migrated_ur += 1
        print(f"[migrate] 用户规则分配迁移: {migrated_ur} 个用户")

        # 用户省份分配
        user_provinces = app_cfg.get("user_provinces", {})
        migrated_up = 0
        for username, provinces in user_provinces.items():
            database.set_user_provinces(username, provinces)
            migrated_up += 1
        print(f"[migrate] 用户省份分配迁移: {migrated_up} 个用户")
    else:
        print("[migrate] app_config.json 不存在，跳过应用配置迁移")

    # 3. 迁移邮件任务历史
    if os.path.exists(tasks_path):
        with open(tasks_path, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        for task in tasks:
            database.save_mail_task(task.get("mails", []))
        print(f"[migrate] 邮件任务历史迁移: {len(tasks)} 条")

    # 4. 迁移已处理邮件 UID
    if os.path.exists(processed_uids_path):
        with open(processed_uids_path, "r", encoding="utf-8") as f:
            uids = json.load(f)
        uid_set = set(uids) if isinstance(uids, list) else set()
        database.add_processed_uids(uid_set)
        print(f"[migrate] 已处理邮件 UID 迁移: {len(uid_set)} 条")

    print("[migrate] 迁移完成!")
    print(f"[migrate] 数据库位置: {database.DB_PATH}")

    # 验证
    users = database.get_all_users()
    rules = database.get_all_rules()
    print(f"[migrate] 验证: {len(users)} 个用户, {len(rules)} 个自定义规则")
    for u in users:
        rid = database.get_user_rule_ids(u["username"])
        provs = database.get_user_provinces(u["username"])
        print(f"  - {u['username']} ({u['role']}): rules={rid}, provinces={provs}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    migrate(force=force)
