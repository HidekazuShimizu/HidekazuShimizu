"""画面を表示せずに「作成 → 個別送信」の流れを通しで確認する。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from aiosmtpd.controller import Controller
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QMessageBox

from mailassist.ai.base import AIBackend
from mailassist.db import Contact, Database
from mailassist.ui import compose_tab
from mailassist.ui.main_window import MainWindow


class FakeBackend(AIBackend):
    def generate(self, system, prompt):
        name = "田中" if "田中" in prompt else "佐藤"
        return f"件名: {name}様へ素材使用のお願い\n---\n{name}様\n\nはじめまして。"


class Handler:
    def __init__(self):
        self.envelopes = []

    async def handle_DATA(self, server, session, envelope):
        self.envelopes.append(envelope)
        return "250 OK"


def wait_until(app, cond, timeout_ms=10000):
    import time
    end = time.time() + timeout_ms / 1000
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        QThreadPool.globalInstance().waitForDone(20)
    return False


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_generate_and_send(app, tmp_path, monkeypatch):
    db = Database(tmp_path / "d.sqlite3")
    db.save_contact(Contact(None, "田中", "tanaka@example.com", notes="猫の絵"))
    db.save_contact(Contact(None, "佐藤", "sato@example.com"))
    for k, v in dict(smtp_host="127.0.0.1", smtp_port=8026, smtp_security="NONE",
                     smtp_user="", sender_name="テスト", sender_email="info@shirakawaroom.com",
                     signature="--\n署名", send_interval_sec=0, save_to_sent=False).items():
        db.set_setting(k, v)

    monkeypatch.setattr(compose_tab, "create_backend", lambda s: FakeBackend())
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    shown = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))

    win = MainWindow(db)
    c = win.compose
    c.app_name.setText("テストアプリ")
    c._check_all(True)
    c.generate()
    assert wait_until(app, lambda: c.pending == 0 and len(c.editors) == 2)
    eds = {e.contact.name: e for e in c.editors}
    assert eds["田中"].subject.text() == "田中様へ素材使用のお願い"
    assert eds["佐藤"].body.toPlainText().endswith("--\n署名")

    eds["佐藤"].include.setChecked(False)  # 1件だけ送る
    handler = Handler()
    ctrl = Controller(handler, hostname="127.0.0.1", port=8026)
    ctrl.start()
    try:
        c.send_selected()
        assert wait_until(app, lambda: len(db.list_sent()) == 1)
    finally:
        ctrl.stop()
    assert [e.rcpt_tos for e in handler.envelopes] == [["tanaka@example.com"]]
    assert eds["田中"].sent and not eds["佐藤"].sent
    assert any("1 件を送信しました" in s for s in shown)
    # 前回の入力内容が保存されている
    assert db.get_setting("last_compose")["app_name"] == "テストアプリ"


def test_blocks_unresolved_placeholders(app, tmp_path, monkeypatch):
    db = Database(tmp_path / "d.sqlite3")
    db.save_contact(Contact(None, "田中", "tanaka@example.com"))
    db.set_setting("smtp_host", "127.0.0.1")

    class PlaceholderBackend(AIBackend):
        def generate(self, system, prompt):
            return "件名: ご相談\n---\nリリース日は【要確認：日付】です。"

    monkeypatch.setattr(compose_tab, "create_backend", lambda s: PlaceholderBackend())
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    win = MainWindow(db)
    c = win.compose
    c._check_all(True)
    c.generate()
    assert wait_until(app, lambda: c.pending == 0 and c.editors)
    c.send_selected()
    assert warned and "要確認" in warned[0]
    assert db.list_sent() == []
