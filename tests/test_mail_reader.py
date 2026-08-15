from mail_reader import matches_keywords, is_excel_attachment, filter_new_uids


def test_matches_keywords_or():
    assert matches_keywords("8月总表数据", ["总表", "月报"]) is True
    assert matches_keywords("客户月报", ["总表", "月报"]) is True
    assert matches_keywords("无关邮件", ["总表", "月报"]) is False
    assert matches_keywords("任意主题", []) is True  # 空关键词 = 全部通过


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
