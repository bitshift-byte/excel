# AGENTS.md

Guidance for AI agents working in this repository.

## What This Is

Unilever (联合利华) SAP delivery Excel merge/filter web system. Users upload `.xlsx`/`.xls` files, the system analyzes sheet headers, lets users correct column names and select provinces, then merges and filters by province — outputting a consolidated Excel file. Also includes an IMAP background mail reader that auto-processes emailed Excel attachments.

**Stack**: FastAPI (Python 3.11) backend + Vue 3 SPA frontend (Vite, Naive UI, Pinia). SQLite for users/config/rules/sessions. openpyxl + xlrd for Excel I/O.

## 功能清单（业务功能）

下一个 AI 接手时先看这里，了解系统能做什么。

### 1. Excel 合并（核心，`/api/analyze` + `/api/process`）
- 上传多个 SAP 导出 Excel（06o/分销报表/分销下单量/跑单明细等），按内置标准 34 列 schema 归并。
- 模糊匹配列名（`source_columns` 别名），支持手动纠正列映射。
- 工厂值重映射（`BUILTIN_RULE.value_mappings`）：按源文件名关键词重写工厂值，如"分销报表"里 8136/8137/8205 → 901，"跑单明细"里 → 801。
- 按省份/交货号区间筛选；输出含：全量数据、筛选数据、交货汇总（按交货号透视）、数据透析、工厂交货透视、奥妙明细/小计 等多个 sheet。
- B_ADDRESS1/备注 通过物流信息映射（已发运/未发运 → SO 文件 → 跨仓订单 三级回退查找）。
- 汇总行过滤：`项目`列为空的行视为小计行被丢弃。

### 2. 邮件捞取（后台 IMAP，`mail_reader.py` + `/api/mail/*`）
- 后台线程轮询 IMAP 邮箱，按关键词匹配主题，下载 Excel 附件并自动走合并流程。
- 关键词匹配大小写不敏感；附件按数据日期归位，避免跨日邮件混入错误日期结果。
- 工厂覆盖：主题/附件名/正文含特定关键词时强制改工厂值（`detect_factory_override`）。
- 已处理 UID 记录到文件，避免重复处理。

### 3. 邮件合并到总表（`/api/mail-merge/run`，`merger.merge_mail_into_master`）
- 选一个邮件捞取产物 + 上传总表（已发运/未发运/明细/客户信息/组套/Sheet5 格式），把每日新订单追加进总表。
- 明细 sheet：追加所有新交货号的所有行。
- 未发运 sheet：从交货汇总追加新订单（B_ADDRESS1/备注按表头名解析列位置，兼容新旧列序）。
- **901 标记**：新追加的 901 库区行（含 B_ADDRESS1 为"京东NONBOM组套订单"的行）→ 提货状态改为"不可提"+红色加粗。仅作用于新行，总表原有 901 行不动。
- 未发运重排（`_restructure_weifayun_sheet`）：901 区在最上面 → 非901区 → 空客户行；每区内按客户名称分组，每组末尾插 SUBTOTAL 小计行（红色字体）；B_ADDRESS1 京东NONBOM → 工厂强制改 901 + 棕色加粗。

### 4. 用户与权限（`auth.py` + `/admin/api/*`）
- 用户/角色（admin/user）、设备绑定、按用户分配规则/省份/功能开关。
- 规则管理（rules.json + SQLite）、应用配置、邮件配置。

### 前端页面（`frontend/src/views/`）
Login、Merge（合并）、Mail（邮件捞取）、MailMerge（邮件合并到总表）、Admin（用户管理）、Rules（规则管理）。

## Dev Commands

