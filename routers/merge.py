"""
合并 / 分析相关路由
- 功能权限、省份列表、分析上传文件、执行合并、下载结果
逻辑从原 app.py 中拆分而来。
"""

import os
import json
import uuid
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import JSONResponse, FileResponse

import config
import auth
from merger import (
    get_province_list,
    serialize_cell,
    read_all_sheets,
    SAMPLE_ROWS,
    merge_files,
)

router = APIRouter()


@router.get("/api/features")
async def get_features_api(request: Request):
    """获取当前用户的功能权限（供前端控制 UI 显示）"""
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(
            content={"status": "error", "detail": "未登录"},
            status_code=401,
        )
    return JSONResponse(
        content={"status": "success", "features": user.get("features", {})}
    )


@router.get("/api/regions")
async def get_regions():
    return JSONResponse(
        content={
            "status": "success",
            "regions": get_province_list(),
        }
    )


@router.post("/api/analyze")
async def analyze_files(request: Request, files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")

    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(config.UPLOAD_DIR, session_id)
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
            groups.append(
                {"group_id": gid, "headers": list(info["headers"]), "sheets": []}
            )
        groups[group_map[h_tuple] - 1]["sheets"].append(key)

    # 获取当前用户，用于按用户拉取规则
    user = auth.get_current_user(request)
    username = user.get("username", "") if user else ""

    return JSONResponse(
        content={
            "status": "success",
            "session_id": session_id,
            "sheets": list(all_sheets.values()),
            "all_columns": all_columns_set,
            "auto_groups": groups,
            "regions": get_province_list(),
            "rules": auth.get_all_rules(username),
        }
    )


@router.post("/api/process")
async def process_files(
    request: Request,
    session_id: str = Form(...),
    mappings: str = Form("{}"),
    selected_sheets: str = Form("[]"),
    provinces: str = Form("[]"),
    rule_id: str = Form(""),
    delivery_min: str = Form(""),
    delivery_max: str = Form(""),
):
    session_dir = os.path.join(config.UPLOAD_DIR, session_id)
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

    # 交货号区间筛选（可选）
    delivery_range = None
    if delivery_min and delivery_max:
        try:
            delivery_range = (int(delivery_min.strip()), int(delivery_max.strip()))
        except (ValueError, TypeError):
            pass

    result = merge_files(
        file_paths=file_paths,
        selected_sheets=selected,
        provinces=prov_list,
        rule_id=rule_id or None,
        output_dir=config.OUTPUT_DIR,
        output_prefix=("筛选结果" if prov_list else "合并结果"),
        manual_mappings=json.loads(mappings) or None,
        delivery_range=delivery_range,
    )
    stats = result["stats"]
    stats["selected_sheets"] = len(selected)
    # sheet 数量取决于是否有奥妙数据（条件创建）
    # 基础 5 个：全量数据、筛选数据、交货汇总、交货汇总_文本日期、工厂交货透视
    # 有奥妙数据时 +2：奥妙明细、奥妙小计
    stats["sheet_count"] = 7 if stats.get("omo_detail_count", 0) > 0 else 5

    return JSONResponse(
        content={
            "status": "success",
            "stats": stats,
            "previews": result["previews"],
            "download_url": "/api/download",
        }
    )


@router.get("/api/download")
async def download():
    files = [f for f in os.listdir(config.OUTPUT_DIR) if f.endswith(".xlsx")]
    if not files:
        raise HTTPException(status_code=404, detail="没有可下载的文件，请先处理")
    files.sort(
        key=lambda f: os.path.getmtime(os.path.join(config.OUTPUT_DIR, f)),
        reverse=True,
    )
    latest = files[0]
    output_path = os.path.join(config.OUTPUT_DIR, latest)
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=latest,
    )
