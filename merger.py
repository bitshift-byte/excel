"""合并核心逻辑（从 app.py 抽出，供 Web 与邮件读取器共用）"""
import os
import sys
import json
import hashlib
import datetime
from collections import OrderedDict
from typing import List, Dict, Tuple, Optional

import openpyxl
import xlrd

PREVIEW_MAX_ROWS = 200
SAMPLE_ROWS = 10


def _base_dir() -> str:
    """可写数据目录：打包后写入固定的用户数据目录，开发时为项目目录"""
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            appdata = os.environ.get("APPDATA")
            base = os.path.join(appdata, "ExcelMerger") if appdata else os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(sys.executable)
        os.makedirs(base, exist_ok=True)
        return base
    return os.path.dirname(os.path.abspath(__file__))


def _resource_path(relative: str) -> str:
    """只读资源路径：PyInstaller 打包后在 sys._MEIPASS 临时目录，开发时为项目目录"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


RULES_FILE = os.path.join(_base_dir(), "rules.json")

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


# ===================== 行政区划数据 =====================

REGIONS_FILE = _resource_path("china_regions.json")


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


def merge_files(
    file_paths: List[str],
    selected_sheets: Optional[List[str]] = None,
    provinces: Optional[List[str]] = None,
    rule_id: Optional[str] = None,
    output_dir: str = "output",
    output_prefix: str = "合并结果",
    manual_mappings: Optional[Dict] = None,
    date_str: Optional[str] = None,
) -> Dict:
    """合并多个 Excel 文件为统一标准列，可选按省份筛选，输出 Excel。

    selected_sheets: sheet key 列表，格式 f"{文件名}::{sheet名}"；None 表示全选。
    provinces: 省份列表；None/[] 表示不筛选（全量）。
    rule_id: 规则 id；None 使用内置默认规则。
    manual_mappings: 手动列名映射 {sheet_key: {原始列名: 标准列名}}；None 表示仅自动匹配。
    返回 {output_path, stats, previews}。
    """
    os.makedirs(output_dir, exist_ok=True)
    prov_list = provinces or []

    files_data = {}
    for fp in file_paths:
        fname = os.path.basename(fp)
        files_data[fname] = read_all_sheets(fp)

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
        xm_val = str(aligned_row.get("项目", "")).strip()
        if not xm_val:
            continue
        dedup_key = (jh_val, xm_val)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        aligned.append(aligned_row)

    # 省份筛选
    if prov_list:
        filtered = [row for row in aligned if match_row_province(row, prov_list)]
    else:
        filtered = aligned

    street_key = None
    for col in all_columns:
        if "街道" in col and "街道2" not in col and "街道 3" not in col:
            street_key = col
            break

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

    day = date_str.replace("-", "") if date_str else datetime.datetime.now().strftime("%Y%m%d")
    short_hash = hashlib.md5(f"{day}_{len(filtered)}_{datetime.datetime.now().strftime('%H%M%S%f')}".encode()).hexdigest()[:8]
    prov_short = "_".join(p.replace("省", "").replace("市", "") for p in prov_list[:3]) if prov_list else "全部"
    output_filename = f"{output_prefix}_{prov_short}_{day}_{short_hash}.xlsx"
    output_path = os.path.join(output_dir, output_filename)
    wb.save(output_path)
    wb.close()

    stats = {
        "total_merged_rows": len(merged_rows),
        "total_columns": len(all_columns),
        "filtered_rows": len(filtered),
        "pivot_delivery_count": len(p4_data),
        "pivot_factory_count": len(p2_data),
        "street_column": street_key if street_key else "未找到",
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
