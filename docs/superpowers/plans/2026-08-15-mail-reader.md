# 邮件读取器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 定时从 126 邮箱读取邮件，按日期+主题关键词筛选，下载 Excel 附件，自动跑合并+省份筛选，产出结果 Excel。

**Architecture:** 抽取 `app.py` 的合并核心为 `merger.py`（纯函数），新建独立的 `mail_reader.py`（标准库 imaplib + time.sleep 定时循环）调用它。零新增运行时依赖，仅 dev 加 pytest。

**Tech Stack:** Python 3.11、imaplib/email/json/time（标准库）、openpyxl/xlrd（复用现有）、pytest（dev）。

---

## 文件结构

| 文件 | 操作 | 职责 |
|---|---|---|
| `merger.py` | 创建 | 合并核心纯函数（从 app.py 迁移）+ `merge_files()` |
| `mail_reader.py` | 创建 | 邮件读取、附件下载、去重、定时循环 |
| `mail_config.example.json` | 创建 | 配置模板（提交到 git，不含真实授权码） |
| `mail_config.json` | 创建（gitignore） | 真实配置（含授权码，不入库） |
| `tests/test_merger.py` | 创建 | merger 纯函数 + 端到端测试 |
| `tests/test_mail_reader.py` | 创建 | mail_reader 纯逻辑测试 |
| `app.py` | 修改 | `/api/process` 改调 `merger.merge_files`，删除已迁移函数 |
| `requirements.txt` | 修改 | 加 `pytest`（dev 依赖，实际放 requirements-dev.txt） |
| `requirements-dev.txt` | 创建 | 仅 pytest |
| `.gitignore` | 修改 | 忽略 `mail_config.json` |

---

## Task 1: 引入测试基础设施

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`（空）
- Modify: `.gitignore`

- [ ] **Step 1: 创建 requirements-dev.txt**

```text
pytest>=7.0.0
```

- [ ] **Step 2: 创建 tests 目录与空 __init__.py**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 3: .gitignore 追加 mail_config.json**

在 `.gitignore` 末尾追加一行：

```text
mail_config.json
```

- [ ] **Step 4: 安装并验证 pytest**

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest --version
```

Expected: 显示 pytest 版本号，无报错。

- [ ] **Step 5: Commit**

```bash
git add requirements-dev.txt tests/__init__.py .gitignore
git commit -m "test: 引入 pytest 基础设施"
```

---

## Task 2: 抽取 merger.py 的纯函数与常量

从 `app.py` 迁移以下内容到 `merger.py`（保持代码原样，仅移动）：

**迁移的常量：**
- `RULES_FILE`、`BUILTIN_RULE_ID`、`BUILTIN_RULE`（app.py:36-103）
- `REGIONS_FILE`、`REGION_KEYWORDS`（app.py:290, 327）
- `PREVIEW_MAX_ROWS`、`SAMPLE_ROWS`（app.py:33-34）

**迁移的函数：**
- `load_rules` / `save_rules`（app.py:106-123）
- `normalize_str`（126）
- `match_columns_to_rule`（133-196）
- `apply_value_mappings`（199-233）
- `build_region_keywords`（293-324）
- `get_province_list`（330-334）
- `match_province`（337-349）
- `match_row_province`（352-371）
- `serialize_cell`（376-383）
- `_to_number`（386-393）
- `_format_date_text`（396-412）
- `_try_parse_date`（415-429）
- `build_pivot_by_delivery`（432-525）
- `build_pivot_by_factory_delivery`（528-611）
- `_parse_sheet_rows`（614-628）
- `_detect_file_type`（631-650）
- `_read_text_table`（653-691）
- `read_all_sheets`（694-731）

**Files:**
- Create: `merger.py`
- Modify: `app.py`

- [ ] **Step 1: 创建 merger.py 并写入迁移内容**

创建 `merger.py`，头部 import 与文档说明：

```python
"""合并核心逻辑（从 app.py 抽出，供 Web 与邮件读取器共用）"""
import os
import re
import json
import datetime
from collections import OrderedDict
from typing import List, Dict, Tuple, Optional

import openpyxl
import xlrd

RULES_FILE = os.path.join(os.path.dirname(__file__), "rules.json")
REGIONS_FILE = os.path.join(os.path.dirname(__file__), "china_regions.json")

PREVIEW_MAX_ROWS = 200
SAMPLE_ROWS = 10
BUILTIN_RULE_ID = "_builtin_default"
```

