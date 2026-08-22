"""
TDD tests for build_data_pivot — generates the "数据透析" sheet.

The 数据透析 sheet is a re-ordered, re-sorted, trimmed version of 交货汇总:
  - 12 columns (drops B_ADDRESS1, 备注, 1, 2)
  - Sorted by 交货 (delivery number) ascending
  - 2 empty rows before the header (handled in merge_files, not here)
  - (空白) row before 总计
  - 总计 row with same sums as 交货汇总

交货汇总 16-col layout:
  [0]发货日期 [1]交货日期 [2]送达方地点 [3]运达方 [4]销售凭证
  [5]交货 [6]运达方的名字 [7]街道
  [8]求和项:交货量 [9]求和项:总重量 [10]求和项:业务量 [11]工厂
  [12]B_ADDRESS1 [13]备注 [14]1 [15]2

数据透析 12-col layout:
  [0]交货 [1]销售凭证 [2]运达方 [3]运达方的名字 [4]送达方地点
  [5]工厂 [6]街道 [7]发货日期 [8]交货日期
  [9]求和项:交货量 [10]求和项:总重量 [11]求和项:业务量
"""
import datetime
from merger import build_data_pivot


# 交货汇总 headers (16 cols)
P4_HEADERS = [
    "发货日期", "交货日期", "送达方地点", "运达方", "销售凭证",
    "交货", "运达方的名字", "街道",
    "求和项:交货量", "求和项:总重量", "求和项:业务量", "工厂",
    "B_ADDRESS1", "备注", "1", "2",
]

def _p4_row(delivery, sales_doc, ship_to, ship_to_name, city, factory, street,
           fa_date, jr_date, jhl, zzl, ywl,
           addr1="", remark="", col1=None, col2=None):
    """Build a 交货汇总 data row (16 cols)."""
    return [
        fa_date, jr_date, city, ship_to, sales_doc,
        delivery, ship_to_name, street,
        jhl, zzl, ywl, factory,
        addr1, remark, col1, col2,
    ]

P4_TOTAL = [
    "总计", None, None, None, None, None, None, None,
    100, 10.0, 30.0, None, None, None, None, None,
]


# =====================================================================
# RED 1: Basic column reorder — 交货 should be first column
# =====================================================================

def test_build_data_pivot_basic_reorder():
    """数据透析 first column should be 交货 (from 交货汇总 index 5)."""
    p4_data = [
        _p4_row("2424830001", "5507040001", "18000001", "客户A", "长沙市",
                "8136", "街道A", datetime.date(2026, 8, 22), datetime.date(2026, 8, 25),
                10, 1.0, 3.0),
        P4_TOTAL,
    ]
    dp_headers, dp_data = build_data_pivot(P4_HEADERS, p4_data)

    assert dp_headers[0] == "交货"
    assert dp_headers[1] == "销售凭证"
    assert dp_headers[2] == "运达方"
    assert dp_headers[3] == "运达方的名字"
    assert dp_headers[4] == "送达方地点"
    assert dp_headers[5] == "工厂"
    assert dp_headers[6] == "街道"
    assert dp_headers[7] == "发货日期"
    assert dp_headers[8] == "交货日期"
    assert dp_headers[9] == "求和项:交货量"
    assert dp_headers[10] == "求和项:总重量"
    assert dp_headers[11] == "求和项:业务量"
    assert len(dp_headers) == 12


# =====================================================================
# RED 2: Data row values are correctly mapped
# =====================================================================

def test_build_data_pivot_row_values():
    """Each data row should have values in the correct reordered positions."""
    p4_data = [
        _p4_row("2424830001", "5507040001", "18000001", "客户A", "长沙市",
                "8136", "街道A", datetime.date(2026, 8, 22), datetime.date(2026, 8, 25),
                10, 1.0, 3.0,
                addr1="ADDR1", remark="备注X", col1=0.5, col2=1.5),
        P4_TOTAL,
    ]
    dp_headers, dp_data = build_data_pivot(P4_HEADERS, p4_data)

    # First data row (before 空白 and 总计)
    row = dp_data[0]
    assert row[0] == "2424830001"          # 交货
    assert row[1] == "5507040001"          # 销售凭证
    assert row[2] == "18000001"            # 运达方
    assert row[3] == "客户A"               # 运达方的名字
    assert row[4] == "长沙市"             # 送达方地点
    assert row[5] == "8136"               # 工厂
    assert row[6] == "街道A"              # 街道
    assert row[7] == datetime.date(2026, 8, 22)  # 发货日期
    assert row[8] == datetime.date(2026, 8, 25)  # 交货日期
    assert row[9] == 10                   # 求和项:交货量
    assert row[10] == 1.0                 # 求和项:总重量
    assert row[11] == 3.0                 # 求和项:业务量
    assert len(row) == 12                 # No extra columns


# =====================================================================
# RED 3: Drops B_ADDRESS1, 备注, 1, 2 columns
# =====================================================================

def test_build_data_pivot_drops_extra_cols():
    """数据透析 should have exactly 12 columns, no B_ADDRESS1/备注/1/2."""
    p4_data = [
        _p4_row("2424830001", "5507040001", "18000001", "客户A", "长沙市",
                "8136", "街道A", datetime.date(2026, 8, 22), datetime.date(2026, 8, 25),
                10, 1.0, 3.0,
                addr1="ADDR1", remark="备注X", col1=0.5, col2=1.5),
        P4_TOTAL,
    ]
    dp_headers, dp_data = build_data_pivot(P4_HEADERS, p4_data)

    assert "B_ADDRESS1" not in dp_headers
    assert "备注" not in dp_headers
    assert "1" not in dp_headers
    assert "2" not in dp_headers
    for row in dp_data:
        assert len(row) == 12


