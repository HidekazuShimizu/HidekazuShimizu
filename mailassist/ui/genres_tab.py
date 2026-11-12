"""依頼ジャンル（テンプレート）の編集。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from ..db import Database, Genre


class GenresTab(QWidget):
    changed = Signal()

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show)

        self.name = QLineEdit()
        self.guidance = QPlainTextEdit()
        self.guidance.setPlaceholderText("このジャンルのメールで必ず触れてほしい点・確認事項を書きます。")

        new_btn = QPushButton("新規")
        save_btn = QPushButton("保存")
        del_btn = QPushButton("削除")
        new_btn.clicked.connect(self._new)
        save_btn.clicked.connect(self._save)
        del_btn.clicked.connect(self._delete)

        right = QVBoxLayout()
        right.addWidget(QLabel("ジャンル名"))
        right.addWidget(self.name)
        right.addWidget(QLabel("押さえるポイント（AIへの指示）"))
        right.addWidget(self.guidance)
        row = QHBoxLayout()
        for b in (new_btn, save_btn, del_btn):
            row.addWidget(b)
        row.addStretch()
        right.addLayout(row)

        layout = QHBoxLayout(self)
        layout.addWidget(self.list, 1)
        layout.addLayout(right, 2)
        self.current: Genre | None = None
        self.reload()

    def reload(self):
        self.genres = self.db.list_genres()
        self.list.clear()
        self.list.addItems([g.name for g in self.genres])
        if self.genres:
            self.list.setCurrentRow(0)

    def _show(self, row: int):
        if 0 <= row < len(self.genres):
            self.current = self.genres[row]
            self.name.setText(self.current.name)
            self.guidance.setPlainText(self.current.guidance)

    def _new(self):
        self.current = Genre(None, "", "", sort_order=len(self.genres))
        self.list.clearSelection()
        self.name.clear()
        self.guidance.clear()
        self.name.setFocus()

    def _save(self):
        if self.current is None or not self.name.text().strip():
            QMessageBox.warning(self, "入力エラー", "ジャンル名を入力してください。")
            return
        self.current.name = self.name.text().strip()
        self.current.guidance = self.guidance.toPlainText().strip()
        self.db.save_genre(self.current)
        self.reload()
        self.changed.emit()

    def _delete(self):
        if self.current is None or self.current.id is None:
            return
        if QMessageBox.question(self, "確認", f"「{self.current.name}」を削除しますか？") == QMessageBox.Yes:
            self.db.delete_genre(self.current.id)
            self.current = None
            self.reload()
            self.changed.emit()