然后将上表列出的 `BUILTIN_RULE`、`load_rules`、`save_rules`、`normalize_str`、`match_columns_to_rule`、`apply_value_mappings`、`build_region_keywords`、`get_province_list`、`match_province`、`match_row_province`、`serialize_cell`、`_to_number`、`_format_date_text`、`_try_parse_date`、`build_pivot_by_delivery`、`build_pivot_by_factory_delivery`、`_parse_sheet_rows`、`_detect_file_type`、`_read_text_table`、`read_all_sheets`、`REGION_KEYWORDS = build_region_keywords()` **原样粘贴**到 `merger.py`。

- [ ] **Step 2: app.py 改为从 merger 导入，删除已迁移代码**

`app.py` 顶部 import 改为：

```python
from merger import (
    RULES_FILE, BUILTIN_RULE_ID, BUILTIN_RULE,
    load_rules, save_rules, normalize_str, match_columns_to_rule,
    apply_value_mappings, build_region_keywords, get_province_list,
    match_province, match_row_province, serialize_cell, _to_number,
    _format_date_text, _try_parse_date, build_pivot_by_delivery,
    build_pivot_by_factory_delivery, _parse_sheet_rows, _detect_file_type,
    _read_text_table, read_all_sheets, REGION_KEYWORDS,
)
```

删除 `app.py` 中已迁移的函数与常量定义。

- [ ] **Step 3: 验证应用仍能启动**

```bash
python3 -c "import app; print('app import OK')"
```

Expected: 打印 `app import OK`，无 ImportError。

- [ ] **Step 4: Commit**

```bash
git add merger.py app.py
git commit -m "refactor: 抽取合并纯函数到 merger.py"
```

---

## Task 3: 实现 merge_files 主流程（merger.py）

将 `/api/process` 中的合并主流程（app.py 原 1051-1225 行逻辑）抽取为 `merge_files`。

**Files:**
- Create: `tests/test_merger.py`
- Modify: `merger.py`

- [ ] **Step 1: 写失败测试（端到端）**

创建 `tests/test_merger.py`：

```python
import os
import openpyxl
from merger import merge_files, match_columns_to_rule, BUILTIN_RULE, match_row_province


def _make_xlsx(path, headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_match_columns_to_rule_exact():
    headers = ["交货", "交货量", "总重量"]
    result = match_columns_to_rule(headers, BUILTIN_RULE)
    mapped = dict(result)
    assert mapped["交货"] == "交货"
    assert mapped["交货量"] == "交货量"


def test_match_row_province():
    from merger import REGION_KEYWORDS
    assert REGION_KEYWORDS  # 行政区划数据已加载
    row = {"送达方地点": "苏州市", "街道": "江苏省苏州市工业园区"}
    assert match_row_province(row, ["江苏"]) is True
    assert match_row_province(row, ["浙江"]) is False


def test_merge_files_end_to_end(tmp_path):
    f = os.path.join(tmp_path, "a.xlsx")
    _make_xlsx(f, ["交货", "项目", "交货量", "送达方地点"],
               [["1001", "10", 5, "苏州市"],
                ["1002", "20", 3, "杭州市"]])
    out_dir = os.path.join(tmp_path, "out")
    os.makedirs(out_dir, exist_ok=True)
    result = merge_files([f], selected_sheets=None, provinces=["江苏"],
                         rule_id=None, output_dir=out_dir, output_prefix="测试")
    assert os.path.exists(result["output_path"])
    assert result["stats"]["filtered_rows"] == 1  # 只保留苏州
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_merger.py -v
```

Expected: FAIL，`ImportError: cannot import name 'merge_files'`。

- [ ] **Step 3: 实现 merge_files**

在 `merger.py` 末尾追加：

