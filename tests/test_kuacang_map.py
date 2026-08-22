"""
TDD tests for 跨仓订单 (cross-warehouse order) file reader.
The 跨仓订单 file fills B_ADDRESS1/备注 in the 交货汇总 sheet
when logistics_map and so_map don't find a match.

File structure:
  - Sheet name: "跨仓结果仓库回传"
  - Row 0: title row (merged cells like "EO给到工单系统，无需填写")
  - Row 1: actual headers
  - Row 2+: data rows

Key columns (by header name in row 1):
  - OBD (col18): the delivery number → matches 交货号 in output
  - 客户订单号 (col1): → fills B_ADDRESS1
  - 备注 (col16): → fills 备注
  - 仓库备注 (col22): → appended to 备注
"""
import os
import datetime
import openpyxl
from merger import read_kuacang_map, build_pivot_by_delivery


# Headers for 跨仓订单 file (row 1)
KC_HEADERS = (
    "*E-Order订单号(必填)", "客户订单号", "客户原始订单号", "客户(售达方)编码",
    "客户(售达方)名称", "送达方编码", "送达方名称", "*行Id(必填)", "*行号(必填)",
    "*商品编码(必填)", "商品名称", "原发货仓", "原发库位", "新发货仓", "新发库位",
    "跨仓数量(箱)", "备注", "SAP订单号", "OBD", "交货量",
    "*仓库实际移仓量(箱)", "OBD", "仓库备注", "工单号", "填写人", "填写时间", "原因",
)


def _kc_row(cust_po, remark, obd, wh_remark=""):
    """Build a 跨仓订单 data row tuple."""
    row = [None] * len(KC_HEADERS)
    row[1] = cust_po
    row[16] = remark
    row[17] = "5507040000"
    row[18] = obd
    row[21] = None
    row[22] = wh_remark
    return tuple(row)


# =====================================================================
# RED 1: Basic case — OBD → 客户订单号 mapping
# =====================================================================

def test_read_kuacang_map_basic():
    """read_kuacang_map returns {OBD: {B_ADDRESS1, 备注}} from 跨仓结果仓库回传 sheet."""
    files_data = {
        "跨仓订单.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("PO123456", "", "2424827207"),
                _kc_row("PO789012", "", "2424827209"),
            ]),
        }
    }

    result = read_kuacang_map(files_data)

    assert "2424827207" in result
    assert result["2424827207"]["B_ADDRESS1"] == "PO123456"
    assert "2424827209" in result
    assert result["2424827209"]["B_ADDRESS1"] == "PO789012"


# =====================================================================
# RED 2: 备注 + 仓库备注 concatenation
# =====================================================================

def test_read_kuacang_map_remark_concat():
    """When both 备注 and 仓库备注 are non-empty, they should be concatenated."""
    files_data = {
        "跨仓订单.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("PO123456", "配额会释放", "2424827207", "无库存，未做单"),
            ]),
        }
    }

    result = read_kuacang_map(files_data)

    assert "2424827207" in result
    entry = result["2424827207"]
    assert entry["B_ADDRESS1"] == "PO123456"
    assert "配额会释放" in entry["备注"]
    assert "无库存，未做单" in entry["备注"]


# =====================================================================
# RED 3: Empty/zero OBD rows skipped
# =====================================================================

def test_read_kuacang_map_empty_obd_skipped():
    """Rows with empty/None/0 OBD should be skipped."""
    files_data = {
        "跨仓订单.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("PO123456", "", "2424827207"),
                _kc_row("PO999999", "", None),       # None OBD — skip
                _kc_row("PO000000", "", "0"),        # OBD=0 — skip
                _kc_row("PO111111", "", ""),         # empty OBD — skip
            ]),
        }
    }

    result = read_kuacang_map(files_data)

    assert "2424827207" in result
    assert len(result) == 1  # only the valid OBD row


# =====================================================================
# RED 4: build_pivot_by_delivery fills B_ADDRESS1 from kuacang_map
#         when logistics_map and so_map miss
# =====================================================================