```bash
# Backend (port 8000) — run from project root
venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8000
# or: venv/bin/python app.py

# Frontend dev server (port 5173, proxies /api + /login → :8000)
cd frontend && npm run dev

# Frontend production build → outputs to ../dist_vue/ (FastAPI serves this when present)
cd frontend && npm run build

# Install deps
pip install -r requirements.txt          # backend
pip install -r requirements-dev.txt      # pytest
cd frontend && npm ci                   # frontend

# Tests
venv/bin/python -m pytest tests/ -q
venv/bin/python -m pytest tests/test_merger.py::test_match_columns_to_rule_exact -v   # single test

# Docker
docker-compose up -d        # builds + runs, maps host :80 → container :8000
docker build -t lx-web .    # manual build
```

The virtualenv is at `venv/` (Python 3.14). Use `venv/bin/python` not bare `python`.

## Architecture

```
app.py                    FastAPI entry; lifespan inits DB, auto-migrates legacy JSON→SQLite, loads config, starts mail background
config.py                 Paths (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, VUE_DIST_DIR), session constants, service token getter
state.py                  In-memory mutable state (SESSIONS, USERS, APP_CONFIG_CACHE) — lost on restart, sessions restored from SQLite
auth.py                   AuthMiddleware (only guards /api/*), user management, config fetching — reads directly from SQLite
database.py               SQLite ops (users, app config, rules, sessions, provinces). DB at data/app.db
merger.py                 CORE: Excel merge logic (1167 lines). BUILTIN_RULE, column matching, province filtering, summary-row filtering
mail_reader.py            IMAP background thread — polls mailbox, downloads Excel attachments, auto-merges
migrate_json_to_sqlite.py One-time migration from legacy JSON config files to SQLite
routers/
  auth.py                 /api/login, /api/logout, /api/me, /api/sync, /api/users, /api/rules
  merge.py                /api/analyze, /api/process, /api/download, /api/regions, /api/features
  mail.py                 /api/mail/* — mail reader control + results listing
  mail_merge.py           /api/mail-merge/* — combine mail-fetched file + uploaded master table
  admin.py                /admin/api/* — user/config/rule management (admin role required)
  pages.py                SPA fallback — serves dist_vue/index.html or legacy templates/index.html
frontend/                 Vue 3 SPA (src/views: Login, Merge, Mail, MailMerge, Admin, Rules)
templates/                Legacy HTML fallback (used only when dist_vue/ doesn't exist)
china_regions.json        Province/city keyword data for region filtering
rules.json                File-based merge rules (user-created, NOT in SQLite)
```

**Frontend serving**: `config.USE_VUE_FRONTEND` is auto-detected by checking if `dist_vue/` exists. If absent, falls back to `templates/index.html`. You must run `npm run build` in `frontend/` before the backend serves the Vue SPA.

