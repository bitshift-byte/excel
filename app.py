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

app = FastAPI(title="Excel 合并筛选系统")

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

PREVIEW_MAX_ROWS = 200
SAMPLE_ROWS = 10

RULES_FILE = os.path.join(os.path.dirname(__file__), "rules.json")

# ===================== 规则管理 =====================

# 内置默认规则 ID
BUILTIN_RULE_ID = "_builtin_default"

# 内置默认规则：联合利华标准34列 + 列名变体映射
BUILTIN_RULE = {
    "id": BUILTIN_RULE_ID,
    "name": "联合利华标准34列（内置）",
    "builtin": True,
    "standard_headers": [
        {"name": "交货", "source_columns": ["交货", "交货号"]},
        {"name": "DlvTy", "source_columns": ["DlvTy", "交货类型"]},
        {"name": "项目", "source_columns": ["项目", "    项目"]},
        {"name": "物料", "source_columns": ["物料", "物料号"]},
        {"name": "描述", "source_columns": ["描述", "物料描述"]},
        {"name": "存储位置", "source_columns": ["存储位置", "位置"]},
        {"name": "销售凭证", "source_columns": ["销售凭证", "销售订单"]},
        {"name": "运达方", "source_columns": ["运达方", "送达方"]},
        {"name": "运达方的名字", "source_columns": ["运达方的名字", "运达方名称"]},
        {"name": "送达方地点", "source_columns": ["送达方地点", "城市"]},
        {"name": "名称 3", "source_columns": ["名称 3", "名称3"]},
        {
            "name": "工厂",
            "source_columns": ["工厂", "Plant"],
            "value_mappings": [
                {"source_file_contains": "分销-下单量", "source_value": "8136", "target_value": "701"},
                {"source_file_contains": "分销-下单量", "source_value": "8137", "target_value": "701"},
                {"source_file_contains": "分销报表", "source_value": "8136", "target_value": "901"},
                {"source_file_contains": "分销报表", "source_value": "8137", "target_value": "901"},
                {"source_file_contains": "分销报表", "source_value": "8205", "target_value": "901"},
                {"source_file_contains": "跑单明细", "source_value": "8136", "target_value": "801"},
                {"source_file_contains": "跑单明细", "source_value": "8137", "target_value": "801"},
                {"source_file_contains": "跑单明细", "source_value": "8205", "target_value": "801"},
            ],
        },
        {"name": "路线", "source_columns": ["路线", "Route"]},
        {"name": "OPS", "source_columns": ["OPS", "全部拣配状态"]},
        {"name": "WhN", "source_columns": ["WhN", "仓库号"]},
        {"name": "批次", "source_columns": ["批次", "Batch"]},
        {"name": "仓位", "source_columns": ["仓位"]},
        {"name": "GM", "source_columns": ["GM", "GS", "货物移动状态"]},
        {"name": "销售组织", "source_columns": ["销售组织", "SOrg.", "SOrg"]},
        {"name": "售达方", "source_columns": ["售达方", "售达方代码"]},
        {"name": "售达方的名字", "source_columns": ["售达方的名字", "售达方名称"]},
        {
            "name": "街道",
            "source_columns": ["街道", "街道地址"],
            "value_mappings": [
                {"when_column": "工厂", "equals": "901", "use_column": "送达方地点"},
            ],
        },
        {"name": "街道2", "source_columns": ["街道2", "街道 2"]},
        {"name": "街道 3", "source_columns": ["街道 3", "街道3"]},
        {"name": "交货量", "source_columns": ["交货量", "交货数量", "    交货量"]},
        {"name": "SU", "source_columns": ["SU", "销售单位"]},
        {"name": "数量(库存单位)", "source_columns": ["数量(库存单位)", "库存数量"]},
        {"name": "计", "source_columns": ["计", "计数", "基本计量单位"]},
        {"name": "总重量", "source_columns": ["总重量", "         总重量"]},
        {"name": "WUn", "source_columns": ["WUn", "重量单位"]},
        {"name": "业务量", "source_columns": ["业务量", "          业务量"]},
        {"name": "VUn", "source_columns": ["VUn", "体积单位"]},
        {"name": "交货日期", "source_columns": ["交货日期", "交货日期(从/到)"]},
        {"name": "发货日期", "source_columns": ["发货日期", "实际发货日", "实际货物移动日期"]},
    ],
}


