"""邮件读取器：从 126 邮箱读取 Excel 附件，自动合并筛选。"""
import os
import json
import time
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