```python
def merge_files(
    file_paths: List[str],
    selected_sheets: Optional[List[str]] = None,
    provinces: Optional[List[str]] = None,
    rule_id: Optional[str] = None,
    output_dir: str = "output",
    output_prefix: str = "合并结果",
    manual_mappings: Optional[Dict] = None,
) -> Dict:
    """合并多个 Excel 文件为统一标准列，可选按省份筛选，输出 Excel。

    selected_sheets: sheet key 列表，格式 f"{文件名}::{sheet名}"；None 表示全选。
    provinces: 省份列表；None/[] 表示不筛选（全量）。
    rule_id: 规则 id；None 使用内置默认规则。
    manual_mappings: 手动列名映射 {sheet_key: {原始列名: 标准列名}}；None 表示仅自动匹配。
    返回 {output_path, stats}。
    """
    os.makedirs(output_dir, exist_ok=True)
    prov_list = provinces or []

    files_data = {}
    for fp in file_paths:
        fname = os.path.basename(fp)
        files_data[fname] = read_all_sheets(fp)

    # 确定 active_rule 与标准列顺序
    active_rule = BUILTIN_RULE
    std_header_order = [sh["name"] for sh in BUILTIN_RULE["standard_headers"] if sh.get("name", "").strip()]
    if rule_id:
        for r in load_rules():
            if r["id"] == rule_id:
                active_rule = r
                std_header_order = [sh["name"] for sh in r["standard_headers"] if sh.get("name", "").strip()]
                break

    # selected_sheets 为 None 时全选所有 sheet
    if selected_sheets is None:
        selected_set = set()
        for fname, sheets in files_data.items():
            for sname in sheets:
                selected_set.add(f"{fname}::{sname}")
    else:
        selected_set = set(selected_sheets)

    std_col_set = set(std_header_order)
    all_columns = list(std_header_order)

    # 合并所有数据行
    merged_rows = []
    for fname, sheets in files_data.items():
        for sname, (headers, data_rows) in sheets.items():
            key = f"{fname}::{sname}"
            if key not in selected_set:
                continue
            auto_map_list = match_columns_to_rule(headers, active_rule)
            manual_map = (manual_mappings or {}).get(key, {})
            mapped_headers = []
            assigned_std = set()
            for i, h in enumerate(headers):
                hs = str(h) if h else ""
                manual_target = manual_map.get(hs, "")
                std_name = None
                if manual_target and manual_target in std_col_set and manual_target not in assigned_std:
                    std_name = manual_target
                if not std_name and i < len(auto_map_list):
                    auto_std = auto_map_list[i][1] if auto_map_list[i] else None
                    if auto_std and auto_std in std_col_set and auto_std not in assigned_std:
                        std_name = auto_std
                if not std_name and hs in std_col_set and hs not in assigned_std:
                    std_name = hs
                if std_name:
                    mapped_headers.append(std_name)
                    assigned_std.add(std_name)
                else:
                    mapped_headers.append(None)
            for row in data_rows:
                row_dict = {}
                for idx, h in enumerate(mapped_headers):
                    if h is None:
                        continue
                    row_dict[h] = row[idx] if idx < len(row) else None
                for sh in active_rule.get("standard_headers", []):
                    vm = sh.get("value_mappings")
                    if vm:
                        apply_value_mappings(row_dict, sh["name"], vm, fname)
                merged_rows.append(row_dict)

    # 对齐 + 去重 + 过滤非法交货号
    aligned = []
    seen_keys = set()
    for row in merged_rows:
        aligned_row = {col: (row.get(col) if row.get(col) is not None else "") for col in all_columns}
        jh_val = str(aligned_row.get("交货", "")).strip()
        if jh_val and not jh_val.isdigit():
            continue
        if not jh_val:
            continue
        dedup_key = (jh_val, str(aligned_row.get("项目", "")).strip())
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        aligned.append(aligned_row)

    # 省份筛选
    if prov_list:
        filtered = [row for row in aligned if match_row_province(row, prov_list)]
    else:
        filtered = aligned

    # 构建多 Sheet 输出
    wb = openpyxl.Workbook()
    output_headers = ["售达方" if h == "售达方的名字" else h for h in all_columns]

    ws1 = wb.active
    ws1.title = "全量数据"
    ws1.append(output_headers)
    for row in aligned:
        ws1.append([row.get(h, "") for h in all_columns])

    ws3 = wb.create_sheet("筛选数据")
    ws3.append(output_headers)
    for row in filtered:
        ws3.append([row.get(h, "") for h in all_columns])

    p4_headers, p4_data, text_dates = build_pivot_by_delivery(filtered)
    ws4 = wb.create_sheet("交货汇总")
    ws4.append(p4_headers)
    for row in p4_data:
        ws4.append(row)

    p5_headers = list(p4_headers)
    ws5 = wb.create_sheet("交货汇总_文本日期")
    ws5.append(p5_headers)
    for row in p4_data:
        new_row = list(row)
        delivery = str(new_row[0]).strip() if new_row[0] else ""
        if delivery == "(空白)":
            if len(new_row) > 8:
                new_row[8] = None
        elif delivery != "总计":
            orig = text_dates.get(delivery, {})
            if len(new_row) > 7 and new_row[7] is None and orig.get("发货日期"):
                new_row[7] = _format_date_text(orig["发货日期"])
            if len(new_row) > 8 and new_row[8] is None and orig.get("交货日期"):
                new_row[8] = _format_date_text(orig["交货日期"])
            if len(new_row) > 6 and new_row[6] is None and orig.get("街道"):
                new_row[6] = orig["街道"]
        ws5.append(new_row)

    p2_headers, p2_data = build_pivot_by_factory_delivery(aligned)
    ws2 = wb.create_sheet("工厂交货透视")
    for row in p2_data:
        ws2.append(row)

    today = datetime.datetime.now().strftime("%Y%m%d")
    short_hash = hashlib.md5(f"{today}_{len(filtered)}_{datetime.datetime.now().strftime('%H%M%S%f')}".encode()).hexdigest()[:8]
    prov_short = "_".join(p.replace("省", "").replace("市", "") for p in prov_list[:3]) if prov_list else "全部"
    output_filename = f"{output_prefix}_{prov_short}_{today}_{short_hash}.xlsx"
    output_path = os.path.join(output_dir, output_filename)
    wb.save(output_path)
    wb.close()

    stats = {
        "total_merged_rows": len(merged_rows),
        "total_columns": len(all_columns),
        "filtered_rows": len(filtered),
        "provinces": prov_list,
    }

    previews = []
    filter_preview_rows = [[row.get(h, "") for h in all_columns] for row in filtered[:PREVIEW_MAX_ROWS]]
    if filter_preview_rows:
        previews.append({
            "sheet_name": "筛选数据",
            "headers": output_headers,
            "rows": [[serialize_cell(c) for c in r] for r in filter_preview_rows],
            "total": len(filtered),
            "preview_count": len(filter_preview_rows),
        })
    previews.append({
        "sheet_name": "交货汇总",
        "headers": [str(h) for h in p4_headers],
        "rows": [[serialize_cell(c) for c in row] for row in p4_data[:PREVIEW_MAX_ROWS]],
        "total": len(p4_data),
        "preview_count": min(len(p4_data), PREVIEW_MAX_ROWS),
    })
    previews.append({
        "sheet_name": "工厂交货透视",
        "headers": [str(h) for h in p2_headers],
        "rows": [[serialize_cell(c) for c in row] for row in p2_data[:PREVIEW_MAX_ROWS]],
        "total": len(p2_data),
        "preview_count": min(len(p2_data), PREVIEW_MAX_ROWS),
    })

    return {"output_path": output_path, "stats": stats, "previews": previews}
```

