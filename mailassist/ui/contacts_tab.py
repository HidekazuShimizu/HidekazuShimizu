"""宛先の登録・編集。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QAbstractItemView, QHeaderView,
)

from ..db import Contact, Database

RELATIONSHIPS = ["初めて連絡", "以前やり取りあり", "知り合い・取引あり"]
HONORIFICS = ["様", "さん", "御中", "先生", "（なし）"]


class ContactDialog(QDialog):
    def __init__(self, parent=None, contact: Contact | None = None):
        super().__init__(parent)
        self.setWindowTitle("宛先の編集" if contact else "宛先の追加")
        self.setMinimumWidth(460)
        self.contact = contact or Contact(None, "", "")

        self.name = QLineEdit(self.contact.name)
        self.email = QLineEdit(self.contact.email)
        self.org = QLineEdit(self.contact.organization)
        self.honorific = QComboBox()
        self.honorific.setEditable(True)
        self.honorific.addItems(HONORIFICS)
        self.honorific.setCurrentText(self.contact.honorific or "（なし）")
        self.relationship = QComboBox()
        self.relationship.setEditable(True)
        self.relationship.addItems(RELATIONSHIPS)
        self.relationship.setCurrentText(self.contact.relationship)
        self.notes = QPlainTextEdit(self.contact.notes)
        self.notes.setPlaceholderText(
            "例：○○というイラストシリーズの作者。利用規約で商用利用は要相談と記載あり。"
        )

        form = QFormLayout()
        form.addRow("名前 *", self.name)
        form.addRow("メールアドレス *", self.email)
        form.addRow("所属・会社名", self.org)
        form.addRow("敬称", self.honorific)
        form.addRow("関係性", self.relationship)
        form.addRow("メモ（文面の個別化に使います）", self.notes)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _accept(self):
        name, email = self.name.text().strip(), self.email.text().strip()
        if not name or "@" not in email:
            QMessageBox.warning(self, "入力エラー", "名前と正しいメールアドレスを入力してください。")
            return
        h = self.honorific.currentText().strip()
        self.contact.name = name
        self.contact.email = email
        self.contact.organization = self.org.text().strip()
        self.contact.honorific = "" if h == "（なし）" else h
        self.contact.relationship = self.relationship.currentText().strip()
        self.contact.notes = self.notes.toPlainText().strip()
        self.accept()


class ContactsTab(QWidget):
    changed = Signal()

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["名前", "所属", "メールアドレス", "関係性", "メモ"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self.edit_selected)

        add = QPushButton("追加")
        edit = QPushButton("編集")
        delete = QPushButton("削除")
        add.clicked.connect(self.add)
        edit.clicked.connect(self.edit_selected)
        delete.clicked.connect(self.delete_selected)

        btns = QHBoxLayout()
        for b in (add, edit, delete):
            btns.addWidget(b)
        btns.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(btns)
        layout.addWidget(self.table)
        self.reload()

    def reload(self):
        self.contacts = self.db.list_contacts()
        self.table.setRowCount(len(self.contacts))
        for r, c in enumerate(self.contacts):
            for col, val in enumerate([c.name, c.organization, c.email, c.relationship,
                                       c.notes.replace("\n", " ")]):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, c.id)
                self.table.setItem(r, col, item)
        self.table.resizeColumnsToContents()

    def _selected(self) -> Contact | None:
        row = self.table.currentRow()
        return self.contacts[row] if 0 <= row < len(self.contacts) else None

    def add(self):
        dlg = ContactDialog(self)
        if dlg.exec():
            self.db.save_contact(dlg.contact)
            self.reload()
            self.changed.emit()

    def edit_selected(self):
        c = self._selected()
        if not c:
            return
        dlg = ContactDialog(self, c)
        if dlg.exec():
            self.db.save_contact(dlg.contact)
            self.reload()
            self.changed.emit()

    def delete_selected(self):
        c = self._selected()
        if not c:
            return
        if QMessageBox.question(self, "確認", f"{c.name} を削除しますか？") == QMessageBox.Yes:
            self.db.delete_contact(c.id)
            self.reload()
            self.changed.emit()