def load_rules() -> list:
    """从 rules.json 读取规则列表，始终在列表首位插入内置默认规则"""
    user_rules = []
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                user_rules = json.load(f)
        except (json.JSONDecodeError, IOError):
            user_rules = []
    # 内置规则始终在最前面
    return [BUILTIN_RULE] + user_rules


def save_rules(rules: list):
    """将规则列表写入 rules.json（自动过滤内置规则）"""
    user_rules = [r for r in rules if not r.get("builtin")]
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(user_rules, f, ensure_ascii=False, indent=2)


def normalize_str(s: str) -> str:
    """标准化字符串用于模糊匹配：去首尾空格 + 转小写 + 去内部空格/下划线"""
    if not s:
        return ""
    return s.strip().lower().replace(" ", "").replace("_", "")


def match_columns_to_rule(headers: list, rule: dict) -> list:
    """
    将表头列表与规则中的标准表头匹配。
    返回映射列表: [(原始列名, 标准表头名), ...]，长度等于 headers，未匹配的为 None。
    支持重复列名：同一列名出现多次时可分别映射到不同标准列。

    匹配策略：
    1. 先精确匹配（normalize 后相等）
    2. 再包含匹配（normalize 后 source_column 是 header 的子串，或反之）
    3. 一个表头只匹配第一个命中的标准表头
    4. 多个表头匹配同一标准表头时取第一个，其余尝试下一个标准表头
    """
    std_headers = rule.get("standard_headers", [])
    # 返回 list of (header_text, std_name or None)
    result = []
    used_targets = set()  # 已被占用的标准表头名

    for header in headers:
        hs = str(header) if header else ""
        if not hs:
            result.append((hs, None))
            continue
        hs_norm = normalize_str(hs)
        matched = None

        # Pass 1: 精确匹配
        for sh in std_headers:
            target = sh.get("name", "")
            if not target or target in used_targets:
                continue
            for sc in sh.get("source_columns", []):
                if normalize_str(sc) == hs_norm:
                    matched = target
                    break
            if matched:
                break

        # Pass 2: 包含匹配（要求较长的匹配长度，避免短词误匹配）
        if not matched:
            for sh in std_headers:
                target = sh.get("name", "")
                if not target or target in used_targets:
                    continue
                for sc in sh.get("source_columns", []):
                    sc_norm = normalize_str(sc)
                    if not sc_norm:
                        continue
                    # 包含匹配：要求匹配长度至少为较长一方的 50%
                    max_len = max(len(sc_norm), len(hs_norm))
                    min_len = min(len(sc_norm), len(hs_norm))
                    if sc_norm in hs_norm or hs_norm in sc_norm:
                        if min_len >= max_len * 0.5:
                            matched = target
                            break
                if matched:
                    break

        if matched:
            used_targets.add(matched)
            result.append((hs, matched))
        else:
            result.append((hs, None))

    return result


def apply_value_mappings(row_dict: dict, std_name: str, value_mappings: list, filename: str) -> bool:
    """对某行的指定标准列应用值映射规则。如果有变更返回 True 并直接修改 row_dict。
    
    支持两种映射类型：
    1. 源文件名 + 源值 → 目标值：
       {"source_file_contains": "分销-下单量", "source_value": "8136", "target_value": "701"}
    2. 条件跨列映射（当某列等于某值时，用另一列的值替换）：
       {"when_column": "工厂", "equals": "901", "use_column": "送达方地点"}
    """
    if not value_mappings:
        return False
    current_val = row_dict.get(std_name, "")
    current_str = str(current_val).strip() if current_val is not None else ""
    
    for vm in value_mappings:
        # Type 1: source file + source value -> target value
        if "source_file_contains" in vm and "source_value" in vm:
            file_keyword = vm.get("source_file_contains", "")
            src_val = str(vm.get("source_value", "")).strip()
            if file_keyword in filename and current_str == src_val:
                row_dict[std_name] = vm.get("target_value", "")
                return True
        # Type 2: conditional cross-column mapping
        elif "when_column" in vm and "equals" in vm:
            when_col = vm.get("when_column", "")
            when_val = str(row_dict.get(when_col, "")).strip() if row_dict.get(when_col) is not None else ""
            equals_val = str(vm.get("equals", "")).strip()
            if when_val == equals_val:
                if vm.get("use_column"):
                    row_dict[std_name] = row_dict.get(vm["use_column"], "")
                    return True
                elif vm.get("target_value") is not None:
                    row_dict[std_name] = vm.get("target_value", "")
                    return True
    return False


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