def test_build_pivot_fills_from_kuacang_map():
    """build_pivot_by_delivery should use kuacang_map as 3rd source for B_ADDRESS1."""
    filtered_rows = [
        {
            "交货": "2424827207", "项目": "10", "交货量": 100,
            "总重量": 1.07, "业务量": 3.128, "工厂": "801",
            "销售凭证": "5507040787", "运达方": "18066037",
            "运达方的名字": "湖南文木", "送达方地点": "长沙市",
            "街道": "湖南省长沙市长沙县", "发货日期": datetime.datetime(2026, 8, 22),
            "交货日期": datetime.datetime(2026, 8, 26), "描述": "奥妙洗衣粉",
        },
    ]

    logistics_map = {}
    so_map = {}
    kuacang_map = {
        "2424827207": {"B_ADDRESS1": "PO15516585260821002-1", "备注": "配额会释放"}
    }

    headers, result, _ = build_pivot_by_delivery(
        filtered_rows, logistics_map, so_map, kuacang_map
    )

    data_row = [r for r in result if r[5] == "2424827207"]
    assert len(data_row) == 1
    row = data_row[0]

    # col 12 = B_ADDRESS1, col 13 = 备注
    assert row[12] == "PO15516585260821002-1"
    assert "配额会释放" in str(row[13])


# =====================================================================
# RED 5: logistics_map / so_map take priority over kuacang_map
# =====================================================================

def test_build_pivot_priority_logistics_over_kuacang():
    """logistics_map should take priority over kuacang_map."""
    filtered_rows = [
        {
            "交货": "2424827207", "项目": "10", "交货量": 100,
            "总重量": 1.07, "业务量": 3.128, "工厂": "801",
            "销售凭证": "5507040787", "运达方": "18066037",
            "运达方的名字": "湖南文木", "送达方地点": "长沙市",
            "街道": "湖南省长沙市长沙县", "发货日期": datetime.datetime(2026, 8, 22),
            "交货日期": datetime.datetime(2026, 8, 26), "描述": "奥妙洗衣粉",
        },
    ]

    logistics_map = {
        "5507040787": {"B_ADDRESS1": "FROM_LOGISTICS", "备注": "LOGI_REMARK"}
    }
    so_map = {}
    kuacang_map = {
        "2424827207": {"B_ADDRESS1": "FROM_KUACANG", "备注": "KC_REMARK"}
    }

    headers, result, _ = build_pivot_by_delivery(
        filtered_rows, logistics_map, so_map, kuacang_map
    )

    data_row = [r for r in result if r[5] == "2424827207"][0]
    assert data_row[12] == "FROM_LOGISTICS"
    assert "LOGI_REMARK" in str(data_row[13])


# =====================================================================
# EDGE CASE 1: 客户订单号 empty but 备注 present — should still capture OBD→备注
# =====================================================================

def test_read_kuacang_map_empty_cust_po_but_has_remark():
    """When 客户订单号 is empty but 备注/仓库备注 has data, should still
    capture the OBD with empty B_ADDRESS1 and the remark."""
    files_data = {
        "跨仓订单.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("", "配额会释放", "2424827207", "无库存"),
                _kc_row("PO123", "", "2424827209"),
            ]),
        }
    }

    result = read_kuacang_map(files_data)

    assert "2424827207" in result
    assert result["2424827207"]["B_ADDRESS1"] == ""
    assert "配额会释放" in result["2424827207"]["备注"]
    assert "无库存" in result["2424827207"]["备注"]
    assert "2424827209" in result
    assert result["2424827209"]["B_ADDRESS1"] == "PO123"


# =====================================================================
# EDGE CASE 2: Both 客户订单号 and 备注 empty — should skip row entirely
# =====================================================================

def test_read_kuacang_map_all_empty_skipped():
    """When both 客户订单号 and 备注/仓库备注 are empty, skip the row."""
    files_data = {
        "跨仓订单.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("", "", "2424827207", ""),
                _kc_row("PO123", "", "2424827209"),
            ]),
        }
    }

    result = read_kuacang_map(files_data)

    assert "2424827207" not in result  # No useful data — skip
    assert "2424827209" in result


