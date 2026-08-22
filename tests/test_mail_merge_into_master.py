"""
TDD tests for merge_mail_into_master — 
merges daily mail-fetched data INTO the 总表 (master table) format.

Instead of generating analysis sheets (全量数据/筛选数据/交货汇总),
this function appends new 交货号 from the mail-fetched file
to the 总表's 明细 sheet, preserving the 总表 format.
"""
import os
import datetime
import openpyxl
import pytest
from merger import merge_mail_into_master


# 总表 明细 headers (37 cols, with empty cols at 1, 35, 36)
MASTER_HEADERS = (
    "交货", "", "DlvTy", "项目", "物料", "描述", "存储位置", "销售凭证",
    "运达方", "运达方的名字", "送达方地点", "名称 3", "工厂", "路线", "OPS", "WhN",
    "批次", "仓位", "GM", "销售组织", "售达方", "售达方", "街道", "街道2",
    "街道 3", "交货量", "SU", "数量(库存单位)", "计", "总重量", "WUn",
    "业务量", "VUn", "交货日期", "发货日期", "", "",
)

# Mail-fetched 筛选数据 headers (34 cols)
MAIL_HEADERS = (
    "交货", "DlvTy", "项目", "物料", "描述", "存储位置", "销售凭证",
    "运达方", "运达方的名字", "送达方地点", "名称 3", "工厂", "路线", "OPS", "WhN",
    "批次", "仓位", "GM", "销售组织", "售达方", "售达方", "街道", "街道2",
    "街道 3", "交货量", "SU", "数量(库存单位)", "计", "总重量", "WUn",
    "业务量", "VUn", "交货日期", "发货日期",
)


def _make_master_row(jiaohuo="2424827207"):
    """Build a 明细 row in 总表 format (37 cols)."""
    row = [None] * 37
    row[0] = jiaohuo
    row[2] = "ZLF1"
    row[3] = "000010"
    row[33] = datetime.datetime(2026, 8, 26)
    row[34] = datetime.datetime(2026, 8, 22)
    return tuple(row)


def _make_mail_row(jiaohuo="2424827180"):
    """Build a 筛选数据 row in mail format (34 cols)."""
    row = [None] * 34
    row[0] = jiaohuo
    row[1] = "ZLF1"
    row[2] = "000010"
    row[32] = datetime.datetime(2026, 8, 28)
    row[33] = datetime.datetime(2026, 8, 22)
    return tuple(row)


def _create_master_file(path, existing_rows):
    """Create a 总表 xlsx with 明细 sheet containing existing rows."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "明细"
    # Write headers
    for c, h in enumerate(MASTER_HEADERS, 1):
        ws.cell(row=1, column=c, value=h)
    # Write existing data
    for r, row in enumerate(existing_rows, 2):
        for c, v in enumerate(row, 1):
            if v is not None:
                ws.cell(row=r, column=c, value=v)
    # Add other sheets
    for sn in ("已发运", "未发运", "客户信息", "组套", "Sheet5"):
        wb.create_sheet(sn)
        ws2 = wb[sn]
        ws2.cell(row=1, column=1, value="header")
    wb.save(path)
    wb.close()


def _create_mail_file(path, rows, sheet_name="筛选数据"):
    """Create a mail-fetched xlsx with 筛选数据 sheet."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    # Write headers
    for c, h in enumerate(MAIL_HEADERS, 1):
        ws.cell(row=1, column=c, value=h)
    # Write data
    for r, row in enumerate(rows, 2):
        for c, v in enumerate(row, 1):
            if v is not None:
                ws.cell(row=r, column=c, value=v)
    # Also add 全量数据 sheet (same structure)
    ws2 = wb.create_sheet("全量数据")
    for c, h in enumerate(MAIL_HEADERS, 1):
        ws2.cell(row=1, column=c, value=h)
    wb.save(path)
    wb.close()


# =====================================================================
# RED 1: New 交货号 from mail file appended to 明细
# =====================================================================

