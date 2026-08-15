"""邮件读取器：从 126 邮箱读取 Excel 附件，自动合并筛选。"""
import os
import re
import json
import time
import threading
import imaplib
import email
import datetime
import tempfile
from email.header import decode_header
from typing import List, Set
from collections import deque

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
    # 网易邮箱要求客户端先发送非空 ID（RFC 2971），否则 SELECT 被拒
    imaplib.Commands["ID"] = ("AUTH",)
    imap._simple_command("ID", '("name" "ExcelMerger" "version" "1.0.0" "vendor" "ExcelMerger")')
    return imap


def search_mails(imap: imaplib.IMAP4_SSL, since_date: datetime.date) -> List[bytes]:
    typ, data = imap.select("INBOX")
    if typ != "OK":
        detail = data[0].decode(errors="replace") if data and data[0] else "未知错误"
        raise RuntimeError(f"选择收件箱失败: {detail}")
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

_logs = deque(maxlen=200)  # 内存日志，最近 200 条


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
    _logs.append(line)
    print(f"[mail_reader] {line}", flush=True)


def get_logs() -> List[str]:
    return list(_logs)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


TASKS_FILE = "data/tasks.json"
MAX_TASKS = 50


def load_tasks(path: str = TASKS_FILE) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_tasks(tasks: list, path: str = TASKS_FILE) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def clean_output_files(output_dir: str) -> None:
    if not os.path.isdir(output_dir):
        return
    files = [f for f in os.listdir(output_dir) if f.startswith("邮件合并") and f.endswith(".xlsx")]
    today = datetime.datetime.now().strftime("%Y%m%d")
    by_date = {}
    for f in files:
        m = re.search(r"(\d{8})", f)
        if not m:
            continue
        by_date.setdefault(m.group(1), []).append(f)
    for date, fs in by_date.items():
        if date == today:
            continue
        fs.sort(key=lambda f: os.path.getmtime(os.path.join(output_dir, f)))
        for f in fs[:-1]:
            try:
                os.remove(os.path.join(output_dir, f))
            except OSError:
                pass


def process_once(cfg: dict) -> int:
    since = datetime.date.today() - datetime.timedelta(days=max(0, int(cfg.get("days_back", 1)) - 1))
    uids_file = cfg.get("processed_uids_file", "data/processed_uids.json")
    processed = load_processed_uids(uids_file)
    output_dir = cfg.get("output_dir", "output")

    log(f"开始一轮：搜索 {since} 之后的邮件")
    imap = connect_imap(cfg["imap_host"], cfg["email"], cfg["auth_code"])
    task_mails = []
    try:
        uids = search_mails(imap, since)
        new_uids = filter_new_uids(uids, processed)
        keywords = cfg.get("subject_keywords", [])
        log(f"共 {len(uids)} 封邮件，其中新邮件 {len(new_uids)} 封")
        handled = 0
        for uid in new_uids:
            try:
                typ, data = imap.uid("fetch", uid, "(BODY[HEADER.FIELDS (SUBJECT)])")
                subject = ""
                if typ == "OK" and data and data[0]:
                    m = email.message_from_bytes(data[0][1])
                    subject = decode_subject(m.get("Subject", ""))
                with tempfile.TemporaryDirectory() as tmp:
                    files = download_excel_attachments(imap, uid, tmp)
                    if not files:
                        log(f"跳过（无 Excel 附件）: {subject}")
                        continue
                    attachment_names = [os.path.basename(f).split("_", 1)[-1] for f in files]
                    matched = matches_keywords(subject, keywords)
                    if matched:
                        result = merge_files(
                            file_paths=files,
                            selected_sheets=None,
                            provinces=cfg.get("provinces", []),
                            rule_id=cfg.get("rule_id"),
                            output_dir=output_dir,
                            output_prefix=cfg.get("output_prefix", "邮件合并"),
                        )
                        log(f"处理成功: {subject} → 全量 {result['stats']['total_merged_rows']} 行，筛选 {result['stats']['filtered_rows']} 行")
                    else:
                        log(f"跳过（主题不匹配，含附件）: {subject}")
                    task_mails.append({
                        "subject": subject,
                        "attachments": attachment_names,
                        "processed": matched,
                    })
                    if matched:
                        processed.add(uid)
                        handled += 1
            except Exception as e:
                log(f"处理失败: {uid.decode()} - {e}")
        save_processed_uids(uids_file, processed)
        if task_mails:
            task = {
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mails": task_mails,
            }
            tasks = load_tasks()
            tasks.insert(0, task)
            save_tasks(tasks[:MAX_TASKS])
        clean_output_files(output_dir)
        log(f"本轮完成，处理 {handled} 封邮件")
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
            log(f"本轮处理 {n} 封邮件，等待 {interval}s 后进行下一轮")
        except Exception as e:
            log(f"本轮异常: {e}")
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