同时在 `merger.py` 顶部补 `import hashlib`。

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_merger.py -v
```

Expected: PASS（3 个测试全绿）。

- [ ] **Step 5: Commit**

```bash
git add merger.py tests/test_merger.py
git commit -m "feat: merger.merge_files 合并主流程"
```

---

## Task 4: app.py 的 /api/process 改调 merge_files

**Files:**
- Modify: `app.py`

- [ ] **Step 1: 重写 /api/process 处理函数**

将 `/api/process` 中「合并 + 输出 + 预览」部分（原 app.py 约 1051-1277 行）替换为调用 `merge_files`，保留 Form 参数解析与预览 JSON 构建。

```python
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
```

注意：`merge_files` 已返回 `previews`，`/api/process` 直接透传，网页 Step 3 预览功能完整保留。

- [ ] **Step 2: 验证 /api/process 仍可用**

```bash
python3 -c "import app; print('OK')"
```

Expected: `OK`。

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "refactor: /api/process 改调 merger.merge_files"
```

---

## Task 5: mail_reader 核心（配置加载 + IMAP 连接 + 搜索 + 附件下载）

**Files:**
- Create: `mail_reader.py`
- Create: `tests/test_mail_reader.py`

- [ ] **Step 1: 写失败测试（纯逻辑部分）**