# =====================================================================
# EDGE CASE 3: Partial fill — so_map fills B_ADDRESS1, kuacang fills 备注
# =====================================================================

def test_build_pivot_partial_fill_so_addr_kuacang_remark():
    """so_map fills B_ADDRESS1, kuacang_map fills only 备注."""
    filtered_rows = [
        {
            "交货": "2424827207", "项目": "10", "交货量": 100,
            "总重量": 1.07, "业务量": 3.128, "工厂": "801",
            "销售凭证": "5507040787", "运达方": "18066037",
            "运达方的名字": "湖南文木", "送达方地点": "长沙市",
            "街道": "湖南省长沙市长沙县", "发货日期": datetime.datetime(2026, 8, 22),
            "交货日期": datetime.datetime(2026, 8, 26), "描述": "奥妙洗衣粉",
        },
    ]

    logistics_map = {}
    so_map = {
        "2424827207": {"B_ADDRESS1": "FROM_SO", "备注": ""}
    }
    kuacang_map = {
        "2424827207": {"B_ADDRESS1": "FROM_KUACANG", "备注": "KC_REMARK"}
    }

    headers, result, _ = build_pivot_by_delivery(
        filtered_rows, logistics_map, so_map, kuacang_map
    )

    row = [r for r in result if str(r[5]) == "2424827207"][0]
    # so_map takes priority for B_ADDRESS1 (since it's checked before kuacang)
    assert row[12] == "FROM_SO"
    # so_map's 备注 is empty, so kuacang's 备注 should fill in
    assert "KC_REMARK" in str(row[13])


# =====================================================================
# EDGE CASE 4: Partial fill — logistics fills B_ADDRESS1, kuacang fills 备注
# =====================================================================

def test_build_pivot_partial_fill_logistics_addr_kuacang_remark():
    """logistics_map fills B_ADDRESS1, kuacang_map fills only 备注."""
    filtered_rows = [
        {
            "交货": "2424827207", "项目": "10", "交货量": 100,
            "总重量": 1.07, "业务量": 3.128, "工厂": "801",
            "销售凭证": "5507040787", "运达方": "18066037",
            "运达方的名字": "湖南文木", "送达方地点": "长沙市",
            "街道": "湖南省长沙市长沙县", "发货日期": datetime.datetime(2026, 8, 22),
            "交货日期": datetime.datetime(2026, 8, 26), "描述": "奥妙洗衣粉",
        },
    ]

    logistics_map = {
        "5507040787": {"B_ADDRESS1": "FROM_LOGI", "备注": ""}
    }
    so_map = {}
    kuacang_map = {
        "2424827207": {"B_ADDRESS1": "FROM_KUACANG", "备注": "KC_REMARK"}
    }

    headers, result, _ = build_pivot_by_delivery(
        filtered_rows, logistics_map, so_map, kuacang_map
    )

    row = [r for r in result if str(r[5]) == "2424827207"][0]
    assert row[12] == "FROM_LOGI"
    assert "KC_REMARK" in str(row[13])


# =====================================================================
# EDGE CASE 5: Multiple 跨仓订单 files — both should be processed
# =====================================================================

def test_read_kuacang_map_multiple_files():
    """Multiple files with 跨仓结果仓库回传 sheet should all be processed."""
    files_data = {
        "跨仓订单A.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("PO_A1", "", "2424827207"),
            ]),
        },
        "跨仓订单B.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("PO_B1", "", "2424827209"),
            ]),
        },
    }

    result = read_kuacang_map(files_data)

    assert "2424827207" in result
    assert result["2424827207"]["B_ADDRESS1"] == "PO_A1"
    assert "2424827209" in result
    assert result["2424827209"]["B_ADDRESS1"] == "PO_B1"


# =====================================================================
# EDGE CASE 6: Duplicate OBD across files — first-wins
# =====================================================================

