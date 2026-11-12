"""設定画面（メールアカウント・署名・AI 接続）。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from .. import edition
from ..ai import available_backends
from ..ai.api_backend import MODELS
from ..db import Database
from ..mail.sender import test_connection
from ..secrets_store import (
    ANTHROPIC_API_KEY, IMAP_PASSWORD, SMTP_PASSWORD, get_secret, set_secret,
)
from .common import Worker, account_from_settings, run_in_background


def _password_field(value: str) -> QLineEdit:
    f = QLineEdit(value)
    f.setEchoMode(QLineEdit.Password)
    return f


class SettingsDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("設定")
        self.setMinimumWidth(560)
        s = db.all_settings()

        tabs = QTabWidget()
        tabs.addTab(self._mail_tab(s), "メールアカウント")
        tabs.addTab(self._signature_tab(s), "差出人・署名")
        tabs.addTab(self._ai_tab(s), "AI接続")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ---- tabs ----
    def _mail_tab(self, s: dict) -> QWidget:
        w = QWidget()
        hint = QLabel(
            "エックスサーバーの場合：サーバーパネル →「メールアカウント設定」→「メールソフト設定」に"
            "表示されるサーバー名（sv○○○○.xserver.jp）を入力します。"
            "ユーザー名はメールアドレス、パスワードはメールアカウントのパスワードです。"
        )
        hint.setWordWrap(True)

        self.smtp_host = QLineEdit(s["smtp_host"])
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(int(s["smtp_port"]))
        self.smtp_security = QComboBox()
        self.smtp_security.addItems(["SSL", "STARTTLS"])
        self.smtp_security.setCurrentText(s["smtp_security"])
        self.smtp_user = QLineEdit(s["smtp_user"])
        self.smtp_pw = _password_field(get_secret(SMTP_PASSWORD))

        smtp = QGroupBox("送信（SMTP）")
        f1 = QFormLayout(smtp)
        f1.addRow("サーバー", self.smtp_host)
        f1.addRow("ポート", self.smtp_port)
        f1.addRow("暗号化", self.smtp_security)
        f1.addRow("ユーザー名", self.smtp_user)
        f1.addRow("パスワード", self.smtp_pw)

        self.imap_host = QLineEdit(s["imap_host"])
        self.imap_port = QSpinBox()
        self.imap_port.setRange(1, 65535)
        self.imap_port.setValue(int(s["imap_port"]))
        self.imap_user = QLineEdit(s["imap_user"])
        self.imap_pw = _password_field(get_secret(IMAP_PASSWORD))
        self.imap_pw.setPlaceholderText("空欄ならSMTPと同じパスワードを使用")
        self.save_to_sent = QCheckBox("送ったメールを「送信済み」フォルダにも保存する（Thunderbirdにも表示されます）")
        self.save_to_sent.setChecked(bool(s["save_to_sent"]))
        self.sent_folder = QLineEdit(s["sent_folder"])
        self.sent_folder.setPlaceholderText("空欄なら自動検出")

        imap = QGroupBox("受信（IMAP）")
        f2 = QFormLayout(imap)
        f2.addRow("サーバー", self.imap_host)
        f2.addRow("ポート", self.imap_port)
        f2.addRow("ユーザー名", self.imap_user)
        f2.addRow("パスワード", self.imap_pw)
        f2.addRow(self.save_to_sent)
        f2.addRow("送信済みフォルダ名", self.sent_folder)

        self.interval = QSpinBox()
        self.interval.setRange(0, 600)
        self.interval.setSuffix(" 秒")
        self.interval.setValue(int(s["send_interval_sec"]))
        misc = QFormLayout()
        misc.addRow("複数送信時の間隔", self.interval)

        test_btn = QPushButton("接続テスト")
        test_btn.clicked.connect(self._test_mail)

        v = QVBoxLayout(w)
        v.addWidget(hint)
        v.addWidget(smtp)
        v.addWidget(imap)
        v.addLayout(misc)
        v.addWidget(test_btn)
        v.addStretch()
        return w

    def _signature_tab(self, s: dict) -> QWidget:
        w = QWidget()
        self.sender_name = QLineEdit(s["sender_name"])
        self.sender_email = QLineEdit(s["sender_email"])
        self.signature = QPlainTextEdit(s["signature"])
        self.signature.setPlaceholderText(
            "--\n山田 太郎\nShirakawa Room\nMail: info@shirakawaroom.com\nWeb: https://shirakawaroom.com"
        )
        f = QFormLayout(w)
        f.addRow("差出人名", self.sender_name)
        f.addRow("差出人アドレス", self.sender_email)
        f.addRow("署名", self.signature)
        return w

    def _ai_tab(self, s: dict) -> QWidget:
        w = QWidget()
        self.backend = QComboBox()
        for key, label in available_backends():
            self.backend.addItem(label, key)
        idx = self.backend.findData(s["ai_backend"])
        self.backend.setCurrentIndex(idx if idx >= 0 else 0)

        self.api_key = _password_field(get_secret(ANTHROPIC_API_KEY))
        self.api_key.setPlaceholderText("sk-ant-...")
        self.model = QComboBox()
        for mid, label in MODELS:
            self.model.addItem(label, mid)
        mi = self.model.findData(s["ai_model"])
        self.model.setCurrentIndex(mi if mi >= 0 else 0)

        f = QFormLayout(w)
        f.addRow("接続方法", self.backend)

        self.cli_box = None
        if edition.is_personal():
            from ..ai.cli_backend import CLI_MODELS

            self.cli_box = QGroupBox("Claude Code 経由（自分用）")
            cf = QFormLayout(self.cli_box)
            self.cli_path = QLineEdit(s["cli_path"])
            self.cli_path.setPlaceholderText("空欄なら自動検出（例：C:\\Users\\you\\AppData\\Roaming\\npm\\claude.cmd）")
            self.cli_model = QComboBox()
            for mid, label in CLI_MODELS:
                self.cli_model.addItem(label, mid)
            ci = self.cli_model.findData(s.get("cli_model") or "opus")
            self.cli_model.setCurrentIndex(ci if ci >= 0 else 0)
            cf.addRow("claude の場所", self.cli_path)
            cf.addRow("モデル", self.cli_model)
            note = QLabel("PCにインストールしてログイン済みの Claude Code を使います。今のプランの利用枠で動作します。")
            note.setWordWrap(True)
            cf.addRow(note)
            f.addRow(self.cli_box)

        api_box = QGroupBox("Claude API")
        af = QFormLayout(api_box)
        af.addRow("APIキー", self.api_key)
        af.addRow("モデル", self.model)
        note = QLabel("APIキーは https://console.anthropic.com で発行できます（従量課金）。"
                      "キーはWindowsの資格情報マネージャーに保存されます。")
        note.setWordWrap(True)
        af.addRow(note)
        f.addRow(api_box)
        return w

    # ---- actions ----
    def _collect(self) -> dict:
        s = {
            "smtp_host": self.smtp_host.text().strip(),
            "smtp_port": self.smtp_port.value(),
            "smtp_security": self.smtp_security.currentText(),
            "smtp_user": self.smtp_user.text().strip(),
            "imap_host": self.imap_host.text().strip(),
            "imap_port": self.imap_port.value(),
            "imap_user": self.imap_user.text().strip(),
            "save_to_sent": self.save_to_sent.isChecked(),
            "sent_folder": self.sent_folder.text().strip(),
            "send_interval_sec": self.interval.value(),
            "sender_name": self.sender_name.text().strip(),
            "sender_email": self.sender_email.text().strip(),
            "signature": self.signature.toPlainText().rstrip(),
            "ai_backend": self.backend.currentData(),
            "ai_model": self.model.currentData(),
        }
        if self.cli_box is not None:
            s["cli_path"] = self.cli_path.text().strip()
            s["cli_model"] = self.cli_model.currentData()
        return s

    def _store_secrets(self):
        set_secret(SMTP_PASSWORD, self.smtp_pw.text())
        set_secret(IMAP_PASSWORD, self.imap_pw.text())
        set_secret(ANTHROPIC_API_KEY, self.api_key.text().strip())

    def _save(self):
        try:
            self._store_secrets()
        except RuntimeError as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        for k, v in self._collect().items():
            self.db.set_setting(k, v)
        self.accept()

    def _test_mail(self):
        try:
            self._store_secrets()
        except RuntimeError as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        account = account_from_settings({**self.db.all_settings(), **self._collect()})
        worker = Worker(lambda _p: test_connection(account))
        worker.signals.finished.connect(
            lambda res: QMessageBox.information(self, "接続テスト", "\n".join(res)))
        worker.signals.error.connect(lambda msg: QMessageBox.critical(self, "接続テスト失敗", msg))
        run_in_background(worker)
        self._worker = worker  # GC 防止