# ===================== 行政区划数据 =====================

REGIONS_FILE = os.path.join(os.path.dirname(__file__), "china_regions.json")


def build_region_keywords() -> Dict[str, list]:
    with open(REGIONS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    regions = {}
    for prov, cities in raw.items():
        keywords = set()
        keywords.add(prov)
        short_prov = prov
        for suffix in ["省", "自治区", "壮族", "回族", "维吾尔"]:
            short_prov = short_prov.replace(suffix, "")
        if short_prov:
            keywords.add(short_prov)

        for city, counties in cities.items():
            keywords.add(city)
            short_city = city
            for suffix in ["市", "自治州", "地区", "盟"]:
                short_city = short_city.replace(suffix, "")
            if short_city:
                keywords.add(short_city)

            for county in counties:
                keywords.add(county)
                for suffix in ["区", "县", "市", "旗", "自治县", "自治区"]:
                    if county.endswith(suffix) and len(county) > len(suffix) + 1:
                        keywords.add(county[: -len(suffix)])

        keywords = sorted([k for k in keywords if len(k) >= 2])
        regions[prov] = keywords

    return regions


REGION_KEYWORDS = build_region_keywords()


def get_province_list() -> list:
    return [
        {"name": prov, "keyword_count": len(kws)}
        for prov, kws in sorted(REGION_KEYWORDS.items())
    ]


def match_province(value, provinces: list) -> bool:
    """检查某个值（城市名/街道地址）是否匹配选中省份"""
    if not value or not provinces:
        return False
    s = str(value).strip()
    if not s:
        return False
    for prov in provinces:
        kws = REGION_KEYWORDS.get(prov, [])
        for kw in kws:
            if s.startswith(kw):
                return True
    return False


def match_row_province(row: dict, provinces: list) -> bool:
    """检查一行数据是否匹配选中省份：优先看'送达方地点'，再看'街道'"""
    if not provinces:
        return True  # 未选省份时全部通过
    # 优先检查"送达方地点"（城市级别，用 startswith 精确匹配）
    for col_name in ["送达方地点", "城市"]:
        val = row.get(col_name)
        if val and match_province(val, provinces):
            return True
    # 再检查"街道"地址（地址通常以省名开头，用 startswith 匹配省份名）
    for col_name in ["街道", "名称 3", "街道 3"]:
        val = row.get(col_name)
        if val:
            s = str(val).strip()
            for prov in provinces:
                kws = REGION_KEYWORDS.get(prov, [])
                for kw in kws:
                    if s.startswith(kw):
                        return True
    return False




def serialize_cell(val):
    if val is None:
        return ""
    if isinstance(val, datetime.datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, datetime.date):
        return val.strftime("%Y-%m-%d")
    return str(val)


def _to_number(val):
    """尝试将值转为 float，失败返回 None"""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _format_date_text(val) -> str:
    """将日期值转为 'YYYY.MM.DD' 文本格式"""
    if val is None or val == "":
        return ""
    if isinstance(val, datetime.datetime):
        return val.strftime("%Y.%m.%d")
    if isinstance(val, datetime.date):
        return val.strftime("%Y.%m.%d")
    s = str(val).strip()
    # 尝试解析常见的日期格式
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.strftime("%Y.%m.%d")
        except ValueError:
            pass
    return s


def _try_parse_date(val):
    """尝试将值转为 datetime，失败则返回 None"""
    if val is None or (isinstance(val, str) and not val.strip()):
        return None
    if isinstance(val, datetime.datetime):
        return val
    if isinstance(val, datetime.date):
        return datetime.datetime(val.year, val.month, val.day)
    s = str(val).strip()
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def build_pivot_by_delivery(filtered_rows: list) -> list:
    """Sheet4/Sheet5: 按交货号汇总透视表（从 Sheet3 筛选数据构建）
    列: 交货, 销售凭证, 运达方, 运达方的名字, 送达方地点, 工厂, 街道, 发货日期, 交货日期, 求和项:交货量, 求和项:总重量, 求和项:业务量

    Sheet4 规则（模拟 Excel 透视表行为）：
    - 数值列：SUM 求和
    - 日期为 datetime → Sheet4 保持 datetime，街道保持原值
    - 日期为文本格式(str) → Sheet4 中日期=None，街道=None（Excel 透视表丢弃文本日期行字段）

    Sheet5 规则：Sheet4 的副本，但 None 的日期/街道用 Sheet3 原始文本值回填
    """
    pivot_map = OrderedDict()
    # 保存 Sheet3 中的原始文本值（用于 Sheet5 回填）
    sheet3_orig = {}  # delivery -> {"发货日期": orig_val, "交货日期": orig_val, "街道": orig_val}

    for row in filtered_rows:
        delivery = str(row.get("交货", "")).strip()
        if not delivery:
            continue
        fa_val = row.get("发货日期", "")
        jr_val = row.get("交货日期", "")
        street_val = row.get("街道", "")

        # 收集原始值（用于 Sheet5 回填）
        if delivery not in sheet3_orig:
            sheet3_orig[delivery] = {}
        if fa_val and str(fa_val).strip() and not sheet3_orig[delivery].get("发货日期"):
            sheet3_orig[delivery]["发货日期"] = fa_val
        if jr_val and str(jr_val).strip() and not sheet3_orig[delivery].get("交货日期"):
            sheet3_orig[delivery]["交货日期"] = jr_val
        if street_val and str(street_val).strip() and not sheet3_orig[delivery].get("街道"):
            sheet3_orig[delivery]["街道"] = street_val

        if delivery not in pivot_map:
            # 判断日期是 datetime 还是文本
            fa_is_dt = isinstance(fa_val, datetime.datetime)
            jr_is_dt = isinstance(jr_val, datetime.datetime)
            pivot_map[delivery] = {
                "交货": delivery,
                "销售凭证": row.get("销售凭证", ""),
                "运达方": row.get("运达方", ""),
                "运达方的名字": row.get("运达方的名字", ""),
                "送达方地点": row.get("送达方地点", ""),
                "工厂": row.get("工厂", ""),
                # Sheet4: 如果日期是文本(str) → 街道=None；如果是 datetime → 街道=原值
                "街道": street_val if (fa_is_dt or jr_is_dt) else None,
                "发货日期": fa_val if fa_is_dt else None,
                "交货日期": jr_val if jr_is_dt else None,
                "_交货量": 0.0,
                "_总重量": 0.0,
                "_业务量": 0.0,
                "_count": 0,
            }
        entry = pivot_map[delivery]
        entry["_交货量"] += _to_number(row.get("交货量")) or 0
        entry["_总重量"] += _to_number(row.get("总重量")) or 0
        entry["_业务量"] += _to_number(row.get("业务量")) or 0
        entry["_count"] += 1

    pivot_headers = [
        "交货", "销售凭证", "运达方", "运达方的名字",
        "送达方地点", "工厂", "街道", "发货日期", "交货日期",
        "求和项:交货量", "求和项:总重量", "求和项:业务量",
    ]
    result = []
    total_jhl = 0.0
    total_zzl = 0.0
    total_ywl = 0.0
    for entry in pivot_map.values():
        jhl = round(entry["_交货量"], 3) if entry["_交货量"] else 0
        zzl = round(entry["_总重量"], 3) if entry["_总重量"] else 0
        ywl = round(entry["_业务量"], 3) if entry["_业务量"] else 0
        total_jhl += jhl
        total_zzl += zzl
        total_ywl += ywl
        result.append([
            entry["交货"],
            entry["销售凭证"],
            entry["运达方"],
            entry["运达方的名字"],
            entry["送达方地点"],
            entry["工厂"],
            entry["街道"],
            entry["发货日期"],
            entry["交货日期"],
            jhl,
            zzl,
            ywl,
        ])
    # 添加 "(空白)" 行
    result.append(["(空白)", "(空白)", "(空白)", "(空白)", "(空白)", "(空白)", "(空白)", "(空白)", "(空白)", None, None, None])
    # 添加 "总计" 行
    result.append(["总计", None, None, None, None, None, None, None, None, round(total_jhl, 3), round(total_zzl, 3), round(total_ywl, 3)])
    return pivot_headers, result, sheet3_orig


def build_pivot_by_factory_delivery(all_rows: list) -> list:
    """Sheet2: 按工厂+交货号透视
    列: 工厂, 交货, 计数项:物料, 求和项:交货量, 求和项:总重量

    返回结构匹配标准答案的Excel透视表格式:
    - 前2行为空行
    - 第3行: 列C="值"
    - 第4行: 表头
    - 数据行: 工厂名仅在该组首行显示
    - 最后一行: 总计行
    """
    pivot_map = OrderedDict()
    for row in all_rows:
        factory = str(row.get("工厂", "")).strip()
        delivery = str(row.get("交货", "")).strip()
        if not delivery:
            continue
        key = (factory, delivery)
        if key not in pivot_map:
            pivot_map[key] = {
                "工厂": factory,
                "交货": delivery,
                "_交货量": 0.0,
                "_总重量": 0.0,
                "_material_count": 0,
            }
        entry = pivot_map[key]
        material = str(row.get("物料", "")).strip()
        if material:
            entry["_material_count"] += 1
        entry["_交货量"] += _to_number(row.get("交货量")) or 0
        entry["_总重量"] += _to_number(row.get("总重量")) or 0

    pivot_headers = ["工厂", "交货", "计数项:物料", "求和项:交货量", "求和项:总重量"]

    # 按工厂分组排序（工厂名排序，同工厂内按交货号排序）
    sorted_items = sorted(pivot_map.items(), key=lambda x: (x[0][0], x[0][1]))

    result = []
    prev_factory = None
    total_materials = 0
    total_jhl = 0.0
    total_zzl = 0.0
    for (factory, delivery), entry in sorted_items:
        factory_display = factory if factory != prev_factory else ""
        mat_count = entry["_material_count"]
        jhl = round(entry["_交货量"], 3) if entry["_交货量"] else 0
        zzl = round(entry["_总重量"], 3) if entry["_总重量"] else 0
        result.append([
            factory_display,
            delivery,
            mat_count,
            jhl,
            zzl,
        ])
        total_materials += mat_count
        total_jhl += jhl
        total_zzl += zzl
        prev_factory = factory

    # 添加总计行
    result.append([
        "总计",
        None,
        total_materials,
        round(total_jhl, 3) if total_jhl else 0,
        round(total_zzl, 3) if total_zzl else 0,
    ])

    # 构建完整输出: 2空行 + "值"行 + 表头 + 数据 + 总计
    # 透视表格式: 前2行空, 第3行列C="值", 第4行表头
    full_result = []
    # 行0: 空行
    full_result.append([None, None, None, None, None])
    # 行1: 空行
    full_result.append([None, None, None, None, None])
    # 行2: 列C="值" (模拟Excel透视表标记)
    full_result.append([None, None, "值", None, None])
    # 行3: 表头
    full_result.append(pivot_headers[:])
    # 行4+: 数据行 + 总计行
    full_result.extend(result)

    return pivot_headers, full_result


def _parse_sheet_rows(rows: list) -> Tuple[tuple, list]:
    """从行列表中提取表头和有效数据行（不含空行）"""
    if not rows:
        return None
    raw_headers = rows[0]
    last_non_none = -1
    for idx, h in enumerate(raw_headers):
        if h is not None:
            last_non_none = idx
    if last_non_none < 0:
        return None
    headers = tuple(raw_headers[: last_non_none + 1])
    data_rows = [tuple(r[: last_non_none + 1]) for r in rows[1:]]
    data_rows = [r for r in data_rows if any(c is not None and str(c).strip() != "" for c in r)]
    return headers, data_rows


def _detect_file_type(filepath: str) -> str:
    """通过 magic bytes 检测文件真实类型，而非仅依赖扩展名。
    返回: 'xlsx' | 'xls' | 'tsv' | 'csv' | 'unknown'
    """
    with open(filepath, "rb") as f:
        head = f.read(8)
    # ZIP magic (xlsx / real xls with macro)
    if head[:4] == b"PK\x03\x04":
        return "xlsx"
    # OLE2 compound document (real .xls binary)
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    # UTF-16 LE BOM
    if head[:2] == b"\xff\xfe":
        return "tsv"
    # UTF-8 BOM or plain text — treat as csv/tsv
    if head[:3] == b"\xef\xbb\xbf" or head[:1] != b"\x00":
        # try to distinguish csv vs tsv by counting tabs vs commas in first 4KB
        return "csv"  # will auto-detect delimiter later
    return "unknown"


def _read_text_table(filepath: str) -> Dict[str, Tuple[tuple, list]]:
    """读取 TSV/CSV 文本文件（可能是 UTF-16 或 UTF-8 编码），返回单 sheet 结果"""
    import csv
    import io

    # 自动检测编码
    with open(filepath, "rb") as f:
        raw = f.read()

    encoding = "utf-8"
    if raw[:2] == b"\xff\xfe":
        encoding = "utf-16-le"
    elif raw[:2] == b"\xfe\xff":
        encoding = "utf-16-be"
    elif raw[:3] == b"\xef\xbb\xbf":
        encoding = "utf-8-sig"

    text = raw.decode(encoding, errors="replace")
    # 去除可能残留的 BOM 字符
    if text and text[0] == "\ufeff":
        text = text[1:]
    # 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 自动检测分隔符：tab vs comma
    first_line = text.split("\n")[0] if text else ""
    if first_line.count("\t") >= first_line.count(","):
        delimiter = "\t"
    else:
        delimiter = ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader]
    result: Dict[str, Tuple[tuple, list]] = {}
    sheet_name = os.path.splitext(os.path.basename(filepath))[0]
    parsed = _parse_sheet_rows(rows)
    if parsed is not None:
        result[sheet_name] = parsed
    return result