def test_merge_appends_new_jiaohuo(tmp_path):
    """New 交货号 from mail file should be appended to 明细 sheet."""
    master_path = str(tmp_path / "master.xlsx")
    mail_path = str(tmp_path / "mail.xlsx")
    output_path = str(tmp_path / "output.xlsx")

    _create_master_file(master_path, [_make_master_row("2424827207")])
    _create_mail_file(mail_path, [_make_mail_row("2424827180")])

    result = merge_mail_into_master(master_path, mail_path, output_path)

    wb = openpyxl.load_workbook(output_path, read_only=True, data_only=True)
    ws = wb["明细"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    data_rows = [r for r in rows if r[0] is not None]
    
    # Should have 2 rows: original + new
    assert len(data_rows) == 2
    jiaohuo_list = [str(r[0]) for r in data_rows]
    assert "2424827207" in jiaohuo_list
    assert "2424827180" in jiaohuo_list
    wb.close()


# =====================================================================
# RED 2: Duplicate 交货号 NOT re-appended
# =====================================================================

def test_merge_skips_duplicate_jiaohuo(tmp_path):
    """交货号 already in 明细 should not be appended again."""
    master_path = str(tmp_path / "master.xlsx")
    mail_path = str(tmp_path / "mail.xlsx")
    output_path = str(tmp_path / "output.xlsx")

    _create_master_file(master_path, [_make_master_row("2424827207")])
    _create_mail_file(mail_path, [_make_mail_row("2424827207")])  # same 交货号

    merge_mail_into_master(master_path, mail_path, output_path)

    wb = openpyxl.load_workbook(output_path, read_only=True, data_only=True)
    ws = wb["明细"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    data_rows = [r for r in rows if r[0] is not None]
    
    # Should still have only 1 row (no duplicate)
    assert len(data_rows) == 1
    wb.close()


# =====================================================================
# RED 3: All 总表 sheets preserved
# =====================================================================

def test_merge_preserves_all_sheets(tmp_path):
    """Output should have all sheets from 总表: 已发运, 未发运, 明细, etc."""
    master_path = str(tmp_path / "master.xlsx")
    mail_path = str(tmp_path / "mail.xlsx")
    output_path = str(tmp_path / "output.xlsx")

    _create_master_file(master_path, [_make_master_row("2424827207")])
    _create_mail_file(mail_path, [_make_mail_row("2424827180")])

    merge_mail_into_master(master_path, mail_path, output_path)

    wb = openpyxl.load_workbook(output_path, read_only=True)
    expected_sheets = {"明细", "已发运", "未发运", "客户信息", "组套", "Sheet5"}
    assert set(wb.sheetnames) == expected_sheets
    wb.close()


# =====================================================================
# RED 4: Column mapping correct (37 cols, empty at 1, 35, 36)
# =====================================================================

def test_merge_column_mapping(tmp_path):
    """Appended rows should have correct column mapping (37 cols)."""
    master_path = str(tmp_path / "master.xlsx")
    mail_path = str(tmp_path / "mail.xlsx")
    output_path = str(tmp_path / "output.xlsx")

    _create_master_file(master_path, [])
    _create_mail_file(mail_path, [_make_mail_row("2424827180")])

    merge_mail_into_master(master_path, mail_path, output_path)

    wb = openpyxl.load_workbook(output_path, read_only=True, data_only=True)
    ws = wb["明细"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    data_rows = [r for r in rows if r[0] is not None]
    
    assert len(data_rows) == 1
    row = data_rows[0]
    # 37 columns
    assert len(row) == 37
    # 交货号 in col 0
    assert str(row[0]) == "2424827180"
    # Col 1 is empty
    assert row[1] is None or row[1] == ""
    # DlvTy in col 2 (was col 1 in mail)
    assert str(row[2]) == "ZLF1"
    # 项目 in col 3 (was col 2 in mail)
    assert str(row[3]) == "000010"
    # 交货日期 in col 33 (was col 32 in mail)
    assert row[33] is not None
    # 发货日期 in col 34 (was col 33 in mail)
    assert row[34] is not None
    wb.close()


# =====================================================================
# RED 5: Returns output path
# =====================================================================

def test_merge_returns_output_path(tmp_path):
    """Function should return the output file path."""
    master_path = str(tmp_path / "master.xlsx")
    mail_path = str(tmp_path / "mail.xlsx")
    output_path = str(tmp_path / "output.xlsx")

    _create_master_file(master_path, [])
    _create_mail_file(mail_path, [_make_mail_row("2424827180")])

    result = merge_mail_into_master(master_path, mail_path, output_path)
    
    assert "output_path" in result
    assert os.path.exists(result["output_path"])
    assert "appended_count" in result
    assert result["appended_count"] == 1


# =====================================================================
# RED 6: Multiple new 交货号 appended
# =====================================================================

def test_merge_multiple_new(tmp_path):
    """Multiple new 交货号 should all be appended."""
    master_path = str(tmp_path / "master.xlsx")
    mail_path = str(tmp_path / "mail.xlsx")
    output_path = str(tmp_path / "output.xlsx")

    _create_master_file(master_path, [
        _make_master_row("2424827207"),
        _make_master_row("2424827208"),
    ])
    _create_mail_file(mail_path, [
        _make_mail_row("2424827180"),
        _make_mail_row("2424827181"),
        _make_mail_row("2424827182"),
        _make_mail_row("2424827207"),  # duplicate, should be skipped
    ])

    result = merge_mail_into_master(master_path, mail_path, output_path)

    wb = openpyxl.load_workbook(output_path, read_only=True, data_only=True)
    ws = wb["明细"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    data_rows = [r for r in rows if r[0] is not None]
    
    # 2 original + 3 new (1 duplicate skipped)
    assert len(data_rows) == 5
    assert result["appended_count"] == 3
    wb.close()