创建 `tests/test_mail_reader.py`：

```python
from mail_reader import matches_keywords, is_excel_attachment, filter_new_uids


def test_matches_keywords_or():
    assert matches_keywords("8月总表数据", ["总表", "月报"]) is True
    assert matches_keywords("客户月报", ["总表", "月报"]) is True
    assert matches_keywords("无关邮件", ["总表", "月报"]) is False


def test_is_excel_attachment():
    assert is_excel_attachment("a.xlsx") is True
    assert is_excel_attachment("b.XLS") is True
    assert is_excel_attachment("c.csv") is True
    assert is_excel_attachment("d.tsv") is True
    assert is_excel_attachment("e.pdf") is False


def test_filter_new_uids():
    processed = {b"1", b"2"}
    new = filter_new_uids([b"1", b"2", b"3"], processed)
    assert new == [b"3"]
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_mail_reader.py -v
```

Expected: FAIL，`ImportError`。

- [ ] **Step 3: 实现 mail_reader.py 纯逻辑 + IMAP 交互**

创建 `mail_reader.py`：

```python
"""邮件读取器：从 126 邮箱读取 Excel 附件，自动合并筛选。"""
import os
import re
import json
import time
import imaplib
import email
import datetime
import tempfile
from email.header import decode_header
from typing import List, Set, Optional

from merger import merge_files


# ---------- 纯逻辑（可测试） ----------

def matches_keywords(subject: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    return any(k and k in subject for k in keywords)


def is_excel_attachment(filename: str) -> bool:
    return filename.lower().endswith((".xlsx", ".xls", ".csv", ".tsv"))


def decode_subject(raw) -> str:
    if not raw:
        return ""
    parts = decode_header(raw)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def load_processed_uids(path: str) -> Set[bytes]:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(x.encode() for x in data)


def save_processed_uids(path: str, uids: Set[bytes]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(x.decode() for x in uids), f)


def filter_new_uids(uids: List[bytes], processed: Set[bytes]) -> List[bytes]:
    return [u for u in uids if u not in processed]


# ---------- IMAP 交互 ----------

def connect_imap(host: str, email_addr: str, auth_code: str) -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL(host, 993)
    imap.login(email_addr, auth_code)
    return imap


def search_mails(imap: imaplib.IMAP4_SSL, since_date: datetime.date) -> List[bytes]:
    """搜索某日期及之后的所有邮件 UID。"""
    imap.select("INBOX")
    date_str = since_date.strftime("%d-%b-%Y")
    typ, data = imap.uid("search", None, f"(SINCE {date_str})")
    if typ != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def download_excel_attachments(imap: imaplib.IMAP4_SSL, uid: bytes, dest_dir: str) -> List[str]:
    """下载某封邮件的 Excel 附件到 dest_dir，返回本地路径列表。"""
    typ, msg_data = imap.uid("fetch", uid, "(RFC822)")
    if typ != "OK":
        return []
    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)
    saved = []
    for part in msg.walk():
        filename = part.get_filename()
        if not filename:
            continue
        decoded = decode_subject(filename)
        if not is_excel_attachment(decoded):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        safe_name = f"{uid.decode()}_{decoded}"
        path = os.path.join(dest_dir, safe_name)
        with open(path, "wb") as f:
            f.write(payload)
        saved.append(path)
    return saved
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_mail_reader.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add mail_reader.py tests/test_mail_reader.py
git commit -m "feat: mail_reader 纯逻辑与 IMAP 交互"
```

---

## Task 6: mail_reader 主流程 + 定时循环

**Files:**
- Modify: `mail_reader.py`

- [ ] **Step 1: 实现 process_once 与 main 循环**

在 `mail_reader.py` 末尾追加：

