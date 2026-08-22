"""
TDD tests for select_source_sheets — auto-selects data-source sheets for mail merge.

The function takes a sheets_map (from read_all_sheets across all files) and returns
the list of selected sheet keys that should participate in the merge pipeline.

Rules:
  - Exclude result-product sheets: 全量数据, 交货汇总, 交货汇总_文本日期,
    工厂交货透视, 奥妙明细, 奥妙小计, 数据透析
  - Select "明细"-type sheets (header contains "交货" column, > 100 rows)
  - Select "已发运"/"未发运" sheets (name contains "发运")
  - Fallback: if nothing matched, select any non-result sheet with > 50 rows
  - Raise ValueError if no sheets can be selected
"""
import pytest
from merger import select_source_sheets


def _sheet_info(filename, sheet_name, headers, row_count):
    """Helper to build a sheets_map entry."""
    key = f"{filename}::{sheet_name}"
    return key, {
        "filename": filename,
        "sheet_name": sheet_name,
        "headers": headers,
        "row_count": row_count,
    }


# Standard 明细 headers (34 cols, contains "交货")
MINGXI_HEADERS = [
    "交货", "DlvTy", "项目", "物料", "描述", "存储位置", "销售凭证",
    "运达方", "运达方的名字", "送达方地点", "名称 3", "工厂", "路线",
    "OPS", "WhN", "批次", "仓位", "GM", "销售组织", "售达方", "售达方",
    "街道", "街道2", "街道 3", "交货量", "SU", "数量(库存单位)", "计",
    "总重量", "WUn", "业务量", "VUn", "交货日期", "发货日期",
]

# 已发运/未发运 headers (contains "销售凭证")
FAYUN_HEADERS = [
    "下单日期", "需求日期", "到货城市", "客户代码", "销售凭证", "订单号",
    "提货状态", "拼车", "装车顺序", "客户名称", "客户地址", "数量", "吨位",
    "体积", "库区", "平台/直送", "粉吨位", "粉体积", "司机", "车型",
    "B_ADDRESS1", "备注",
]

# 交货汇总 headers (16 cols)
JIAOHUO_HUIZONG_HEADERS = [
    "发货日期", "交货日期", "送达方地点", "运达方", "销售凭证",
    "交货", "运达方的名字", "街道",
    "求和项:交货量", "求和项:总重量", "求和项:业务量", "工厂",
    "B_ADDRESS1", "备注", "1", "2",
]

# 数据透析 headers (12 cols)
SHUJU_TOUXI_HEADERS = [
    "交货", "销售凭证", "运达方", "运达方的名字", "送达方地点",
    "工厂", "街道", "发货日期", "交货日期",
    "求和项:交货量", "求和项:总重量", "求和项:业务量",
]

# 全量数据 headers (same as 明细)
QUANLIANG_HEADERS = list(MINGXI_HEADERS)


# =====================================================================
# RED 1: 明细 sheet is selected (has "交货" column, > 100 rows)
# =====================================================================

def test_select_source_sheets_mingxi_selected():
    """明细 sheet with 交货 column and > 100 rows should be selected."""
    k, v = _sheet_info("总表.xlsx", "明细", MINGXI_HEADERS, 500)
    sheets_map = {k: v}

    selected = select_source_sheets(sheets_map)

    assert k in selected


# =====================================================================
# RED 2: 已发运/未发运 sheets are selected
# =====================================================================

def test_select_source_sheets_fayun_selected():
    """已发运 and 未发运 sheets should be selected regardless of row count."""
    k1, v1 = _sheet_info("总表.xlsx", "已发运", FAYUN_HEADERS, 30)
    k2, v2 = _sheet_info("总表.xlsx", "未发运", FAYUN_HEADERS, 10)
    sheets_map = {k1: v1, k2: v2}

    selected = select_source_sheets(sheets_map)

    assert k1 in selected
    assert k2 in selected


# =====================================================================
# RED 3: Result-product sheets are excluded — 全量数据, 交货汇总, etc.
# =====================================================================

def test_select_source_sheets_excludes_result_products():
    """Result-product sheets should NOT be selected. When only result sheets exist,
    the function should raise ValueError."""
    result_sheets = [
        ("邮件合并.xlsx", "全量数据", QUANLIANG_HEADERS, 7000),
        ("邮件合并.xlsx", "交货汇总", JIAOHUO_HUIZONG_HEADERS, 62),
        ("邮件合并.xlsx", "交货汇总_文本日期", JIAOHUO_HUIZONG_HEADERS, 62),
        ("邮件合并.xlsx", "数据透析", SHUJU_TOUXI_HEADERS, 62),
        ("邮件合并.xlsx", "工厂交货透视", ["工厂", "交货", "计数项:物料", "求和项:交货量", "求和项:总重量"], 200),
        ("邮件合并.xlsx", "奥妙明细", MINGXI_HEADERS, 30),
        ("邮件合并.xlsx", "奥妙小计", ["交货", "求和项:总重量", "求和项:业务量"], 12),
    ]

    sheets_map = {}
    for fname, sn, headers, rows in result_sheets:
        k, v = _sheet_info(fname, sn, headers, rows)
        sheets_map[k] = v

    with pytest.raises(ValueError, match="未找到可合并的数据"):
        select_source_sheets(sheets_map)


