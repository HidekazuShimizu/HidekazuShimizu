"""SMTP による送信と、IMAP の「送信済み」フォルダへの保存。"""

from __future__ import annotations

import imaplib
import re
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid


@dataclass
class MailAccount:
    sender_name: str
    sender_email: str
    smtp_host: str
    smtp_port: int
    smtp_security: str  # "SSL" or "STARTTLS"
    smtp_user: str
    smtp_password: str
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    save_to_sent: bool = True
    sent_folder: str = ""


class MailError(Exception):
    pass


def build_message(account: MailAccount, to_name: str, to_addr: str,
                  subject: str, body: str,
                  in_reply_to: str = "", references: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((account.sender_name, account.sender_email)) \
        if account.sender_name else account.sender_email
    msg["To"] = formataddr((to_name, to_addr)) if to_name else to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    domain = account.sender_email.split("@")[-1] if "@" in account.sender_email else None
    msg["Message-ID"] = make_msgid(domain=domain)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = (references + " " + in_reply_to).strip()
    msg.set_content(body, charset="utf-8")
    return msg


class SmtpSession:
    """複数通を1回の接続で順番に送るためのセッション。"""

    def __init__(self, account: MailAccount, timeout: int = 30):
        self.account = account
        self.timeout = timeout
        self.smtp: smtplib.SMTP | None = None

    def __enter__(self):
        a = self.account
        ctx = ssl.create_default_context()
        try:
            if a.smtp_security.upper() == "SSL":
                self.smtp = smtplib.SMTP_SSL(a.smtp_host, a.smtp_port, context=ctx, timeout=self.timeout)
            else:
                self.smtp = smtplib.SMTP(a.smtp_host, a.smtp_port, timeout=self.timeout)
                self.smtp.ehlo()
                if a.smtp_security.upper() == "STARTTLS":
                    self.smtp.starttls(context=ctx)
                    self.smtp.ehlo()
                # "NONE" は暗号化なし（テスト用。画面からは選べない）
            if a.smtp_user:
                self.smtp.login(a.smtp_user, a.smtp_password)
        except smtplib.SMTPAuthenticationError as e:
            raise MailError("SMTPの認証に失敗しました。ユーザー名とパスワードを確認してください。") from e
        except (OSError, smtplib.SMTPException) as e:
            raise MailError(f"SMTPサーバーに接続できませんでした: {e}") from e
        return self

    def send(self, msg: EmailMessage) -> None:
        assert self.smtp is not None
        try:
            self.smtp.send_message(msg)
        except smtplib.SMTPException as e:
            raise MailError(f"送信に失敗しました（{msg['To']}）: {e}") from e

    def __exit__(self, *exc):
        if self.smtp is not None:
            try:
                self.smtp.quit()
            except Exception:
                pass


# ---- IMAP: 送信済みフォルダへの保存 ----

_LIST_RE = re.compile(r'\((?P<flags>[^)]*)\) "(?P<delim>[^"]*)" (?P<name>.+)')


def _connect_imap(account: MailAccount) -> imaplib.IMAP4_SSL:
    try:
        imap = imaplib.IMAP4_SSL(account.imap_host, account.imap_port,
                                 ssl_context=ssl.create_default_context())
        imap.login(account.imap_user or account.smtp_user,
                   account.imap_password or account.smtp_password)
        return imap
    except imaplib.IMAP4.error as e:
        raise MailError("IMAPの認証に失敗しました。") from e
    except OSError as e:
        raise MailError(f"IMAPサーバーに接続できませんでした: {e}") from e


def detect_sent_folder(imap: imaplib.IMAP4) -> str:
    typ, data = imap.list()
    if typ != "OK":
        return "INBOX.Sent"
    names = []
    for raw in data or []:
        if not raw:
            continue
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        m = _LIST_RE.match(line)
        if not m:
            continue
        name = m.group("name").strip().strip('"')
        if "\\Sent" in m.group("flags"):
            return name
        names.append(name)
    for cand in ("INBOX.Sent", "Sent", "INBOX/Sent", "Sent Items", "Sent Messages"):
        if cand in names:
            return cand
    return "INBOX.Sent"


def _quote(name: str) -> str:
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_to_sent(account: MailAccount, messages: list[EmailMessage]) -> str:
    """送信済みフォルダに保存し、使ったフォルダ名を返す。"""
    imap = _connect_imap(account)
    try:
        folder = account.sent_folder or detect_sent_folder(imap)
        for msg in messages:
            typ, _ = imap.append(_quote(folder), "(\\Seen)",
                                 imaplib.Time2Internaldate(time.time()), msg.as_bytes())
            if typ != "OK":
                raise MailError(f"送信済みフォルダ（{folder}）への保存に失敗しました。")
        return folder
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def test_connection(account: MailAccount) -> list[str]:
    """SMTP と IMAP の接続確認。結果メッセージのリストを返す。"""
    results = []
    with SmtpSession(account):
        results.append("SMTP: 接続・認証 OK")
    if account.imap_host:
        imap = _connect_imap(account)
        try:
            results.append(f"IMAP: 接続・認証 OK（送信済みフォルダ: {detect_sent_folder(imap)}）")
        finally:
            imap.logout()
    return results
