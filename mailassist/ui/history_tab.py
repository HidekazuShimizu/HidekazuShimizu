"""送信履歴の表示。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QPlainTextEdit, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..db import Database


class HistoryTab(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["送信日時", "宛先", "ジャンル", "件名"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.currentCellChanged.connect(lambda r, *_: self._show(r))
        self.body = QPlainTextEdit()
        self.body.setReadOnly(True)
        refresh = QPushButton("更新")
        refresh.clicked.connect(self.reload)

        split = QSplitter(Qt.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.body)
        v = QVBoxLayout(self)
        v.addWidget(refresh, alignment=Qt.AlignLeft)
        v.addWidget(split)
        self.reload()

    def reload(self):
        self.items = self.db.list_sent()
        self.table.setRowCount(len(self.items))
        for r, m in enumerate(self.items):
            for c, val in enumerate([m.sent_at.replace("T", " "), m.to_addr, m.genre, m.subject]):
                self.table.setItem(r, c, QTableWidgetItem(val))
        self.table.resizeColumnsToContents()
        self.body.clear()

    def _show(self, row: int):
        if 0 <= row < len(self.items):
            m = self.items[row]
            self.body.setPlainText(f"件名: {m.subject}\n宛先: {m.to_addr}\n\n{m.body}")