# =====================================================================
# RED 4: 数据透析 specifically excluded even with "交货" column
# =====================================================================

def test_select_source_sheets_excludes_shuju_touxi():
    """数据透析 has 交货 in headers but must be excluded (it's a result product).
    When only 数据透析 exists, should raise ValueError."""
    k, v = _sheet_info("邮件合并.xlsx", "数据透析", SHUJU_TOUXI_HEADERS, 62)
    sheets_map = {k: v}

    with pytest.raises(ValueError, match="未找到可合并的数据"):
        select_source_sheets(sheets_map)


# =====================================================================
# RED 5: 数据透析 with > 100 rows still excluded
# =====================================================================

def test_select_source_sheets_excludes_shuju_touxi_many_rows():
    """数据透析 with > 100 rows should still be excluded.
    When only 数据透析 exists, should raise ValueError."""
    k, v = _sheet_info("邮件合并.xlsx", "数据透析", SHUJU_TOUXI_HEADERS, 500)
    sheets_map = {k: v}

    with pytest.raises(ValueError, match="未找到可合并的数据"):
        select_source_sheets(sheets_map)


# =====================================================================
# RED 6: Mix of source + result sheets — only sources selected
# =====================================================================

def test_select_source_sheets_mixed():
    """When both source and result sheets exist, only sources selected."""
    sheets = [
        ("总表.xlsx", "明细", MINGXI_HEADERS, 500),
        ("总表.xlsx", "已发运", FAYUN_HEADERS, 100),
        ("总表.xlsx", "未发运", FAYUN_HEADERS, 50),
        ("邮件合并.xlsx", "全量数据", QUANLIANG_HEADERS, 7000),
        ("邮件合并.xlsx", "交货汇总", JIAOHUO_HUIZONG_HEADERS, 62),
        ("邮件合并.xlsx", "数据透析", SHUJU_TOUXI_HEADERS, 62),
        ("邮件合并.xlsx", "筛选数据", MINGXI_HEADERS, 200),
    ]

    sheets_map = {}
    for fname, sn, headers, rows in sheets:
        k, v = _sheet_info(fname, sn, headers, rows)
        sheets_map[k] = v

    selected = select_source_sheets(sheets_map)

    # Sources should be selected
    assert "总表.xlsx::明细" in selected
    assert "总表.xlsx::已发运" in selected
    assert "总表.xlsx::未发运" in selected
    # 筛选数据 also has 交货 header and > 100 rows — it's NOT in RESULT_SHEET_NAMES
    # so it should be selected (it acts as a data source in mail merge)
    assert "邮件合并.xlsx::筛选数据" in selected

    # Result products should be excluded
    assert "邮件合并.xlsx::全量数据" not in selected
    assert "邮件合并.xlsx::交货汇总" not in selected
    assert "邮件合并.xlsx::数据透析" not in selected


# =====================================================================
# RED 7: Fallback — if no 明细/发运 matched, select > 50 row sheets
# =====================================================================

def test_select_source_sheets_fallback():
    """When no 明细/发运 found, fall back to any non-result sheet with > 50 rows."""
    # A sheet that doesn't have "交货" in headers and isn't "发运"
    other_headers = ["日期", "仓库", "物料", "数量"]
    k, v = _sheet_info("其他.xlsx", "Sheet1", other_headers, 80)
    sheets_map = {k: v}

    selected = select_source_sheets(sheets_map)

    assert k in selected


# =====================================================================
# RED 8: No selectable sheets raises ValueError
# =====================================================================

def test_select_source_sheets_no_match_raises():
    """When no sheets can be selected, raise ValueError."""
    k, v = _sheet_info("其他.xlsx", "Sheet1", ["日期", "仓库"], 5)
    sheets_map = {k: v}

    with pytest.raises(ValueError, match="未找到可合并的数据"):
        select_source_sheets(sheets_map)


# =====================================================================
# RED 9: 明细 with exactly 100 rows — NOT selected (threshold is > 100)
# =====================================================================

def test_select_source_sheets_threshold_100():
    """明细 with <= 100 rows and <= 50 rows should NOT be selected
    (primary requires >100, fallback requires >50)."""
    k, v = _sheet_info("总表.xlsx", "明细", MINGXI_HEADERS, 30)
    sheets_map = {k: v}

    with pytest.raises(ValueError, match="未找到可合并的数据"):
        select_source_sheets(sheets_map)


# =====================================================================
# RED 10: 明细 with 101 rows — selected
# =====================================================================

def test_select_source_sheets_threshold_101():
    """明细 with 101 rows should be selected."""
    k, v = _sheet_info("总表.xlsx", "明细", MINGXI_HEADERS, 101)
    sheets_map = {k: v}

    selected = select_source_sheets(sheets_map)

    assert k in selected
