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
    assert match_row_province(row, ["江苏省"]) is True
    assert match_row_province(row, ["浙江省"]) is False


def test_merge_files_end_to_end(tmp_path):
    f = os.path.join(tmp_path, "a.xlsx")
    _make_xlsx(f, ["交货", "项目", "交货量", "送达方地点"],
               [["1001", "10", 5, "苏州市"],
                ["1002", "20", 3, "杭州市"]])
    out_dir = os.path.join(tmp_path, "out")
    os.makedirs(out_dir, exist_ok=True)
    result = merge_files([f], selected_sheets=None, provinces=["江苏省"],
                         rule_id=None, output_dir=out_dir, output_prefix="测试")
    assert os.path.exists(result["output_path"])
    assert result["stats"]["filtered_rows"] == 1  # 只保留苏州
