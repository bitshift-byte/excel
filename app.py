"""
联合利华 Excel 合并筛选系统
- 登录认证（session token）
- 第一步：上传文件，分析所有 Sheet 表头 + 前10行数据
- 第二步：用户纠正表头列名 + 选择参与合并的 Sheet + 选择筛选省份
- 第三步：按列名对齐合并，筛选选中省份的数据，输出 Excel + 预览
"""

import os
import json
import uuid
import datetime
import secrets
import asyncio
from typing import List, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from merger import (
    BUILTIN_RULE_ID,
    BUILTIN_RULE,
    load_rules,
    save_rules,
    get_province_list,
    serialize_cell,
    read_all_sheets,
    SAMPLE_ROWS,
    match_columns_to_rule,
    apply_value_mappings,
    build_pivot_by_delivery,
    build_pivot_by_factory_delivery,
    _format_date_text,
    match_row_province,
    PREVIEW_MAX_ROWS,
    merge_files,
)

import mail_reader

MAIL_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "mail_config.json")


@asynccontextmanager
async def lifespan(app):
    if os.path.exists(MAIL_CONFIG_FILE):
        cfg = mail_reader.load_config(MAIL_CONFIG_FILE)
        if cfg.get("enabled"):
            mail_reader.start_background(cfg)
    yield
    mail_reader.stop_background()


app = FastAPI(title="Excel 合并筛选系统", lifespan=lifespan)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)



# ===================== 认证 =====================

# 用户数据库（演示用，实际可对接数据库）
USERS = {
    "admin": {"password": "admin123", "name": "管理员", "role": "admin"},
    "user": {"password": "user123", "name": "普通用户", "role": "user"},
}

# session token → username 映射（内存存储，重启失效）
SESSIONS: Dict[str, str] = {}
SESSION_COOKIE = "nebula_session"
SESSION_MAX_AGE = 86400  # 24h


class AuthMiddleware(BaseHTTPMiddleware):
    """拦截需要认证的路由，未登录重定向到 /login"""

    PUBLIC_PATHS = {"/login", "/api/login", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 公开路由直接放行
        if path in self.PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)

        # 检查 session
        token = request.cookies.get(SESSION_COOKIE)
        if token and token in SESSIONS:
            request.state.username = SESSIONS[token]
            return await call_next(request)

        # API 路由返回 401
        if path.startswith("/api/"):
            return JSONResponse({"status": "error", "detail": "未登录或会话已过期"}, status_code=401)

        # 页面重定向到登录
        return RedirectResponse("/login", status_code=302)


app.add_middleware(AuthMiddleware)


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(SESSION_COOKIE)
    if token and token in SESSIONS:
        username = SESSIONS[token]
        user_info = USERS.get(username)
        if user_info:
            return {"username": username, "name": user_info["name"], "role": user_info["role"]}
    return None