```python
def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_once(cfg: dict) -> int:
    """执行一轮：搜索→过滤→下载→合并→记录 UID。返回处理邮件数。"""
    since = datetime.date.today() - datetime.timedelta(days=max(0, int(cfg.get("days_back", 1)) - 1))
    uids_file = cfg.get("processed_uids_file", "processed_uids.json")
    processed = load_processed_uids(uids_file)
    output_dir = cfg.get("output_dir", "output")

    imap = connect_imap(cfg["imap_host"], cfg["email"], cfg["auth_code"])
    try:
        uids = search_mails(imap, since)
        new_uids = filter_new_uids(uids, processed)
        keywords = cfg.get("subject_keywords", [])
        handled = 0
        for uid in new_uids:
            try:
                typ, data = imap.uid("fetch", uid, "(BODY[HEADER.FIELDS (SUBJECT)])")
                subject = ""
                if typ == "OK" and data and data[0]:
                    m = email.message_from_bytes(data[0][1])
                    subject = decode_subject(m.get("Subject", ""))
                if not matches_keywords(subject, keywords):
                    continue
                with tempfile.TemporaryDirectory() as tmp:
                    files = download_excel_attachments(imap, uid, tmp)
                    if not files:
                        continue
                    merge_files(
                        file_paths=files,
                        selected_sheets=None,
                        provinces=cfg.get("provinces", []),
                        rule_id=cfg.get("rule_id"),
                        output_dir=output_dir,
                        output_prefix=cfg.get("output_prefix", "邮件合并"),
                    )
                processed.add(uid)
                handled += 1
            except Exception as e:
                print(f"[mail_reader] 处理邮件 {uid.decode()} 失败: {e}")
        save_processed_uids(uids_file, processed)
        return handled
    finally:
        imap.logout()


def main():
    cfg_path = os.environ.get("MAIL_CONFIG", "mail_config.json")
    cfg = load_config(cfg_path)
    interval = int(cfg.get("poll_interval_seconds", 3600))
    print(f"[mail_reader] 启动，轮询间隔 {interval}s，配置 {cfg_path}")
    while True:
        try:
            n = process_once(cfg)
            print(f"[mail_reader] 本轮处理 {n} 封邮件: {datetime.datetime.now()}")
        except Exception as e:
            print(f"[mail_reader] 本轮异常: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 语法与导入检查**

```bash
python3 -c "import mail_reader; print('OK')"
```

Expected: `OK`。

- [ ] **Step 3: Commit**

```bash
git add mail_reader.py
git commit -m "feat: mail_reader 主流程与定时循环"
```

---

## Task 7: 配置模板 + 使用文档

**Files:**
- Create: `mail_config.example.json`

- [ ] **Step 1: 创建配置模板**

创建 `mail_config.example.json`：

```json
{
  "imap_host": "imap.126.com",
  "email": "your_account@126.com",
  "auth_code": "你的126客户端授权码",
  "subject_keywords": ["总表", "月报"],
  "provinces": [],
  "days_back": 1,
  "poll_interval_seconds": 3600,
  "output_dir": "output",
  "output_prefix": "邮件合并",
  "processed_uids_file": "processed_uids.json"
}
```

- [ ] **Step 2: 运行方式说明（写入回复，不建文档文件）**

启动命令：

```bash
cp mail_config.example.json mail_config.json
# 编辑 mail_config.json 填入真实邮箱与授权码
python mail_reader.py
```

- [ ] **Step 3: Commit**

```bash
git add mail_config.example.json
git commit -m "docs: 邮件读取器配置模板"
```

---

## Task 8: 端到端验证（本地真实文件）

**Files:** 无新增

- [ ] **Step 1: 用仓库内示例 xlsx 验证 merge_files**

```bash
python3 -c "
from merger import merge_files
import glob
files = glob.glob('*.xlsx')
r = merge_files(files, selected_sheets=None, provinces=[], rule_id=None, output_dir='output', output_prefix='验证')
print('输出:', r['output_path'])
print('统计:', r['stats'])
"
```

Expected: 打印输出文件路径与统计，且 `output/` 下生成 xlsx。

- [ ] **Step 2: 全量测试通过**

```bash
pytest tests/ -v
```

Expected: 全部 PASS。

- [ ] **Step 3: Commit（如无改动则跳过）**

---

## 说明与后续

- 126 授权码获取：登录 126 邮箱网页版 → 设置 → POP3/SMTP/IMAP → 开启 IMAP → 生成「客户端授权码」。