def test_read_kuacang_map_duplicate_obd_across_files():
    """When same OBD appears in multiple files, first file's value wins."""
    files_data = {
        "跨仓订单A.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("PO_FIRST", "remark1", "2424827207"),
            ]),
        },
        "跨仓订单B.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("PO_SECOND", "remark2", "2424827207"),
            ]),
        },
    }

    result = read_kuacang_map(files_data)

    assert result["2424827207"]["B_ADDRESS1"] == "PO_FIRST"
    assert "remark1" in result["2424827207"]["备注"]


# =====================================================================
# EDGE CASE 7: OBD stored as float (from .xls via xlrd)
# =====================================================================

def test_read_kuacang_map_obd_as_float():
    """OBD stored as float (e.g., 2424827207.0 from xlrd) should normalize correctly."""
    row = list(_kc_row("PO123", "", "2424827207"))
    row[18] = 2424827207.0  # float as xlrd would read it
    files_data = {
        "跨仓订单.xls": {
            "跨仓结果仓库回传": (KC_HEADERS, [tuple(row)]),
        }
    }

    result = read_kuacang_map(files_data)

    # Float OBD should be normalized to int string "2424827207"
    # (not "2424827207.0") so it matches the 交货号 in build_pivot_by_delivery.
    assert "2424827207" in result
    assert result["2424827207"]["B_ADDRESS1"] == "PO123"


# =====================================================================
# EDGE CASE 8: Sheet name with extra whitespace
# =====================================================================

def test_read_kuacang_map_sheet_name_with_whitespace():
    """Sheet name with leading/trailing whitespace should still match."""
    files_data = {
        "跨仓订单.xlsx": {
            " 跨仓结果仓库回传 ": (KC_HEADERS, [
                _kc_row("PO123", "", "2424827207"),
            ]),
        }
    }

    result = read_kuacang_map(files_data)

    assert "2424827207" in result


# =====================================================================
# EDGE CASE 9: Only 仓库备注 present (no 客户订单号, no 备注)
# =====================================================================

def test_read_kuacang_map_only_warehouse_remark():
    """When only 仓库备注 has data, should capture OBD with that remark."""
    files_data = {
        "跨仓订单.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("", "", "2424827207", "仓库无库存"),
            ]),
        }
    }

    result = read_kuacang_map(files_data)

    assert "2424827207" in result
    assert result["2424827207"]["B_ADDRESS1"] == ""
    assert "仓库无库存" in result["2424827207"]["备注"]


# =====================================================================
# EDGE CASE 10: No kuacang_map passed — should not crash
# =====================================================================

def test_build_pivot_no_kuacang_map():
    """build_pivot_by_delivery should work when kuacang_map is None."""
    filtered_rows = [
        {
            "交货": "2424827207", "项目": "10", "交货量": 100,
            "总重量": 1.07, "业务量": 3.128, "工厂": "801",
            "销售凭证": "5507040787", "运达方": "18066037",
            "运达方的名字": "湖南文木", "送达方地点": "长沙市",
            "街道": "湖南省长沙市长沙县", "发货日期": datetime.datetime(2026, 8, 22),
            "交货日期": datetime.datetime(2026, 8, 26), "描述": "奥妙洗衣粉",
        },
    ]

    logistics_map = {"5507040787": {"B_ADDRESS1": "FROM_LOGI", "备注": "LOGI_REMARK"}}
    so_map = {}

    # kuacang_map defaults to None
    headers, result, _ = build_pivot_by_delivery(
        filtered_rows, logistics_map, so_map
    )

    row = [r for r in result if str(r[5]) == "2424827207"][0]
    assert row[12] == "FROM_LOGI"


# =====================================================================
# EDGE CASE 11: Empty files_data — should return empty dict
# =====================================================================

def test_read_kuacang_map_empty_files():
    """Empty files_data should return empty dict."""
    result = read_kuacang_map({})
    assert result == {}


# =====================================================================
# EDGE CASE 12: Files without 跨仓结果仓库回传 sheet
# =====================================================================

def test_read_kuacang_map_no_matching_sheet():
    """Files without 跨仓结果仓库回传 sheet should be silently skipped."""
    files_data = {
        "分销报表.xlsx": {
            "Sheet1": (("交货", "项目", "交货量"), [("2424827207", "10", 100)]),
        },
    }

    result = read_kuacang_map(files_data)
    assert result == {}


