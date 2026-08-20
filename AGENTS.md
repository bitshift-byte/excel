# AGENTS.md

Guidance for AI agents working in this repository.

## What This Is

Unilever (联合利华) SAP delivery Excel merge/filter web system. Users upload `.xlsx`/`.xls` files, the system analyzes sheet headers, lets users correct column names and select provinces, then merges and filters by province — outputting a consolidated Excel file. Also includes an IMAP background mail reader that auto-processes emailed Excel attachments.

**Stack**: FastAPI (Python 3.11) backend + Vue 3 SPA frontend (Vite, Naive UI, Pinia). SQLite for users/config/rules/sessions. openpyxl + xlrd for Excel I/O.

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
