"""メインウィンドウ。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget

from .. import APP_NAME, __version__, edition
from ..db import Database
from ..resources import icon_path
from .compose_tab import ComposeTab
from .contacts_tab import ContactsTab
from .genres_tab import GenresTab
from .history_tab import HistoryTab
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        suffix = "（自分用）" if edition.is_personal() else ""
        self.setWindowTitle(f"{APP_NAME}{suffix}")
        self.resize(1200, 800)

        self.compose = ComposeTab(db)
        self.contacts = ContactsTab(db)
        self.genres = GenresTab(db)
        self.history = HistoryTab(db)
        self.contacts.changed.connect(self.compose.reload_contacts)
        self.genres.changed.connect(self.compose.reload_genres)

        tabs = QTabWidget()
        tabs.addTab(self.compose, "メール作成")
        tabs.addTab(self.contacts, "宛先")
        tabs.addTab(self.genres, "ジャンル")
        tabs.addTab(self.history, "送信履歴")
        tabs.currentChanged.connect(lambda i: self.history.reload() if tabs.widget(i) is self.history else None)
        self.setCentralWidget(tabs)

        menu = self.menuBar()
        settings_action = QAction("設定", self)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)
        about_action = QAction("このアプリについて", self)
        about_action.triggered.connect(self.about)
        menu.addAction(about_action)

        if not db.get_setting("smtp_host"):
            self.statusBar().showMessage("はじめに「設定」でメールアカウントとAI接続を設定してください。")

    def open_settings(self):
        if SettingsDialog(self.db, self).exec():
            self.statusBar().showMessage("設定を保存しました。", 5000)

    def about(self):
        box = QMessageBox(self)
        box.setWindowTitle("このアプリについて")
        box.setIconPixmap(QPixmap(str(icon_path())).scaled(
            96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        box.setText(f"<b>{APP_NAME}</b><br>許可取り・依頼メールの作成アシスタント")
        box.setInformativeText(
            f"バージョン {__version__}　エディション: {'自分用' if edition.is_personal() else '標準'}\n\n"
            "メール本文の作成のため、入力内容はAI（Claude）に送信されます。")
        box.exec()