# ===================== 路由 =====================

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    with open("templates/login.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/login")
async def login_api(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    user = USERS.get(username)
    if not user or user["password"] != password:
        return JSONResponse({"status": "error", "detail": "用户名或密码错误"}, status_code=401)

    token = secrets.token_hex(16)
    SESSIONS[token] = username

    resp = JSONResponse({"status": "success", "user": {"username": username, "name": user["name"], "role": user["role"]}})
    resp.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@app.post("/api/logout")
async def logout_api(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token and token in SESSIONS:
        del SESSIONS[token]
    resp = JSONResponse({"status": "success"})
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/api/me")
async def get_me(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"status": "error", "detail": "未登录"}, status_code=401)
    return JSONResponse({"status": "success", "user": user})


# ===================== 规则 CRUD =====================

@app.get("/api/rules")
async def list_rules():
    return JSONResponse(content={"status": "success", "rules": load_rules()})


@app.post("/api/rules")
async def create_rule(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="规则名称不能为空")
    standard_headers = body.get("standard_headers", [])
    if not standard_headers:
        raise HTTPException(status_code=400, detail="请至少添加一个标准表头")

    rules = load_rules()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    rule = {
        "id": "r" + uuid.uuid4().hex[:8],
        "name": name,
        "standard_headers": [
            {
                "name": sh.get("name", "").strip(),
                "source_columns": [sc.strip() for sc in sh.get("source_columns", []) if sc.strip()],
                **({"value_mappings": sh["value_mappings"]} if sh.get("value_mappings") else {}),
            }
            for sh in standard_headers
            if sh.get("name", "").strip()
        ],
        "created_at": now,
        "updated_at": now,
    }
    rules.append(rule)
    save_rules(rules)
    return JSONResponse(content={"status": "success", "rule": rule})


@app.put("/api/rules/{rule_id}")
async def update_rule(rule_id: str, request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="规则名称不能为空")
    standard_headers = body.get("standard_headers", [])

    if rule_id == BUILTIN_RULE_ID:
        raise HTTPException(status_code=400, detail="内置规则不可修改")
    rules = load_rules()
    found = None
    for r in rules:
        if r["id"] == rule_id:
            found = r
            break
    if not found:
        raise HTTPException(status_code=404, detail="规则不存在")

    found["name"] = name
    found["standard_headers"] = [
        {
            "name": sh.get("name", "").strip(),
            "source_columns": [sc.strip() for sc in sh.get("source_columns", []) if sc.strip()],
            **({"value_mappings": sh["value_mappings"]} if sh.get("value_mappings") else {}),
        }
        for sh in standard_headers
        if sh.get("name", "").strip()
    ]
    found["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    save_rules(rules)
    return JSONResponse(content={"status": "success", "rule": found})


@app.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: str):
    if rule_id == BUILTIN_RULE_ID:
        raise HTTPException(status_code=400, detail="内置规则不可删除")
    rules = load_rules()
    new_rules = [r for r in rules if r["id"] != rule_id]
    if len(new_rules) == len(rules):
        raise HTTPException(status_code=404, detail="规则不存在")
    save_rules(new_rules)
    return JSONResponse(content={"status": "success"})


@app.post("/api/rules/parse")
async def parse_rule_excel(files: List[UploadFile] = File(...)):
    """上传 Excel 文件，解析所有 Sheet 的表头，用于规则创建时导入"""
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")

    import tempfile
    sheets_info = []
    for f in files:
        # 写入临时文件
        suffix = os.path.splitext(f.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await f.read())
            tmp_path = tmp.name
        try:
            sheets = read_all_sheets(tmp_path)
            for sname, (headers, data_rows) in sheets.items():
                header_list = [str(h) if h else "" for h in headers if h is not None and str(h).strip()]
                sheets_info.append({
                    "filename": f.filename,
                    "sheet_name": sname,
                    "headers": header_list,
                    "row_count": len(data_rows),
                })
        finally:
            os.unlink(tmp_path)

    if not sheets_info:
        raise HTTPException(status_code=400, detail="未找到有效的 Sheet 数据")

    return JSONResponse(content={
        "status": "success",
        "sheets": sheets_info,
    })


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/regions")
async def get_regions():
    return JSONResponse(content={
        "status": "success",
        "regions": get_province_list(),
    })


@app.post("/api/analyze")
async def analyze_files(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")

    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(UPLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    saved_files = []
    for f in files:
        # 统一保存为小写后缀，避免大写扩展名导致后续判断失败
        fname = f.filename
        root, ext = os.path.splitext(fname)
        if ext:
            fname = root + ext.lower()
        save_path = os.path.join(session_dir, fname)
        with open(save_path, "wb") as out:
            out.write(await f.read())
        saved_files.append(fname)

    all_sheets = {}
    all_columns_set = []
    all_columns_seen = set()

    for fname in saved_files:
        filepath = os.path.join(session_dir, fname)
        sheets = read_all_sheets(filepath)
        for sname, (headers, data_rows) in sheets.items():
            sample = []
            for r in data_rows[:SAMPLE_ROWS]:
                sample.append([serialize_cell(c) for c in r])
            key = f"{fname}::{sname}"
            all_sheets[key] = {
                "filename": fname,
                "sheet_name": sname,
                "headers": [str(h) if h else "" for h in headers],
                "row_count": len(data_rows),
                "sample_rows": sample,
            }
            for h in headers:
                hs = str(h) if h else ""
                if hs and hs not in all_columns_seen:
                    all_columns_set.append(hs)
                    all_columns_seen.add(hs)

    # 自动分组：表头完全相同的 sheet
    groups = []
    group_map = {}
    gid = 0
    for key, info in all_sheets.items():
        h_tuple = tuple(info["headers"])
        if h_tuple not in group_map:
            gid += 1
            group_map[h_tuple] = gid
            groups.append({"group_id": gid, "headers": list(info["headers"]), "sheets": []})
        groups[group_map[h_tuple] - 1]["sheets"].append(key)

    return JSONResponse(content={
        "status": "success",
        "session_id": session_id,
        "sheets": list(all_sheets.values()),
        "all_columns": all_columns_set,
        "auto_groups": groups,
        "regions": get_province_list(),
        "rules": load_rules(),
    })


@app.post("/api/process")
async def process_files(
    request: Request,
    session_id: str = Form(...),
    mappings: str = Form("{}"),
    selected_sheets: str = Form("[]"),
    provinces: str = Form("[]"),
    rule_id: str = Form(""),
):
    session_dir = os.path.join(UPLOAD_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=400, detail="会话已过期，请重新上传")

    selected = json.loads(selected_sheets)
    prov_list = json.loads(provinces)
    if not selected:
        raise HTTPException(status_code=400, detail="请至少选择一个 Sheet")

    file_paths = [
        os.path.join(session_dir, fname)
        for fname in os.listdir(session_dir)
        if fname.lower().endswith((".xlsx", ".xls", ".csv", ".tsv"))
    ]

    result = merge_files(
        file_paths=file_paths,
        selected_sheets=selected,
        provinces=prov_list,
        rule_id=rule_id or None,
        output_dir=OUTPUT_DIR,
        output_prefix=("筛选结果" if prov_list else "合并结果"),
        manual_mappings=json.loads(mappings) or None,
    )
    stats = result["stats"]
    stats["selected_sheets"] = len(selected)
    stats["sheet_count"] = 5

    return JSONResponse(content={
        "status": "success",
        "stats": stats,
        "previews": result["previews"],
        "download_url": "/api/download",
    })


@app.get("/api/download")
async def download():
    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".xlsx")]
    if not files:
        raise HTTPException(status_code=404, detail="没有可下载的文件，请先处理")
    files.sort(key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)), reverse=True)
    latest = files[0]
    output_path = os.path.join(OUTPUT_DIR, latest)
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=latest,
    )


