"""
联合利华 Excel 合并筛选系统
- 登录认证（session token）
- 第一步：上传文件，分析所有 Sheet 表头 + 前10行数据
- 第二步：用户纠正表头列名 + 选择参与合并的 Sheet + 选择筛选省份
- 第三步：按列名对齐合并，筛选选中省份的数据，输出 Excel + 预览
"""

import os
import re
import json
import uuid
import hashlib
import datetime
import secrets
from collections import OrderedDict
from typing import List, Dict, Tuple, Optional

import openpyxl
import xlrd
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import MutableHeaders

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
)

app = FastAPI(title="Excel 合并筛选系统")

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

    mapping_dict = json.loads(mappings)
    selected = json.loads(selected_sheets)
    prov_list = json.loads(provinces)
    selected_set = set(selected)

    if not selected:
        raise HTTPException(status_code=400, detail="请至少选择一个 Sheet")

    files_data = {}
    for fname in os.listdir(session_dir):
        if fname.lower().endswith((".xlsx", ".xls", ".csv", ".tsv")):
            files_data[fname] = read_all_sheets(os.path.join(session_dir, fname))

    # 如果指定了规则，为每个选中 Sheet 生成自动映射
    active_rule = None
    std_header_order = []
    if rule_id:
        rules = load_rules()
        for r in rules:
            if r["id"] == rule_id:
                active_rule = r
                break
        if active_rule:
            std_header_order = [
                sh["name"] for sh in active_rule.get("standard_headers", [])
                if sh.get("name", "").strip()
            ]
            for fname, sheets in files_data.items():
                for sname, (headers, _) in sheets.items():
                    key = f"{fname}::{sname}"
                    if key not in selected_set:
                        continue
                    # 仅生成自动映射列表（在合并循环中使用），不转 dict 避免重复列名覆盖
                    # mapping_dict 只保留用户手动映射，不填充 auto_map 结果
                    pass

    # ====== 列名映射 + 合并（基于规则） ======
    # 如果用户未选规则，自动使用内置默认规则
    if not active_rule:
        active_rule = BUILTIN_RULE
        std_header_order = [sh["name"] for sh in active_rule["standard_headers"] if sh.get("name", "").strip()]
        # 为每个选中 sheet 生成自动映射
        for fname, sheets in files_data.items():
            for sname, (headers, _) in sheets.items():
                key = f"{fname}::{sname}"
                if key not in selected_set:
                    continue
                # 仅生成自动映射列表（在合并循环中使用），不转 dict 避免重复列名覆盖
                # mapping_dict 只保留用户手动映射，不填充 auto_map 结果
                pass

    # 确定输出列：只包含规则中定义的标准列（按规则顺序）
    std_col_set = set(std_header_order)
    all_columns = list(std_header_order)  # 只输出标准列

    # 合并所有数据行，通过映射将原始列名转为标准列名
    merged_rows = []
    for fname, sheets in files_data.items():
        for sname, (headers, data_rows) in sheets.items():
            key = f"{fname}::{sname}"
            if key not in selected_set:
                continue
            # 重新执行 match_columns_to_rule 获取逐列映射（支持重复列名）
            # 手动映射覆盖：如果有手动映射，优先使用
            auto_map_list = match_columns_to_rule(headers, active_rule) if active_rule else []
            manual_map = mapping_dict.get(key, {})
            # 构建逐列映射: 第 i 列 -> 标准列名 or None
            mapped_headers = []
            assigned_std = set()  # 已分配的标准列名
            for i, h in enumerate(headers):
                hs = str(h) if h else ""
                # 先检查手动映射
                manual_target = manual_map.get(hs, "")
                std_name = None
                if manual_target and manual_target in std_col_set and manual_target not in assigned_std:
                    std_name = manual_target
                # 如果没有手动映射，用自动映射结果
                if not std_name and i < len(auto_map_list):
                    auto_std = auto_map_list[i][1] if auto_map_list[i] else None
                    if auto_std and auto_std in std_col_set and auto_std not in assigned_std:
                        std_name = auto_std
                # 如果列名本身就是标准列名，直接保留
                if not std_name and hs in std_col_set and hs not in assigned_std:
                    std_name = hs
                if std_name:
                    mapped_headers.append(std_name)
                    assigned_std.add(std_name)
                else:
                    mapped_headers.append(None)  # 非标准列或重复标准列，丢弃
            for row in data_rows:
                row_dict = {}
                for idx, h in enumerate(mapped_headers):
                    if h is None:
                        continue  # 非标准列，跳过
                    row_dict[h] = row[idx] if idx < len(row) else None
                # 应用值映射规则（按 standard_headers 顺序，使跨列条件映射生效）
                if active_rule:
                    for sh in active_rule.get('standard_headers', []):
                        vm = sh.get('value_mappings')
                        if vm:
                            apply_value_mappings(row_dict, sh['name'], vm, fname)
                merged_rows.append(row_dict)

    # 对齐到 all_columns（只有标准列）
    aligned = []
    # 去重：按 (交货, 项目) 去重，防止多个源文件中重叠数据导致重复
    seen_keys = set()
    for row in merged_rows:
        aligned_row = {col: (row.get(col) if row.get(col) is not None else "") for col in all_columns}
        # 过滤汇总行：交货号必须为纯数字（排除"装运编号"等文本行）
        jh_val = str(aligned_row.get("交货", "")).strip()
        if jh_val and not jh_val.isdigit():
            continue  # 跳过非数字交货号（汇总行/页脚行）
        # 过滤空交货号行（汇总行）
        if not jh_val:
            continue  # 跳过空交货号行
        # 构建去重 key: (交货号, 项目号)
        dedup_key = (jh_val, str(aligned_row.get("项目", "")).strip())
        if dedup_key in seen_keys:
            continue  # 跳过重复行
        seen_keys.add(dedup_key)
        aligned.append(aligned_row)

    # 找关键列
    street_key = None
    for col in all_columns:
        if "街道" in col and "街道2" not in col and "街道 3" not in col:
            street_key = col
            break

    # 按选中省份筛选（未选省份时导出全部数据）
    if prov_list:
        filtered = [row for row in aligned if match_row_province(row, prov_list)]
    else:
        filtered = aligned

    # ====== 构建多 Sheet 输出 Excel ======
    wb = openpyxl.Workbook()
    # 标准答案中第20和21列都叫"售达方"（重复列名），内部用"售达方的名字"区分，输出时重命名
    output_headers = ["售达方" if h == "售达方的名字" else h for h in all_columns]

    def _auto_width(ws, headers):
        for col_idx, h in enumerate(headers, 1):
            max_len = len(str(h))
            for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, values_only=True):
                for cell in row:
                    if cell:
                        max_len = max(max_len, len(str(cell)))
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = min(max_len + 4, 50)

    # Sheet1: 全量数据
    ws1 = wb.active
    ws1.title = "全量数据"
    ws1.append(output_headers)
    for row in aligned:
        ws1.append([row.get(h, "") for h in all_columns])
    _auto_width(ws1, output_headers)

    # Sheet3: 筛选数据
    ws3 = wb.create_sheet("筛选数据")
    ws3.append(output_headers)
    for row in filtered:
        ws3.append([row.get(h, "") for h in all_columns])
    _auto_width(ws3, output_headers)

    # Sheet4: 按交货号汇总透视（筛选数据）
    p4_headers, p4_data, text_dates = build_pivot_by_delivery(filtered)
    ws4 = wb.create_sheet("交货汇总")
    ws4.append(p4_headers)
    for row in p4_data:
        ws4.append(row)
    _auto_width(ws4, p4_headers)

    # Sheet5: 文本日期版透视（Sheet4 的副本，None 值用 Sheet3 原始文本回填）
    # 规则：
    # - datetime 保持不变
    # - None 日期 → 用 Sheet3 中的文本日期填充
    # - None 街道 → 用 Sheet3 中的街道填充
    # - "(空白)" 行：交货日期列(索引8)为 None
    p5_headers = list(p4_headers)
    ws5 = wb.create_sheet("交货汇总_文本日期")
    ws5.append(p5_headers)
    for row in p4_data:
        new_row = list(row)
        delivery = str(new_row[0]).strip() if new_row[0] else ""
        if delivery == "(空白)":
            # Sheet5 的 "(空白)" 行：交货日期列(索引8)为 None 而非 "(空白)"
            if len(new_row) > 8:
                new_row[8] = None
        elif delivery != "总计":
            orig = text_dates.get(delivery, {})
            # 发货日期：如果为 None，用 Sheet3 原始文本填充
            if len(new_row) > 7 and new_row[7] is None:
                if orig.get("发货日期"):
                    new_row[7] = _format_date_text(orig["发货日期"])
            # 交货日期：如果为 None，用 Sheet3 原始文本填充
            if len(new_row) > 8 and new_row[8] is None:
                if orig.get("交货日期"):
                    new_row[8] = _format_date_text(orig["交货日期"])
            # 街道：如果为 None，用 Sheet3 原始值填充
            if len(new_row) > 6 and new_row[6] is None:
                if orig.get("街道"):
                    new_row[6] = orig["街道"]
        ws5.append(new_row)
    _auto_width(ws5, p5_headers)

    # Sheet2: 按工厂+交货号透视（全量数据）— 透视表格式
    # 数据已包含: 2空行 + "值"行 + 表头 + 数据 + 总计行
    p2_headers, p2_data = build_pivot_by_factory_delivery(aligned)
    ws2 = wb.create_sheet("工厂交货透视")
    for row in p2_data:
        ws2.append(row)
    _auto_width(ws2, p2_headers)

    if not filtered:
        ws_note = wb.create_sheet("说明")
        ws_note.append(["未找到匹配省份的数据，筛选数据Sheet为空"])

    today = datetime.datetime.now().strftime("%Y%m%d")
    hash_source = f"{today}_{len(filtered)}_{len(all_columns)}_{datetime.datetime.now().strftime('%H%M%S%f')}"
    short_hash = hashlib.md5(hash_source.encode()).hexdigest()[:8]
    prov_short = "_".join(p.replace("省", "").replace("市", "") for p in prov_list[:3]) if prov_list else "全部"
    action = "筛选结果" if prov_list else "合并结果"
    output_filename = f"{action}_{prov_short}_{today}_{short_hash}.xlsx"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    wb.save(output_path)
    wb.close()

    # ====== 预览（返回多个 sheet 的预览） ======
    previews = []

    def _add_preview(name, headers, rows):
        if not rows:
            return
        preview_rows = []
        for row in rows[:PREVIEW_MAX_ROWS]:
            preview_rows.append([serialize_cell(c) for c in row])
        previews.append({
            "sheet_name": name,
            "headers": [str(h) for h in headers],
            "rows": preview_rows,
            "total": len(rows),
            "preview_count": len(preview_rows),
        })

    # 筛选数据预览
    filter_preview_rows = [[row.get(h, "") for h in all_columns] for row in filtered[:PREVIEW_MAX_ROWS]]
    if filter_preview_rows:
        previews.append({
            "sheet_name": "筛选数据",
            "headers": output_headers,
            "rows": [[serialize_cell(c) for c in r] for r in filter_preview_rows],
            "total": len(filtered),
            "preview_count": len(filter_preview_rows),
        })

    # 透视表预览
    _add_preview("交货汇总", p4_headers, p4_data)
    _add_preview("工厂交货透视", p2_headers, p2_data)

    stats = {
        "selected_sheets": len(selected),
        "total_merged_rows": len(merged_rows),
        "total_columns": len(all_columns),
        "filtered_rows": len(filtered),
        "pivot_delivery_count": len(p4_data),
        "pivot_factory_count": len(p2_data),
        "street_column": street_key or "未找到",
        "provinces": prov_list,
        "sheet_count": 5,
    }

    return JSONResponse(content={
        "status": "success",
        "stats": stats,
        "previews": previews,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
