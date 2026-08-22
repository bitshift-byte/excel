"""合并核心逻辑（从 app.py 抽出，供 Web 与邮件读取器共用）"""
import os
import sys
import re
import json
import hashlib
import datetime
from datetime import timezone, timedelta
from collections import OrderedDict
from typing import List, Dict, Tuple, Optional

import openpyxl
import xlrd

PREVIEW_MAX_ROWS = 200
SAMPLE_ROWS = 10


def _base_dir() -> str:
    """可写数据目录：项目根目录"""
    return os.path.dirname(os.path.abspath(__file__))


def _resource_path(relative: str) -> str:
    """只读资源路径：项目根目录"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


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
                {"source_file_contains": "分销下单量", "source_value": "8136", "target_value": "701"},
                {"source_file_contains": "分销下单量", "source_value": "8137", "target_value": "701"},
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
       {"source_file_contains": "分销下单量", "source_value": "8136", "target_value": "701"}
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



# 中国时区 UTC+8
_CN_TZ = timezone(timedelta(hours=8))

def now_cn() -> datetime.datetime:
    """返回中国时区(UTC+8)的当前时间"""
    return datetime.datetime.now(_CN_TZ)

def fromtimestamp_cn(ts: float) -> datetime.datetime:
    """将时间戳转为中国时区(UTC+8)的 datetime"""
    return datetime.datetime.fromtimestamp(ts, tz=_CN_TZ)



def _excel_date(val):
    """将 datetime 值转为 date-only，避免 Excel 显示时分秒"""
    if isinstance(val, datetime.datetime):
        return datetime.date(val.year, val.month, val.day)
    return val


def serialize_cell(val):
    if val is None:
        return ""
    if isinstance(val, datetime.datetime):
        return val.strftime("%Y/%m/%d")
    if isinstance(val, datetime.date):
        return val.strftime("%Y/%m/%d")
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
        return val.strftime("%Y/%m/%d")
    if isinstance(val, datetime.date):
        return val.strftime("%Y/%m/%d")
    s = str(val).strip()
    # 尝试解析常见的日期格式
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.strftime("%Y/%m/%d")
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


def build_pivot_by_delivery(filtered_rows: list, logistics_map: Optional[Dict] = None, so_map: Optional[Dict] = None, kuacang_map: Optional[Dict] = None) -> Tuple[list, list, dict]:
    """Sheet4/Sheet5: 按交货号汇总透视表（从 Sheet3 筛选数据构建）
    列: 交货, 销售凭证, 运达方, 运达方的名字, 送达方地点, 工厂, 街道, 发货日期, 交货日期, 求和项:交货量, 求和项:总重量, 求和项:业务量, B_ADDRESS1, 备注, 1, 2

    Sheet4 规则（模拟 Excel 透视表行为）：
    - 数值列：SUM 求和
    - 日期为 datetime → Sheet4 保持 datetime，街道保持原值
    - 日期为文本格式(str) → Sheet4 中日期=None，街道=None（Excel 透视表丢弃文本日期行字段）
    - B_ADDRESS1/备注：先查 logistics_map（已发运/未发运，key=销售凭证），未命中的再查 so_map（SO文件，key=交货号），再未命中查 kuacang_map（跨仓订单，key=交货号）
    - 列1/列2（O/P 子合计）：该交货下"奥妙+洗衣粉/皂粉"类别的总重量/业务量子合计

    Sheet5 规则：Sheet4 的副本，但 None 的日期/街道用 Sheet3 原始文本值回填
    """
    pivot_map = OrderedDict()
    # 保存 Sheet3 中的原始文本值（用于 Sheet5 回填）
    sheet3_orig = {}  # delivery -> {"发货日期": orig_val, "交货日期": orig_val, "街道": orig_val}
    # 计算"奥妙+洗衣粉/皂粉"子合计（用于 Sheet4 的 O/P 列和 Sheet5）
    omo_subtotals = {}  # delivery -> {"zzl": 0.0, "ywl": 0.0}

    for row in filtered_rows:
        delivery = str(row.get("交货", "")).strip()
        if not delivery:
            continue
        fa_val = row.get("发货日期", "")
        jr_val = row.get("交货日期", "")
        # 过滤掉日期为空的行（与标准答案对齐，避免无日期的交货号进入汇总）
        if not fa_val or not str(fa_val).strip():
            continue
        if not jr_val or not str(jr_val).strip():
            continue
        street_val = row.get("街道", "")

        # 检查是否为"奥妙+洗衣粉/皂粉"类别
        desc = str(row.get("描述", ""))
        is_omo = "奥妙" in desc and ("洗衣粉" in desc or "皂粉" in desc)
        if is_omo:
            if delivery not in omo_subtotals:
                omo_subtotals[delivery] = {"zzl": 0.0, "ywl": 0.0}
            zzl_v = _to_number(row.get("总重量"))
            ywl_v = _to_number(row.get("业务量"))
            if zzl_v:
                omo_subtotals[delivery]["zzl"] += zzl_v
            if ywl_v:
                omo_subtotals[delivery]["ywl"] += ywl_v

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
                # 街道始终保留原值（与标准答案行为一致）
                "街道": street_val,
                "发货日期": datetime.date(fa_val.year, fa_val.month, fa_val.day) if fa_is_dt else None,
                "交货日期": datetime.date(jr_val.year, jr_val.month, jr_val.day) if jr_is_dt else None,
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
        "发货日期", "交货日期", "送达方地点", "运达方", "销售凭证",
        "交货", "运达方的名字", "街道",
        "求和项:交货量", "求和项:总重量", "求和项:业务量", "工厂",
        "B_ADDRESS1", "备注", "1", "2",
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
        # 通过 logistics_map LEFT JOIN 取 B_ADDRESS1/备注
        addr1 = ""
        remark = ""
        if logistics_map:
            xp = str(entry["销售凭证"]).strip() if entry["销售凭证"] else ""
            logi = logistics_map.get(xp)
            if logi:
                addr1 = logi.get("B_ADDRESS1", "") or ""
                remark = logi.get("备注", "") or ""
        # 2. 如果 logistics_map 未命中，用交货号查 SO map
        # SO 文件的"客户订单号"字段值 == 本表的"交货"号
        if so_map:
            delivery_no = str(entry["交货"]).strip() if entry["交货"] else ""
            so_data = so_map.get(delivery_no)
            if so_data:
                if not addr1:
                    addr1 = so_data.get("B_ADDRESS1", "") or ""
                if not remark:
                    remark = so_data.get("备注", "") or ""
        # 3. 如果仍未命中，用交货号查 跨仓订单 map（kuacang_map）
        if kuacang_map:
            delivery_no = str(entry["交货"]).strip() if entry["交货"] else ""
            kc_data = kuacang_map.get(delivery_no)
            if kc_data:
                if not addr1:
                    addr1 = kc_data.get("B_ADDRESS1", "") or ""
                if not remark:
                    remark = kc_data.get("备注", "") or ""
        # O/P 子合计：奥妙+洗衣粉/皂粉的总重量/业务量
        omo = omo_subtotals.get(entry["交货"])
        o_val = round(omo["zzl"], 3) if omo else None
        p_val = round(omo["ywl"], 3) if omo else None
        result.append([
            entry["发货日期"],
            entry["交货日期"],
            entry["送达方地点"],
            entry["运达方"],
            entry["销售凭证"],
            entry["交货"],
            entry["运达方的名字"],
            entry["街道"],
            jhl,
            zzl,
            ywl,
            entry["工厂"],
            addr1,
            remark,
            o_val,
            p_val,
        ])
    # 添加 "总计" 行
    result.append(["总计", None, None, None, None, None, None, None, round(total_jhl, 3), round(total_zzl, 3), round(total_ywl, 3), None, None, None, None, None])
    return pivot_headers, result, sheet3_orig



def build_data_pivot(p4_headers: list, p4_data: list) -> Tuple[list, list]:
    """构建"数据透析" sheet 数据。

    数据透析是交货汇总的重排+精简版本：
    - 12列（丢弃 B_ADDRESS1, 备注, 1, 2）
    - 列顺序: 交货, 销售凭证, 运达方, 运达方的名字, 送达方地点, 工厂, 街道,
              发货日期, 交货日期, 求和项:交货量, 求和项:总重量, 求和项:业务量
    - 按交货号升序排列
    - 数据行后追加 (空白) 行和 总计 行

    Args:
        p4_headers: 交货汇总的 16 列表头
        p4_data: 交货汇总的数据行列表（最后一行为 总计 行）

    Returns:
        (dp_headers, dp_data): 数据透析的 12 列表头和数据行
    """
    # 交货汇总 16-col → 数据透析 12-col 的列映射
    # 交货汇总 index: 交货[5], 销售凭证[4], 运达方[3], 运达方的名字[6],
    #                 送达方地点[2], 工厂[11], 街道[7], 发货日期[0], 交货日期[1],
    #                 求和项:交货量[8], 求和项:总重量[9], 求和项:业务量[10]
    COL_MAP = [5, 4, 3, 6, 2, 11, 7, 0, 1, 8, 9, 10]

    dp_headers = [
        "交货", "销售凭证", "运达方", "运达方的名字", "送达方地点",
        "工厂", "街道", "发货日期", "交货日期",
        "求和项:交货量", "求和项:总重量", "求和项:业务量",
    ]

    # 分离数据行和总计行
    data_rows = []
    total_row = None
    for row in p4_data:
        if row and str(row[0]).strip() == "总计":
            total_row = row
        else:
            # 重排列并截取 12 列
            new_row = [row[src_idx] if src_idx < len(row) else None for src_idx in COL_MAP]
            data_rows.append(new_row)

    # 按交货号（index 0）升序排序
    data_rows.sort(key=lambda r: str(r[0]) if r[0] is not None else "")

    # 从总计行提取合计值（交货汇总 index 8/9/10）
    if total_row:
        total_jhl = total_row[8] if len(total_row) > 8 and total_row[8] is not None else 0
        total_zzl = total_row[9] if len(total_row) > 9 and total_row[9] is not None else 0
        total_ywl = total_row[10] if len(total_row) > 10 and total_row[10] is not None else 0
    else:
        total_jhl = 0
        total_zzl = 0
        total_ywl = 0

    # 追加 (空白) 行
    data_rows.append(["(空白)"] * 9 + [None, None, None])

    # 追加 总计 行
    data_rows.append(["总计", None, None, None, None, None, None, None, None,
                      total_jhl, total_zzl, total_ywl])

    return dp_headers, data_rows

def read_logistics_map(files_data: Dict) -> Dict[str, Dict]:
    """从已发运/未发运 sheet 构建 销售凭证 → {B_ADDRESS1, 备注} 映射。
    
    遍历所有输入文件中名为"已发运"或"未发运"的 sheet，
    按"销售凭证"列去重（LEFT JOIN 语义：已发运优先）。
    """
    logistics_map = {}
    for fname, sheets in files_data.items():
        for sname, (headers, data_rows) in sheets.items():
            if sname not in ("已发运", "未发运"):
                continue
            h_map = {}
            for i, h in enumerate(headers):
                h_map[str(h).strip() if h else ""] = i
            ci_xp = h_map.get("销售凭证")
            ci_addr = h_map.get("B_ADDRESS1")
            ci_remark = h_map.get("备注")
            if ci_xp is None:
                continue
            is_sent = (sname == "已发运")
            for row in data_rows:
                xp = str(row[ci_xp]).strip() if ci_xp < len(row) and row[ci_xp] is not None else ""
                if not xp:
                    continue
                # 已发运优先：如果已存在则不覆盖
                if xp in logistics_map and logistics_map[xp].get("_from_sent"):
                    continue
                addr = row[ci_addr] if ci_addr is not None and ci_addr < len(row) else None
                remark = row[ci_remark] if ci_remark is not None and ci_remark < len(row) else None
                logistics_map[xp] = {
                    "B_ADDRESS1": addr if addr is not None else "",
                    "备注": remark if remark is not None else "",
                    "_from_sent": is_sent,
                }
    return logistics_map


def read_so_map(files_data: Dict) -> Dict[str, Dict]:
    """从 SO 文件构建 客户订单号(=交货号) → {B_ADDRESS1, 备注} 映射。

    SO 文件特征：
    - sheet 名为 Sheet1/Sheet2 等（非"已发运"/"未发运"）
    - 表头同时含"客户订单号"、"NOTES2"、"B_ADDRESS1"
    - JOIN key: "客户订单号"（值 == 产出物的"交货"号）
    - NOTES2 → 备注, B_ADDRESS1 → B_ADDRESS1
    """
    so_map = {}
    for fname, sheets in files_data.items():
        for sname, (headers, data_rows) in sheets.items():
            h_map = {}
            for i, h in enumerate(headers):
                h_map[str(h).strip() if h else ""] = i
            ci_order = h_map.get("客户订单号")
            # NOTES2 / NOTE2, B_ADDRESS1 / 地址 是同义列名变体（SO vs OMR）
            ci_notes = h_map.get("NOTES2", h_map.get("NOTE2"))
            ci_addr = h_map.get("B_ADDRESS1", h_map.get("地址"))
            # 必须同时含三列才认定为 SO 文件
            if ci_order is None or ci_notes is None or ci_addr is None:
                continue
            for row in data_rows:
                order_no = str(row[ci_order]).strip() if ci_order < len(row) and row[ci_order] is not None else ""
                if not order_no:
                    continue
                # 有值优先：已存在且有 B_ADDRESS1 值则不覆盖
                if order_no in so_map and so_map[order_no].get("B_ADDRESS1"):
                    continue
                notes_val = row[ci_notes] if ci_notes < len(row) else None
                addr_val = row[ci_addr] if ci_addr < len(row) else None
                so_map[order_no] = {
                    "B_ADDRESS1": addr_val if addr_val is not None else "",
                    "备注": notes_val if notes_val is not None else "",
                }
    return so_map


def read_kuacang_map(files_data: Dict) -> Dict[str, Dict]:
    """从跨仓订单文件构建 OBD(=交货号) → {B_ADDRESS1, 备注} 映射。

    跨仓订单文件特征：
    - sheet 名为 "跨仓结果仓库回传"（允许前后空白）
    - 表头含 "OBD"、"客户订单号"、"备注"、"仓库备注"
    - OBD 值 == 产出物的"交货"号
    - 客户订单号 + 工单号 → B_ADDRESS1（拼接，跳过空值）
    - 备注 + 仓库备注 + 填写人 → 备注（拼接，跳过空值）

    优先级：已存在且有 B_ADDRESS1 值的条目不被覆盖 B_ADDRESS1；
    已存在且有备注的条目不被覆盖备注；空字段可被后续行补全。
    """
    kuacang_map: Dict[str, Dict] = {}
    for fname, sheets in files_data.items():
        for sname, (headers, data_rows) in sheets.items():
            # 允许 sheet 名前后有空白
            if sname.strip() != "跨仓结果仓库回传":
                continue
            h_map = {}
            for i, h in enumerate(headers):
                key = str(h).strip() if h else ""
                # 保留第一次出现的列索引（"OBD" 在跨仓订单中出现两次，取第一个）
                if key not in h_map:
                    h_map[key] = i
            # 需要同时有 OBD 和 客户订单号 才认定为跨仓订单 sheet
            ci_obd = h_map.get("OBD")
            ci_cust = h_map.get("客户订单号")
            if ci_obd is None or ci_cust is None:
                continue
            ci_remark = h_map.get("备注")
            ci_wh_remark = h_map.get("仓库备注")
            ci_gdh = h_map.get("工单号")
            ci_txr = h_map.get("填写人")

            for row in data_rows:
                obd_raw = row[ci_obd] if ci_obd < len(row) and row[ci_obd] is not None else ""
                # 规范化 OBD：float → int 字符串（xlrd 读取 .xls 时数字为 float）
                if isinstance(obd_raw, float) and obd_raw.is_integer():
                    obd = str(int(obd_raw))
                else:
                    obd = str(obd_raw).strip() if obd_raw else ""
                # 跳过空/None/0 的 OBD
                if not obd or obd == "0":
                    continue
                cust_po = str(row[ci_cust]).strip() if ci_cust < len(row) and row[ci_cust] is not None else ""
                # B_ADDRESS1 = 客户订单号 + 工单号（跳过空值）
                addr_parts = []
                if cust_po:
                    addr_parts.append(cust_po)
                if ci_gdh is not None and ci_gdh < len(row):
                    v = row[ci_gdh]
                    if v is not None and str(v).strip():
                        addr_parts.append(str(v).strip())
                addr1 = " | ".join(addr_parts) if addr_parts else ""
                # 备注 = 备注 + 仓库备注 + 填写人（跳过空值）
                parts = []
                if ci_remark is not None and ci_remark < len(row):
                    v = row[ci_remark]
                    if v is not None and str(v).strip():
                        parts.append(str(v).strip())
                if ci_wh_remark is not None and ci_wh_remark < len(row):
                    v = row[ci_wh_remark]
                    if v is not None and str(v).strip():
                        parts.append(str(v).strip())
                if ci_txr is not None and ci_txr < len(row):
                    v = row[ci_txr]
                    if v is not None and str(v).strip():
                        parts.append(str(v).strip())
                remark = " | ".join(parts) if parts else ""
                # 客户订单号和备注都为空，跳过此行（无有用数据）
                if not addr1 and not remark:
                    continue
                # 已存在的条目：补全空字段，不覆盖已有值
                if obd in kuacang_map:
                    existing = kuacang_map[obd]
                    if not existing.get("B_ADDRESS1") and addr1:
                        existing["B_ADDRESS1"] = addr1
                    if not existing.get("备注") and remark:
                        existing["备注"] = remark
                else:
                    kuacang_map[obd] = {
                        "B_ADDRESS1": addr1,
                        "备注": remark,
                    }
    return kuacang_map



def build_omo_detail(filtered_rows: list, std_headers: list) -> Tuple[list, list]:
    """生成"奥妙+洗衣粉/皂粉"明细子集和小计表。
    
    返回 (omo_detail_rows, omo_subtotal_rows):
    - omo_detail_rows: 筛选出的明细行（同标准列，去掉空列），用于"奥妙明细"sheet
    - omo_subtotal_rows: 按交货号汇总的 (交货, 求和项:总重量, 求和项:业务量)，用于"奥妙小计"sheet
    """
    detail_rows = []
    subtotal_map = OrderedDict()
    
    for row in filtered_rows:
        desc = str(row.get("描述", ""))
        if "奥妙" not in desc or ("洗衣粉" not in desc and "皂粉" not in desc):
            continue
        delivery = str(row.get("交货", "")).strip()
        if not delivery:
            continue
        # 明细行
        detail_rows.append([row.get(h, "") for h in std_headers])
        # 小计
        if delivery not in subtotal_map:
            subtotal_map[delivery] = {"zzl": 0.0, "ywl": 0.0}
        zzl_v = _to_number(row.get("总重量"))
        ywl_v = _to_number(row.get("业务量"))
        if zzl_v:
            subtotal_map[delivery]["zzl"] += zzl_v
        if ywl_v:
            subtotal_map[delivery]["ywl"] += ywl_v
    
    subtotal_rows = []
    for delivery, sub in subtotal_map.items():
        subtotal_rows.append([
            delivery,
            round(sub["zzl"], 3) if sub["zzl"] else 0,
            round(sub["ywl"], 3) if sub["ywl"] else 0,
        ])
    
    return detail_rows, subtotal_rows


def build_pivot_by_factory_delivery(all_rows: list) -> Tuple[list, list]:
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


def _normalize_cell(value):
    """规范化单元格值：将整数浮点数转为整数（xlrd 读取 .xls 时数字均为 float），
    将文本格式日期（如 "2026.08.18"）解析为 datetime 对象。"""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    # 尝试解析文本格式日期：YYYY.MM.DD 或 YYYY-MM.DD 等
    if isinstance(value, str):
        s = value.strip()
        if s and re.match(r'^\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}$', s):
            for sep in ('.', '-', '/'):
                parts = s.split(sep)
                if len(parts) == 3:
                    try:
                        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                        return datetime.datetime(y, m, d)
                    except (ValueError, IndexError):
                        pass
    return value


def _parse_sheet_rows(rows: list) -> Tuple[tuple, list]:
    """从行列表中提取表头和有效数据行（不含空行）。

    自动跳过开头的标题行 / 空行：扫描前 10 行，选择非空单元格最多的一行作为表头。
    真正的表头行通常有大量非空列，而标题行只有 1-3 个非空单元格。
    """
    if not rows:
        return None

    def _non_empty_count(row):
        return sum(1 for c in row if c is not None and str(c).strip() != "")

    # 扫描前 10 行，选择非空单元格最多的一行作为表头
    max_scan = min(len(rows), 10)
    header_idx = 0
    best_count = 0
    for i in range(max_scan):
        cnt = _non_empty_count(rows[i])
        if cnt > best_count:
            best_count = cnt
            header_idx = i

    raw_headers = rows[header_idx]
    # 找到第一个和最后一个非空列，剥离前导/尾部空列
    first_non_empty = None
    last_non_empty = -1
    for idx, h in enumerate(raw_headers):
        if h is not None and str(h).strip() != "":
            if first_non_empty is None:
                first_non_empty = idx
            last_non_empty = idx
    if first_non_empty is None or last_non_empty < 0:
        return None
    headers = tuple(_normalize_cell(h) for h in raw_headers[first_non_empty : last_non_empty + 1])
    data_rows = [
        tuple(_normalize_cell(c) for c in r[first_non_empty : last_non_empty + 1])
        for r in rows[header_idx + 1 :]
    ]
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
        datemode = wb.datemode
        for sname in wb.sheet_names():
            sheet = wb.sheet_by_name(sname)
            rows = []
            for r in range(sheet.nrows):
                row = []
                for c in range(sheet.ncols):
                    ctype = sheet.cell_type(r, c)
                    val = sheet.cell_value(r, c)
                    if ctype == xlrd.XL_CELL_DATE:
                        try:
                            val = xlrd.xldate_as_datetime(val, datemode)
                        except Exception:
                            pass
                    row.append(val)
                rows.append(row)
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



# 结果产物 sheet 名称集合 — 这些 sheet 是合并输出，不参与二次合并
RESULT_SHEET_NAMES = {
    "全量数据", "交货汇总", "交货汇总_文本日期",
    "数据透析", "工厂交货透视", "奥妙明细", "奥妙小计",
}


def select_source_sheets(sheets_map: Dict[str, Dict]) -> list:
    """从 sheets_map 中自动选择应参与合并的数据源 sheet。

    选择规则：
    1. 排除结果产物 sheet（RESULT_SHEET_NAMES）
    2. 选中明细型 sheet（表头含"交货"列且行数 > 100）
    3. 选中已发运/未发运 sheet（sheet名含"发运"）
    4. 如果以上都没命中，回退选非结果产物且行数 > 50 的 sheet
    5. 如果仍无选中，抛出 ValueError

    Args:
        sheets_map: {sheet_key: {filename, sheet_name, headers, row_count}}

    Returns:
        选中的 sheet key 列表
    """
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
        # 回退：选非结果产物且行数 > 50 的 sheet
        for key, info in sheets_map.items():
            if info["sheet_name"] in RESULT_SHEET_NAMES:
                continue
            if info["row_count"] > 50:
                selected_keys.append(key)

    if not selected_keys:
        raise ValueError(
            "未找到可合并的数据 sheet（需要总表含「明细」「已发运」「未发运」）"
        )

    return selected_keys


def merge_files(
    file_paths: List[str],
    selected_sheets: Optional[List[str]] = None,
    provinces: Optional[List[str]] = None,
    rule_id: Optional[str] = None,
    output_dir: str = "output",
    output_prefix: str = "合并结果",
    manual_mappings: Optional[Dict] = None,
    date_str: Optional[str] = None,
    delivery_range: Optional[Tuple[int, int]] = None,
) -> Dict:
    """合并多个 Excel 文件为统一标准列，可选按省份/交货号区间筛选，输出 Excel。

    selected_sheets: sheet key 列表，格式 f"{文件名}::{sheet名}"；None 表示全选。
    provinces: 省份列表；None/[] 表示不筛选（全量）。
    rule_id: 规则 id；None 使用内置默认规则。
    manual_mappings: 手动列名映射 {sheet_key: {原始列名: 标准列名}}；None 表示仅自动匹配。
    delivery_range: 可选，交货号区间 (min, max)，如 (2424796922, 2424802864)。
    返回 {output_path, stats, previews}。
    """
    os.makedirs(output_dir, exist_ok=True)
    prov_list = provinces or []

    # 排除不参与合并的文件：下单计划（数据重复，工厂值未映射）
    EXCLUDE_KEYWORDS = ["下单计划"]
    filtered_paths = [
        fp for fp in file_paths
        if not any(kw in os.path.basename(fp) for kw in EXCLUDE_KEYWORDS)
    ]

    # 按文件优先级排序：06o/分销报表/分销下单量/跑单明细 优先
    def _file_priority(fp):
        fn = os.path.basename(fp).lower()
        if "06o" in fn:
            return 0
        if "分销报表" in fn:
            return 1
        if "分销下单量" in fn or "分销-下单量" in fn:
            return 2
        if "跑单明细" in fn:
            return 3
        return 5

    sorted_paths = sorted(filtered_paths, key=_file_priority)
    files_data = {}
    for fp in sorted_paths:
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

    # selected_sheets 为 None 时，按表头与规则标准表头的匹配率自动筛选 sheet
    # 只选匹配率 >= 60% 的 sheet，排除无关 sheet（如 OMR 导出、预报量等）
    SHEET_MATCH_THRESHOLD = 0.75
    if selected_sheets is None:
        selected_set = set()
        std_header_count = len(std_header_order)
        for fname, sheets in files_data.items():
            for sname, (headers, data_rows) in sheets.items():
                if not headers or not data_rows:
                    continue
                auto_map = match_columns_to_rule(list(headers), active_rule)
                matched_count = sum(1 for m in auto_map if m and m[1])
                match_ratio = matched_count / std_header_count if std_header_count else 0
                if match_ratio >= SHEET_MATCH_THRESHOLD:
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
                # 分销报表特殊处理：如果有「提货仓库」列，用提货仓库值覆盖工厂值
                # （提货仓库=YG → 工厂=YG，而非 8136→901 的默认映射）
                if "分销报表" in fname:
                    _thck_idx = None
                    for _i, _h in enumerate(headers):
                        if str(_h).strip() == "提货仓库":
                            _thck_idx = _i
                            break
                    if _thck_idx is not None and _thck_idx < len(row):
                        _thck_val = row[_thck_idx]
                        if _thck_val is not None and str(_thck_val).strip():
                            row_dict["工厂"] = str(_thck_val).strip()
                # 单位转换：统一总重量为吨、业务量为M3
                _wun = str(row_dict.get("WUn", "")).strip()
                if _wun == "公斤":
                    _zw = row_dict.get("总重量")
                    if isinstance(_zw, (int, float)) and _zw:
                        row_dict["总重量"] = _zw / 1000
                    row_dict["WUn"] = "吨"
                _vun = str(row_dict.get("VUn", "")).strip()
                if _vun == "CCM":
                    _yw = row_dict.get("业务量")
                    if isinstance(_yw, (int, float)) and _yw:
                        row_dict["业务量"] = _yw / 1000000
                    row_dict["VUn"] = "M3"
                row_dict["_source_file"] = f"{fname}::{sname}"
                merged_rows.append(row_dict)

    # 对齐 + 去重 + 过滤非法交货号
    aligned = []
    seen_keys = {}  # dedup_key → index in aligned (dict, for field completion)
    for row in merged_rows:
        aligned_row = {col: (row.get(col) if row.get(col) is not None else "") for col in all_columns}
        aligned_row["_source_file"] = row.get("_source_file", "")
        jh_val = str(aligned_row.get("交货", "")).strip()
        if jh_val and not jh_val.isdigit():
            continue
        if not jh_val:
            continue
        xm_val = str(aligned_row.get("项目", "")).strip()
        # 标准化项目号：去掉前导零，使 "000010" 和 "10" 被识别为同一项目
        # 避免不同来源文件（分销报表 vs 跨仓订单）的重复行被重复计算
        if xm_val and xm_val.isdigit():
            xm_normalized = str(int(xm_val))
        else:
            xm_normalized = xm_val
        # 项目号为空时用交货号作为去重键（保留项目号缺失的行）
        dedup_key = (jh_val, xm_normalized) if xm_normalized else (jh_val, "")
        if dedup_key in seen_keys:
            # 去重时做字段补全：用当前行的非空值补到已有行的空字段上
            # 解决不同数据源（如邮件产物 vs 总表）字段完整度不同的问题
            existing = aligned[seen_keys[dedup_key]]
            for col in all_columns:
                if col == "_source_file":
                    continue
                existing_val = existing.get(col, "")
                new_val = aligned_row.get(col, "")
                if (not existing_val or existing_val == "") and new_val:
                    existing[col] = new_val
            continue
        seen_keys[dedup_key] = len(aligned)
        aligned.append(aligned_row)

    # 省份筛选
    if prov_list:
        filtered = [row for row in aligned if match_row_province(row, prov_list)]
    else:
        filtered = aligned

    # 交货号区间筛选（可选，如只取 08-17 批次）
    if delivery_range:
        jhd_min, jhd_max = delivery_range
        def _in_range(row):
            jhd = row.get("交货", "")
            if jhd is None or str(jhd).strip() == "":
                return False
            try:
                v = int(str(jhd).strip())
                return jhd_min <= v <= jhd_max
            except (ValueError, TypeError):
                return False
        filtered = [row for row in filtered if _in_range(row)]

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
        ws1.append([_excel_date(row.get(h, "")) for h in all_columns])

    ws3 = wb.create_sheet("筛选数据")
    ws3.append(output_headers)
    for row in filtered:
        ws3.append([_excel_date(row.get(h, "")) for h in all_columns])

    # 读取物流信息（已发运/未发运的 B_ADDRESS1/备注，通过销售凭证关联）
    logistics_map = read_logistics_map(files_data)
    # 读取 SO 文件的 NOTES2(→备注)/B_ADDRESS1，通过交货号(=客户订单号)关联
    so_map = read_so_map(files_data)
    # 读取跨仓订单文件的 客户订单号(→B_ADDRESS1)/备注/仓库备注，通过交货号(=OBD)关联
    kuacang_map = read_kuacang_map(files_data)

    p4_headers, p4_data, text_dates = build_pivot_by_delivery(filtered, logistics_map, so_map, kuacang_map)
    ws4 = wb.create_sheet("交货汇总")
    ws4.append(p4_headers)
    for row in p4_data:
        ws4.append(row)

    # 数据透析 sheet（交货汇总的重排+精简版本，按交货号排序）
    dp_headers, dp_data = build_data_pivot(p4_headers, p4_data)
    ws_dp = wb.create_sheet("数据透析")
    ws_dp.append([None] * 12)  # 空行1
    ws_dp.append([None] * 12)  # 空行2
    ws_dp.append(dp_headers)   # 表头
    for row in dp_data:
        ws_dp.append(row)

    p5_headers = list(p4_headers)
    ws5 = wb.create_sheet("交货汇总_文本日期")
    ws5.append(p5_headers)
    for row in p4_data:
        new_row = list(row)
        # 交货 在 index 5
        delivery = str(new_row[5]).strip() if len(new_row) > 5 and new_row[5] else ""
        if delivery == "总计":
            pass  # 总计行保持原样
        else:
            orig = text_dates.get(delivery, {})
            # 发货日期 在 index 0
            if len(new_row) > 0 and new_row[0] is None and orig.get("发货日期"):
                new_row[0] = _format_date_text(orig["发货日期"])
            # 交货日期 在 index 1
            if len(new_row) > 1 and new_row[1] is None and orig.get("交货日期"):
                new_row[1] = _format_date_text(orig["交货日期"])
            # 街道 在 index 7
            if len(new_row) > 7 and new_row[7] is None and orig.get("街道"):
                new_row[7] = orig["街道"]
        ws5.append(new_row)

    p2_headers, p2_data = build_pivot_by_factory_delivery(aligned)
    ws2 = wb.create_sheet("工厂交货透视")
    for row in p2_data:
        ws2.append(row)

    # 生成"奥妙+洗衣粉/皂粉"明细子集和小计表
    omo_detail_rows, omo_subtotal_rows = build_omo_detail(filtered, all_columns)
    if omo_detail_rows:
        ws_omo_detail = wb.create_sheet("奥妙明细")
        ws_omo_detail.append(output_headers)
        for row in omo_detail_rows:
            ws_omo_detail.append([_excel_date(v) for v in row])

        ws_omo_subtotal = wb.create_sheet("奥妙小计")
        ws_omo_subtotal.append(["", "", ""])  # 前2行空
        ws_omo_subtotal.append(["", "", ""])
        ws_omo_subtotal.append(["交货", "求和项:总重量", "求和项:业务量"])
        for row in omo_subtotal_rows:
            ws_omo_subtotal.append(row)

    day = date_str.replace("-", "") if date_str else now_cn().strftime("%Y%m%d")
    short_hash = hashlib.md5(f"{day}_{len(filtered)}_{now_cn().strftime('%H%M%S%f')}".encode()).hexdigest()[:8]
    prov_short = "_".join(p.replace("省", "").replace("市", "") for p in prov_list[:3]) if prov_list else "全部"
    output_filename = f"{output_prefix}_{prov_short}_{day}_{short_hash}.xlsx"
    output_path = os.path.join(output_dir, output_filename)

    # 统一设置所有 sheet 中日期单元格的显示格式为斜杠 yyyy/m/d
    _DATE_FMT = "yyyy/m/d"
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, (datetime.datetime, datetime.date)):
                    cell.number_format = _DATE_FMT
    wb.save(output_path)
    wb.close()

    stats = {
        "total_merged_rows": len(merged_rows),
        "total_columns": len(all_columns),
        "filtered_rows": len(filtered),
        "pivot_delivery_count": len(p4_data),
        "pivot_factory_count": len(p2_data),
        "omo_detail_count": len(omo_detail_rows),
        "omo_subtotal_count": len(omo_subtotal_rows),
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