**Auth model**: AuthMiddleware only protects `/api/*` routes. SPA pages (`/`, `/login`, `/admin`, etc.) are served without server-side auth — Vue Router handles login redirects client-side. Sessions are in-memory (`state.SESSIONS`) but persisted to SQLite for restart recovery via `_restore_session_from_db()`.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SERVICE_TOKEN` | `lx-internal-service-token` | Inter-service secret (currently unused after auth was embedded, but still set in Docker) |
| `PASSWORD_SALT` | `excel-merger-salt` | Password hashing salt |
| `DATA_DIR` | `<project>/data` | SQLite DB + config directory override |

**Proxy env vars** (`ALL_PROXY`, `HTTP_PROXY`, `HTTPS_PROXY` and lowercase variants) are **stripped at import time** in `app.py` (lines 23–24). This is intentional — the app must not route through proxies. Do not remove this.

## Architecture Quirks & Gotchas

1. **`auth_service` module no longer exists.** Auth was refactored from a separate service (port 8001) into embedded SQLite (`auth.py` + `database.py`). The `deploy/README.md`, `auth_service_url.example.txt`, and 3 test files still reference the old `auth_service` module — these are stale artifacts. `auth.py` docstring explicitly states: "不再通过 HTTP 调用远程认证服务".

2. **Test suite is largely broken.** Only `test_mail_reader.py` (5 tests) fully passes. `test_merger.py` has 2 failing tests (merge expectations stale). `test_app_auth.py` (16 tests) errors due to mocking a non-existent `auth.verify_user_status_with_auth_service`. `test_auth_service.py`, `test_province_isolation.py`, `test_rule_isolation_service.py` fail at import (`ModuleNotFoundError: auth_service`). `test_rule_isolation_desktop.py` is mixed. **Do not assume `pytest` is green — verify which tests pass before relying on them.**

3. **`BUILTIN_RULE` in `merger.py` is hardcoded business logic.** It defines the Unilever standard 34-column schema with `source_columns` aliases for fuzzy header matching, plus `value_mappings` for the 工厂 (plant) field that remap values (e.g., `8136→701`) based on the source filename containing keywords like "分销下单量", "分销报表", "跑单明细". Changing this affects all merges.

4. **Summary rows are filtered by missing 项目 (item) number.** During merge, any row where the `项目` column is empty/None is treated as a subtotal/summary row and dropped. This is domain-specific behavior, not a bug.

4b. **901 库区 = 京东 NONBOM 组套订单（RTS 再包），是特殊业务标识。** 相关规则：
   - `BUILTIN_RULE` 把"分销报表"里的 8136/8137/8205 重映射为 901。
   - 未发运 sheet 里，B_ADDRESS1 以"京东NONBOM组套订单"开头的行 → 工厂强制改 901、B_ADDRESS1 棕色加粗（`_is_jd_nonbom` + `_restructure_weifayun_sheet`）。
   - **新追加的 901 行**提货状态标"不可提"+红色加粗（仅在 `merge_mail_into_master` 追加阶段，`_RED_FONT`）；**总表原有 901 行保持原值不动**。
   - `_restructure_weifayun_sheet` 重排未发运：901区置顶 → 按客户名称分组 → 每组末尾 SUBTOTAL 小计行。
   - 901 行在已发运 sheet 不标"不可提"（已出库按业务语义不标）。

5. **`config.py` has side effects at import.** It creates `data/`, `uploads/`, `output/` directories on module load. Importing `config` anywhere triggers directory creation.

6. **`rules.json` is file-based, not in SQLite.** User-created merge rules (with column mappings and value mappings) live in `rules.json`. The builtin rule (`_builtin_default`) is hardcoded in `merger.py` and always available. Admin-managed rules go to SQLite, but `rules.json` is the file the system reads/writes for rule persistence.

7. **Column names are Chinese.** Standard headers like 交货, 销售凭证, 运达方, 送达方地点, 工厂, 物料, 描述, 交货量, 总重量, 业务量. The `source_columns` arrays in rules provide fuzzy matching against variant names.

8. **Province filtering uses `china_regions.json` keyword matching.** `match_row_province()` checks 送达方地点 and 街道 fields against province/city keywords. Filtering by "江苏省" matches rows containing "苏州市", "江苏省" in those fields.

9. **On startup, `app.py` lifespan auto-migrates** from legacy `data/auth_config.json` / `data/app_config.json` to SQLite if those files exist. This is a one-time migration; once migrated, the JSON files are ignored.

## Database

SQLite at `data/app.db` (created by `database.init_db()` on first startup). Tables: users, app_config, rules, user_rules, user_provinces, sessions. Default users seeded on init: `admin/admin123` (admin role), `user1/user123`, `user2/user123`. Passwords are SHA256-hashed with `PASSWORD_SALT`.

## CI/CD

GitHub Actions (`.github/workflows/build-docker.yml`) triggers on `v*` tags → builds multi-stage Docker image (frontend build + Python runtime) → pushes to `ghcr.io/<repo>`. No lint/typecheck/test CI step exists — only Docker build on tag.

## Data Files (gitignored)

`data/` (SQLite DB, migrated configs), `uploads/` (user uploads), `output/` (merge results), `dist_vue/` (frontend build), `*.xlsx` (sample/test data in root). All gitignored. The `.xlsx` files in root are real Unilever SAP exports used for manual testing — do not commit new ones.
