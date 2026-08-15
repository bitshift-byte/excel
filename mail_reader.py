"""邮件读取器：从 126 邮箱读取 Excel 附件，自动合并筛选。"""
import os
import json
import time
import threading
import imaplib
import email
import datetime
import tempfile
from email.header import decode_header
from typing import List, Set

from merger import merge_files


# ---------- 纯逻辑（可测试） ----------

def matches_keywords(subject: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    return any(k and k in subject for k in keywords)


def is_excel_attachment(filename: str) -> bool:
    return filename.lower().endswith((".xlsx", ".xls", ".csv", ".tsv"))


def decode_subject(raw) -> str:
    if not raw:
        return ""
    parts = decode_header(raw)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def load_processed_uids(path: str) -> Set[bytes]:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(x.encode() for x in data)


def save_processed_uids(path: str, uids: Set[bytes]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(x.decode() for x in uids), f)


def filter_new_uids(uids: List[bytes], processed: Set[bytes]) -> List[bytes]:
    return [u for u in uids if u not in processed]


# ---------- IMAP 交互 ----------

def connect_imap(host: str, email_addr: str, auth_code: str) -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL(host, 993)
    imap.login(email_addr, auth_code)
    return imap


def search_mails(imap: imaplib.IMAP4_SSL, since_date: datetime.date) -> List[bytes]:
    imap.select("INBOX")
    date_str = since_date.strftime("%d-%b-%Y")
    typ, data = imap.uid("search", None, f"(SINCE {date_str})")
    if typ != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def download_excel_attachments(imap: imaplib.IMAP4_SSL, uid: bytes, dest_dir: str) -> List[str]:
    typ, msg_data = imap.uid("fetch", uid, "(RFC822)")
    if typ != "OK":
        return []
    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)
    saved = []
    for part in msg.walk():
        filename = part.get_filename()
        if not filename:
            continue
        decoded = decode_subject(filename)
        if not is_excel_attachment(decoded):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        safe_name = f"{uid.decode()}_{decoded}"
        path = os.path.join(dest_dir, safe_name)
        with open(path, "wb") as f:
            f.write(payload)
        saved.append(path)
    return saved


# ---------- 主流程 ----------

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_once(cfg: dict) -> int:
    since = datetime.date.today() - datetime.timedelta(days=max(0, int(cfg.get("days_back", 1)) - 1))
    uids_file = cfg.get("processed_uids_file", "processed_uids.json")
    processed = load_processed_uids(uids_file)
    output_dir = cfg.get("output_dir", "output")

    imap = connect_imap(cfg["imap_host"], cfg["email"], cfg["auth_code"])
    try:
        uids = search_mails(imap, since)
        new_uids = filter_new_uids(uids, processed)
        keywords = cfg.get("subject_keywords", [])
        handled = 0
        for uid in new_uids:
            try:
                typ, data = imap.uid("fetch", uid, "(BODY[HEADER.FIELDS (SUBJECT)])")
                subject = ""
                if typ == "OK" and data and data[0]:
                    m = email.message_from_bytes(data[0][1])
                    subject = decode_subject(m.get("Subject", ""))
                if not matches_keywords(subject, keywords):
                    continue
                with tempfile.TemporaryDirectory() as tmp:
                    files = download_excel_attachments(imap, uid, tmp)
                    if not files:
                        continue
                    merge_files(
                        file_paths=files,
                        selected_sheets=None,
                        provinces=cfg.get("provinces", []),
                        rule_id=cfg.get("rule_id"),
                        output_dir=output_dir,
                        output_prefix=cfg.get("output_prefix", "邮件合并"),
                    )
                processed.add(uid)
                handled += 1
            except Exception as e:
                print(f"[mail_reader] 处理邮件 {uid.decode()} 失败: {e}")
        save_processed_uids(uids_file, processed)
        return handled
    finally:
        imap.logout()


def main():
    cfg_path = os.environ.get("MAIL_CONFIG", "mail_config.json")
    cfg = load_config(cfg_path)
    interval = int(cfg.get("poll_interval_seconds", 3600))
    print(f"[mail_reader] 启动，轮询间隔 {interval}s，配置 {cfg_path}")
    start_background(cfg)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        stop_background()


# ---------- 后台线程管理 ----------

_stop_event = threading.Event()
_worker_thread = None


def _run_loop(cfg: dict):
    interval = int(cfg.get("poll_interval_seconds", 3600))
    while not _stop_event.is_set():
        try:
            n = process_once(cfg)
            print(f"[mail_reader] 本轮处理 {n} 封邮件: {datetime.datetime.now()}")
        except Exception as e:
            print(f"[mail_reader] 本轮异常: {e}")
        _stop_event.wait(interval)


def start_background(cfg: dict) -> bool:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return False
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_run_loop, args=(cfg,), daemon=True)
    _worker_thread.start()
    return True


def stop_background() -> bool:
    global _worker_thread
    if not _worker_thread or not _worker_thread.is_alive():
        return False
    _stop_event.set()
    _worker_thread.join(timeout=5)
    _worker_thread = None
    return True


def is_running() -> bool:
    return _worker_thread is not None and _worker_thread.is_alive()


if __name__ == "__main__":
    main()
