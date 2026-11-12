"""UI 共通部品：バックグラウンド処理とアカウント情報の組み立て。"""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from ..mail.sender import MailAccount
from ..secrets_store import IMAP_PASSWORD, SMTP_PASSWORD, get_secret


class WorkerSignals(QObject):
    progress = Signal(object)
    finished = Signal(object)
    error = Signal(str)


class Worker(QRunnable):
    """fn(progress_callback, *args) を別スレッドで実行する。"""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(self.signals.progress.emit, *self.args, **self.kwargs)
        except Exception as e:  # noqa: BLE001 - UIに表示するため全て捕まえる
            msg = str(e) or e.__class__.__name__
            if not getattr(e, "__module__", "").startswith("mailassist"):
                msg += "\n\n" + traceback.format_exc(limit=3)
            self.signals.error.emit(msg)
        else:
            self.signals.finished.emit(result)


def run_in_background(worker: Worker) -> None:
    QThreadPool.globalInstance().start(worker)


def account_from_settings(s: dict) -> MailAccount:
    smtp_pw = get_secret(SMTP_PASSWORD)
    return MailAccount(
        sender_name=s.get("sender_name") or "",
        sender_email=s.get("sender_email") or "",
        smtp_host=s.get("smtp_host") or "",
        smtp_port=int(s.get("smtp_port") or 465),
        smtp_security=s.get("smtp_security") or "SSL",
        smtp_user=s.get("smtp_user") or "",
        smtp_password=smtp_pw,
        imap_host=s.get("imap_host") or "",
        imap_port=int(s.get("imap_port") or 993),
        imap_user=s.get("imap_user") or "",
        imap_password=get_secret(IMAP_PASSWORD) or smtp_pw,
        save_to_sent=bool(s.get("save_to_sent")),
        sent_folder=s.get("sent_folder") or "",
    )
