"""邮件读取器：从 126 邮箱读取 Excel 附件，自动合并筛选。"""
import os
import re
import json
import time
import base64
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


def load_processed_uids(path: str) -> set:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data)


def save_processed_uids(path: str, uids: set) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(uids), f)


def filter_new_uids(items: list, processed: set) -> list:
    # items 是 [(folder, uid_bytes), ...]，processed 是 {"folder::uid", ...}
    return [(f, u) for f, u in items if f"{f}::{u.decode()}" not in processed]


# ---------- IMAP 交互 ----------

EXCLUDED_FOLDERS = {"草稿箱", "已发送", "已删除", "垃圾邮件", "病毒邮件", "广告邮件", "订阅邮件", "废弃"}


def utf7_decode(s: str) -> str:
    result = []
    i = 0
    while i < len(s):
        if s[i] == '&':
            end = s.find('-', i)
            if end == -1:
                result.append(s[i:])
                break
            if end == i + 1:
                result.append('&')
            else:
                b64 = s[i + 1:end].replace(',', '/')
                try:
                    raw = base64.b64decode(b64 + '=' * (-len(b64) % 4))
                    result.append(raw.decode('utf-16-be'))
                except Exception:
                    result.append(s[i:end + 1])
            i = end + 1
        else:
            result.append(s[i])
            i += 1
    return ''.join(result)


def list_mail_folders(imap: imaplib.IMAP4_SSL) -> list:
    """返回 [(folder_raw, folder_decoded), ...]，排除系统文件夹"""
    typ, folders = imap.list()
    result = []
    for f in folders:
        raw = f.decode('utf-8', errors='replace')
        m = re.search(r'"([^"]*)"\s*$', raw)
        folder = m.group(1) if m else raw
        decoded = utf7_decode(folder)
        if decoded in EXCLUDED_FOLDERS:
            continue
        result.append((folder, decoded))
    return result


def connect_imap(host: str, email_addr: str, auth_code: str) -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL(host, 993)
    imap.login(email_addr, auth_code)
    # 网易邮箱要求客户端先发送非空 ID（RFC 2971），否则 SELECT 被拒
    imaplib.Commands["ID"] = ("AUTH",)
    imap._simple_command("ID", '("name" "ExcelMerger" "version" "1.0.0" "vendor" "ExcelMerger")')
    return imap


def search_mails(imap: imaplib.IMAP4_SSL, since_date: datetime.date, before_date: datetime.date = None) -> list:
    """搜索所有文件夹（排除系统文件夹），返回 [(folder, uid), ...]"""
    since_str = since_date.strftime("%d-%b-%Y")
    if before_date:
        before_str = before_date.strftime("%d-%b-%Y")
        criteria = f"(SINCE {since_str} BEFORE {before_str})"
    else:
        criteria = f"(SINCE {since_str})"
    results = []
    for folder, _decoded in list_mail_folders(imap):
        try:
            typ, _ = imap.select(f'"{folder}"', readonly=True)
            if typ != "OK":
                continue
            typ, data = imap.uid("search", None, criteria)
            if typ == "OK" and data and data[0]:
                for uid in data[0].split():
                    results.append((folder, uid))
        except Exception:
            continue
    return results


def download_excel_attachments(imap: imaplib.IMAP4_SSL, folder: str, uid: bytes, dest_dir: str, start_idx: int = 0) -> list:
    typ, _ = imap.select(f'"{folder}"', readonly=True)
    if typ != "OK":
        return []
    typ, msg_data = imap.uid("fetch", uid, "(RFC822)")
    if typ != "OK":
        return []
    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)
    saved = []
    idx = start_idx
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
        safe_name = f"{idx}_{decoded}"
        path = os.path.join(dest_dir, safe_name)
        with open(path, "wb") as f:
            f.write(payload)
        saved.append((path, decoded))
        idx += 1
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
    date_str = (cfg.get("date") or "").strip()
    if date_str:
        try:
            target = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target = datetime.date.today()
    else:
        target = datetime.date.today()
    since = target
    before = target + datetime.timedelta(days=1)
    uids_file = cfg.get("processed_uids_file", "data/processed_uids.json")
    processed = load_processed_uids(uids_file)
    output_dir = cfg.get("output_dir", "output")

    log(f"开始一轮：搜索 {target} 的邮件")
    imap = connect_imap(cfg["imap_host"], cfg["email"], cfg["auth_code"])
    task_mails = []
    try:
        items = search_mails(imap, since, before)
        new_items = filter_new_uids(items, processed)
        keywords = cfg.get("subject_keywords", [])
        log(f"共 {len(items)} 封邮件，其中新邮件 {len(new_items)} 封")
        handled = 0
        all_files = []
        with tempfile.TemporaryDirectory() as collect_dir:
            file_idx = 0
            for folder, uid in new_items:
                try:
                    imap.select(f'"{folder}"', readonly=True)
                    typ, data = imap.uid("fetch", uid, "(BODY[HEADER.FIELDS (SUBJECT)])")
                    subject = ""
                    if typ == "OK" and data and data[0]:
                        m = email.message_from_bytes(data[0][1])
                        subject = decode_subject(m.get("Subject", ""))
                    files = download_excel_attachments(imap, folder, uid, collect_dir, file_idx)
                    if not files:
                        log(f"跳过（无 Excel 附件）: {subject}")
                        continue
                    attachment_names = [name for _, name in files]
                    file_idx += len(files)
                    matched = matches_keywords(subject, keywords)
                    if matched:
                        all_files.extend([path for path, _ in files])
                        processed.add(f"{folder}::{uid.decode()}")
                        handled += 1
                        log(f"匹配: {subject} → {len(files)} 个附件")
                    else:
                        log(f"跳过（主题不匹配，含附件）: {subject}")
                    task_mails.append({
                        "subject": subject,
                        "attachments": attachment_names,
                        "processed": matched,
                    })
                except Exception as e:
                    log(f"处理失败: {uid.decode()} - {e}")
            if all_files:
                result = merge_files(
                    file_paths=all_files,
                    selected_sheets=None,
                    provinces=cfg.get("provinces", []),
                    rule_id=cfg.get("rule_id"),
                    output_dir=output_dir,
                    output_prefix=cfg.get("output_prefix", "邮件合并"),
                )
                log(f"合并完成: 全量 {result['stats']['total_merged_rows']} 行，筛选 {result['stats']['filtered_rows']} 行")
            else:
                log("无匹配附件，跳过合并")
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