# =====================================================================
# RED 4: Sorted by 交货 ascending
# =====================================================================

def test_build_data_pivot_sorted_by_delivery():
    """Data rows should be sorted by 交货 number ascending."""
    p4_data = [
        _p4_row("2424830003", "5507040003", "18000003", "客户C", "株洲市",
                "8136", "街道C", datetime.date(2026, 8, 22), datetime.date(2026, 8, 26),
                30, 3.0, 9.0),
        _p4_row("2424830001", "5507040001", "18000001", "客户A", "长沙市",
                "8136", "街道A", datetime.date(2026, 8, 22), datetime.date(2026, 8, 25),
                10, 1.0, 3.0),
        _p4_row("2424830002", "5507040002", "18000002", "客户B", "衡阳市",
                "8136", "街道B", datetime.date(2026, 8, 22), datetime.date(2026, 8, 27),
                60, 6.0, 18.0),
        P4_TOTAL,
    ]
    dp_headers, dp_data = build_data_pivot(P4_HEADERS, p4_data)

    # Data rows are all rows except (空白) and 总计
    data_rows = [r for r in dp_data if r[0] not in ("(空白)", "总计")]
    deliveries = [r[0] for r in data_rows]
    assert deliveries == ["2424830001", "2424830002", "2424830003"]


# =====================================================================
# RED 5: (空白) row exists before 总计
# =====================================================================

def test_build_data_pivot_blank_row():
    """A (空白) row should appear immediately before the 总计 row."""
    p4_data = [
        _p4_row("2424830001", "5507040001", "18000001", "客户A", "长沙市",
                "8136", "街道A", datetime.date(2026, 8, 22), datetime.date(2026, 8, 25),
                10, 1.0, 3.0),
        P4_TOTAL,
    ]
    dp_headers, dp_data = build_data_pivot(P4_HEADERS, p4_data)

    # Last two rows should be (空白) then 总计
    assert dp_data[-2][0] == "(空白)"
    assert dp_data[-1][0] == "总计"

    # (空白) row: text columns are "(空白)", numeric columns are None
    blank_row = dp_data[-2]
    assert blank_row[0] == "(空白)"
    assert blank_row[9] is None   # 求和项:交货量
    assert blank_row[10] is None  # 求和项:总重量
    assert blank_row[11] is None  # 求和项:业务量


# =====================================================================
# RED 6: 总计 row has correct sums
# =====================================================================

def test_build_data_pivot_total_row():
    """总计 row should have sums matching 交货汇总 total."""
    p4_total = [
        "总计", None, None, None, None, None, None, None,
        12605, 139.503, 358.145, None, None, None, None, None,
    ]
    p4_data = [
        _p4_row("2424830001", "5507040001", "18000001", "客户A", "长沙市",
                "8136", "街道A", datetime.date(2026, 8, 22), datetime.date(2026, 8, 25),
                12605, 139.503, 358.145),
        p4_total,
    ]
    dp_headers, dp_data = build_data_pivot(P4_HEADERS, p4_data)

    total_row = dp_data[-1]
    assert total_row[0] == "总计"
    assert total_row[9] == 12605      # 求和项:交货量
    assert total_row[10] == 139.503   # 求和项:总重量
    assert total_row[11] == 358.145   # 求和项:业务量
    # Non-sum columns should be None
    assert total_row[1] is None       # 销售凭证
    assert total_row[5] is None       # 工厂


# =====================================================================
# RED 7: Empty input (only 总计 row, no data)
# =====================================================================

def test_build_data_pivot_empty_data():
    """When p4_data has only the 总计 row, output should have (空白) + 总计 only."""
    p4_total = [
        "总计", None, None, None, None, None, None, None,
        0, 0, 0, None, None, None, None, None,
    ]
    dp_headers, dp_data = build_data_pivot(P4_HEADERS, [p4_total])

    # Should still have headers
    assert len(dp_headers) == 12
    # Should have (空白) and 总计 rows, no data rows
    data_rows = [r for r in dp_data if r[0] not in ("(空白)", "总计")]
    assert len(data_rows) == 0
    assert dp_data[-2][0] == "(空白)"
    assert dp_data[-1][0] == "总计"


# =====================================================================
# RED 8: Multiple data rows with same delivery (shouldn't happen in
# practice, but verify sorting is stable)
# =====================================================================

def test_build_data_pivot_total_row_position():
    """总计 row should always be the last row, (空白) second to last."""
    p4_data = [
        _p4_row("2424830001", "5507040001", "18000001", "客户A", "长沙市",
                "8136", "街道A", datetime.date(2026, 8, 22), datetime.date(2026, 8, 25),
                10, 1.0, 3.0),
        _p4_row("2424830002", "5507040002", "18000002", "客户B", "衡阳市",
                "8136", "街道B", datetime.date(2026, 8, 22), datetime.date(2026, 8, 27),
                20, 2.0, 6.0),
        P4_TOTAL,
    ]
    dp_headers, dp_data = build_data_pivot(P4_HEADERS, p4_data)

    assert dp_data[-1][0] == "总计"
    assert dp_data[-2][0] == "(空白)"
    # 2 data rows + (空白) + 总计 = 4 rows
    assert len(dp_data) == 4
