"""
邮件合并路由
- 从邮件捞取产物中选一个 + 上传总表 → 两个文件一起合并 → 产出最终表格
"""
import os
import shutil
import uuid
import json
import datetime
from typing import List, Optional
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse, FileResponse

import openpyxl

import config
import auth
from merger import (
    read_all_sheets,
    match_columns_to_rule,
    serialize_cell,
    merge_files,
    load_rules,
    SAMPLE_ROWS,
)

router = APIRouter(prefix="/api/mail-merge", tags=["mail-merge"])


# ===================== 列出邮件捞取产物 =====================

@router.get("/mail-results")
async def list_mail_results(request: Request):
    """列出 output 目录中邮件捞取的产物文件"""
    if not auth.get_current_user(request):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")

    files = []
    if os.path.isdir(config.OUTPUT_DIR):
        for f in os.listdir(config.OUTPUT_DIR):
            if f.startswith("邮件合并") and not f.startswith("邮件合并结果") and f.endswith(".xlsx"):
                path = os.path.join(config.OUTPUT_DIR, f)
                st = os.stat(path)

                sheet_info = []
                try:
                    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                    for sn in wb.sheetnames:
                        ws = wb[sn]
                        sheet_info.append({
                            "name": sn,
                            "rows": ws.max_row - 1 if ws.max_row > 0 else 0,
                            "cols": ws.max_column,
                        })
                    wb.close()
                except Exception:
                    pass

                files.append({
                    "filename": f,
                    "mtime": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "size": st.st_size,
                    "sheets": sheet_info,
                })
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return JSONResponse(content={"status": "success", "files": files})


# ===================== 选邮件产物 + 上传总表 → 一键合并 =====================

@router.post("/run")
async def run_merge(
    request: Request,
    files: List[UploadFile] = File(default=[]),
    mail_filename: str = Form(default=""),
    delivery_min: str = Form(default=""),
    delivery_max: str = Form(default=""),
):
    """选邮件产物 + 上传总表 → 两个文件一起合并

    两种来源汇合到一起：
    1. mail_filename: 从邮件捞取产物中选的文件（output 目录中）
    2. files: 用户上传的总表文件（含明细/已发运/未发运）

    把两个文件放一起跑 merge_files 管道。
    """
    if not auth.get_current_user(request):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")

    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(config.UPLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    saved_files = []
    source_desc = []  # 记录每个文件来源

    # 1. 复制选中的邮件产物
    if mail_filename:
        mail_path = os.path.join(config.OUTPUT_DIR, mail_filename)
        if not os.path.isfile(mail_path):
            raise HTTPException(status_code=400, detail=f"邮件产物不存在: {mail_filename}")
        # 复制到 session 目录
        dest = os.path.join(session_dir, mail_filename)
        shutil.copy2(mail_path, dest)
        saved_files.append(mail_filename)
        source_desc.append({"name": mail_filename, "source": "邮件捞取产物"})

    # 2. 保存上传的总表
    for f in files:
        if not f.filename:
            continue
        fname = f.filename
        root, ext = os.path.splitext(fname)
        if ext:
            fname = root + ext.lower()
        save_path = os.path.join(session_dir, fname)
        with open(save_path, "wb") as out:
            content = await f.read()
            out.write(content)
        saved_files.append(fname)
        source_desc.append({"name": fname, "source": "上传文件"})

    if not saved_files:
        raise HTTPException(status_code=400, detail="请选择邮件产物或上传总表文件")

    file_paths = [os.path.join(session_dir, f) for f in saved_files]

    # 分析所有 sheet，区分「源数据 sheet」和「结果产物 sheet」
    # 邮件产物的「筛选数据」是按省份筛选后的明细数据，应作为数据源参与合并
    # 「全量数据」是全国数据，不能直接当数据源（会引入非目标省份的数据）
    # 其他结果产物（交货汇总等）也排除，避免数据翻倍
    RESULT_SHEET_NAMES = {
        "全量数据", "交货汇总", "交货汇总_文本日期",
        "工厂交货透视", "奥妙明细", "奥妙小计",
    }
    sheets_map = {}
    for fp in file_paths:
        sheets = read_all_sheets(fp)
        fname = os.path.basename(fp)
        for sname, (headers, data_rows) in sheets.items():
            key = f"{fname}::{sname}"
            sheets_map[key] = {
                "filename": fname,
                "sheet_name": sname,
                "headers": headers,
                "row_count": len(data_rows),
            }

    # 自动选中：只选总表中的「明细」「已发运」「未发运」sheet
    # 排除邮件产物中已经是结果产物的 sheet
    selected_keys = []
    for key, info in sheets_map.items():
        sn = info["sheet_name"]
        # 排除结果产物 sheet
        if sn in RESULT_SHEET_NAMES:
            continue
        # 选中明细型 sheet（含"交货"列且行数多）
        headers_str = [str(h) if h else "" for h in info["headers"]]
        has_jiaohuo = any("交货" in h for h in headers_str)
        if has_jiaohuo and info["row_count"] > 100:
            selected_keys.append(key)
        # 选中已发运/未发运
        elif "发运" in sn:
            selected_keys.append(key)

    if not selected_keys:
        # 如果没匹配到，选非结果产物的行数 > 50 的 sheet
        for key, info in sheets_map.items():
            if info["sheet_name"] in RESULT_SHEET_NAMES:
                continue
            if info["row_count"] > 50:
                selected_keys.append(key)

    if not selected_keys:
        raise HTTPException(status_code=400, detail="未找到可合并的数据 sheet（需要总表含「明细」「已发运」「未发运」）")

    # 交货号区间
    delivery_range = None
    if delivery_min and delivery_max:
        try:
            delivery_range = (int(delivery_min.strip()), int(delivery_max.strip()))
        except (ValueError, TypeError):
            pass

    # 执行合并
    result = merge_files(
        file_paths=file_paths,
        selected_sheets=selected_keys,
        provinces=[],
        rule_id=None,
        output_dir=config.OUTPUT_DIR,
        output_prefix="邮件合并结果",
        manual_mappings=None,
        delivery_range=delivery_range,
    )

    stats = result["stats"]
    stats["selected_sheets"] = len(selected_keys)
    stats["sheet_count"] = 7 if stats.get("omo_detail_count", 0) > 0 else 5
    stats["source_files"] = source_desc
    stats["source_sheets"] = [
        {"name": info["sheet_name"], "rows": info["row_count"], "file": info["filename"]}
        for info in sheets_map.values()
    ]

    return JSONResponse(content={
        "status": "success",
        "stats": stats,
        "previews": result["previews"],
        "download_url": "/api/mail-merge/download",
    })


# ===================== 下载结果 =====================

@router.get("/download")
async def download(request: Request):
    """下载最近的合并结果"""
    if not auth.get_current_user(request):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    files = [f for f in os.listdir(config.OUTPUT_DIR)
             if f.startswith("邮件合并结果") and f.endswith(".xlsx")]
    if not files:
        files = [f for f in os.listdir(config.OUTPUT_DIR) if f.endswith(".xlsx")]
    if not files:
        raise HTTPException(status_code=404, detail="没有可下载的文件")
    files.sort(key=lambda f: os.path.getmtime(os.path.join(config.OUTPUT_DIR, f)), reverse=True)
    latest = files[0]
    return FileResponse(
        os.path.join(config.OUTPUT_DIR, latest),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=latest,
    )
