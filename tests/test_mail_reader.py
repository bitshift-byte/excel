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
    processed = {"INBOX::1", "INBOX::2"}
    new = filter_new_uids([("INBOX", b"1"), ("INBOX", b"2"), ("INBOX", b"3")], processed)
    assert new == [("INBOX", b"3")]


def test_background_thread_start_stop(monkeypatch):
    import time
    import mail_reader
    monkeypatch.setattr(mail_reader, "process_once", lambda cfg: 0)
    assert mail_reader.is_running() is False
    assert mail_reader.start_background({"poll_interval_seconds": 3600}) is True
    time.sleep(0.2)
    assert mail_reader.is_running() is True
    assert mail_reader.stop_background() is True
    assert mail_reader.is_running() is False


def test_clean_output_files(tmp_path):
    import os
    import datetime
    from mail_reader import clean_output_files
    today = datetime.datetime.now().strftime("%Y%m%d")
    names = [f"邮件合并_湖南_{today}_a.xlsx", f"邮件合并_湖南_{today}_b.xlsx",
             "邮件合并_湖南_20260814_a.xlsx", "邮件合并_湖南_20260814_b.xlsx"]
    for f in names:
        p = os.path.join(tmp_path, f)
        open(p, "w").close()
        os.utime(p, (100, 100))
    # 让历史日期 b 比 a 新（b 应被保留）
    os.utime(os.path.join(tmp_path, "邮件合并_湖南_20260814_b.xlsx"), (200, 200))
    clean_output_files(str(tmp_path))
    remain = sorted(os.listdir(tmp_path))
    assert f"邮件合并_湖南_{today}_a.xlsx" in remain  # 当天全留
    assert f"邮件合并_湖南_{today}_b.xlsx" in remain
    assert "邮件合并_湖南_20260814_b.xlsx" in remain  # 历史留最后一个（最新）
    assert "邮件合并_湖南_20260814_a.xlsx" not in remain  # 历史旧的删除