# ===================== 邮件读取器配置 =====================

@app.get("/api/mail/config")
async def get_mail_config():
    cfg = None
    if os.path.exists(MAIL_CONFIG_FILE):
        with open(MAIL_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    return JSONResponse(content={"status": "success", "config": cfg, "running": mail_reader.is_running()})


@app.put("/api/mail/config")
async def set_mail_config(request: Request):
    body = await request.json()
    with open(MAIL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    if body.get("enabled"):
        mail_reader.start_background(body)
    else:
        mail_reader.stop_background()
    return JSONResponse(content={"status": "success", "running": mail_reader.is_running()})


@app.post("/api/mail/start")
async def start_mail():
    if not os.path.exists(MAIL_CONFIG_FILE):
        raise HTTPException(status_code=400, detail="请先保存邮件配置")
    cfg = mail_reader.load_config(MAIL_CONFIG_FILE)
    mail_reader.start_background(cfg)
    return JSONResponse(content={"status": "success", "running": mail_reader.is_running()})


@app.post("/api/mail/stop")
async def stop_mail():
    mail_reader.stop_background()
    return JSONResponse(content={"status": "success", "running": mail_reader.is_running()})


@app.get("/api/mail/status")
async def mail_status():
    return JSONResponse(content={"status": "success", "running": mail_reader.is_running()})


@app.get("/api/mail/logs")
async def mail_logs():
    return JSONResponse(content={"status": "success", "logs": mail_reader.get_logs()})


@app.post("/api/mail/run")
async def run_mail_once():
    if not os.path.exists(MAIL_CONFIG_FILE):
        raise HTTPException(status_code=400, detail="请先保存邮件配置")
    cfg = mail_reader.load_config(MAIL_CONFIG_FILE)
    handled = await asyncio.to_thread(mail_reader.process_once, cfg)
    return JSONResponse(content={"status": "success", "handled": handled, "logs": mail_reader.get_logs()})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