# =====================================================================
# EDGE CASE 13: OBD as string (not int) — type-safe matching
# =====================================================================

def test_read_kuacang_map_obd_as_string():
    """OBD stored as string '2424827207' should work correctly."""
    row = list(_kc_row("PO123", "", "2424827207"))
    row[18] = "2424827207"  # string OBD
    files_data = {
        "跨仓订单.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [tuple(row)]),
        }
    }

    result = read_kuacang_map(files_data)

    assert "2424827207" in result
    assert result["2424827207"]["B_ADDRESS1"] == "PO123"


# =====================================================================
# EDGE CASE 14: Sheet name matches but no OBD/客户订单号 columns
#               (e.g. 合肥内跨仓明细 files also have "跨仓结果仓库回传" sheet)
# =====================================================================

def test_read_kuacang_map_sheet_name_match_but_wrong_headers():
    """Sheet named 跨仓结果仓库回传 but without OBD/客户订单号 columns
    should be silently skipped (e.g. 合肥内跨仓明细 template files)."""
    files_data = {
        "合肥内跨仓明细.xlsx": {
            "跨仓结果仓库回传": (("EO给到工单系统，无需填写",), [
                ("26081900001782",),
                ("26081900001780",),
            ]),
        },
        "跨仓订单.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [
                _kc_row("PO123", "", "2424827207"),
            ]),
        },
    }

    result = read_kuacang_map(files_data)

    # Only the real 跨仓订单 file should produce entries
    assert len(result) == 1
    assert "2424827207" in result


# =====================================================================
# EDGE CASE 15: OBD with leading zeros (string format)
# =====================================================================

def test_read_kuacang_map_obd_with_leading_zeros():
    """OBD stored as string with leading zeros should be preserved as-is."""
    row = list(_kc_row("PO123", "", "2424827207"))
    row[18] = "02424827207"  # string with leading zero
    files_data = {
        "跨仓订单.xlsx": {
            "跨仓结果仓库回传": (KC_HEADERS, [tuple(row)]),
        }
    }

    result = read_kuacang_map(files_data)

    assert "02424827207" in result
    assert result["02424827207"]["B_ADDRESS1"] == "PO123"


# =====================================================================
# EDGE CASE 16: Remark from kuacang_map when logistics_map has B_ADDRESS1
#               but empty 备注 (cross-source partial fill)
# =====================================================================

def test_build_pivot_logistics_addr_kuacang_remark_cross_fill():
    """logistics fills B_ADDRESS1 + empty 备注, kuacang fills only 备注."""
    filtered_rows = [
        {
            "交货": "2424827207", "项目": "10", "交货量": 100,
            "总重量": 1.07, "业务量": 3.128, "工厂": "801",
            "销售凭证": "5507040787", "运达方": "18066037",
            "运达方的名字": "湖南文木", "送达方地点": "长沙市",
            "街道": "湖南省长沙市长沙县", "发货日期": datetime.datetime(2026, 8, 22),
            "交货日期": datetime.datetime(2026, 8, 26), "描述": "奥妙洗衣粉",
        },
    ]

    logistics_map = {
        "5507040787": {"B_ADDRESS1": "LOGI_ADDR", "备注": "LOGI_REMARK"}
    }
    so_map = {}
    kuacang_map = {
        "2424827207": {"B_ADDRESS1": "KC_ADDR", "备注": "KC_REMARK"}
    }

    headers, result, _ = build_pivot_by_delivery(
        filtered_rows, logistics_map, so_map, kuacang_map
    )

    row = [r for r in result if str(r[5]) == "2424827207"][0]
    # logistics takes full priority — both B_ADDRESS1 and 备注 from logistics
    assert row[12] == "LOGI_ADDR"
    assert "LOGI_REMARK" in str(row[13])
    # kuacang values should NOT appear
    assert "KC_ADDR" not in str(row[12])
    assert "KC_REMARK" not in str(row[13])