def read_all_sheets(filepath: str) -> Dict[str, Tuple[tuple, list]]:
    result: Dict[str, Tuple[tuple, list]] = {}
    ext = os.path.splitext(filepath)[1].lower()
    ftype = _detect_file_type(filepath)

    if ftype == "xlsx":
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        for sname in wb.sheetnames:
            ws = wb[sname]
            rows = list(ws.iter_rows(values_only=True))
            parsed = _parse_sheet_rows(rows)
            if parsed is not None:
                result[sname] = parsed
        wb.close()
    elif ftype == "xls":
        wb = xlrd.open_workbook(filepath)
        for sname in wb.sheet_names():
            sheet = wb.sheet_by_name(sname)
            rows = [sheet.row_values(r) for r in range(sheet.nrows)]
            parsed = _parse_sheet_rows(rows)
            if parsed is not None:
                result[sname] = parsed
    elif ftype in ("tsv", "csv"):
        result = _read_text_table(filepath)
    else:
        # 最后兜底：尝试 openpyxl，失败则尝试文本方式
        try:
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            for sname in wb.sheetnames:
                ws = wb[sname]
                rows = list(ws.iter_rows(values_only=True))
                parsed = _parse_sheet_rows(rows)
                if parsed is not None:
                    result[sname] = parsed
            wb.close()
        except Exception:
            result = _read_text_table(filepath)
    return result


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
