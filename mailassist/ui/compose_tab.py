"""メール作成画面：ジャンル選択 → 宛先選択 → AI作成 → 確認・編集 → 個別送信。"""

from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSplitter, QTabWidget, QVBoxLayout,
    QWidget,
)

from ..ai import AIError, create_backend
from ..ai.prompts import (
    SYSTEM_PROMPT, ComposeRequest, build_compose_prompt, find_placeholders, parse_draft,
)
from ..db import Contact, Database, SentMessage
from ..mail.sender import MailError, SmtpSession, build_message, save_to_sent
from .common import Worker, account_from_settings, run_in_background

TONES = ["かなり丁寧", "丁寧", "やわらかめ"]
LENGTHS = ["短め", "標準", "詳しめ"]

# 前回の入力内容として保存する項目
_FORM_FIELDS = ["app_name", "app_summary", "distribution", "platforms", "url",
                "usage_scope", "credit", "extra_instructions"]


class DraftEditor(QWidget):
    """1宛先分の下書き。"""

    def __init__(self, contact: Contact):
        super().__init__()
        self.contact = contact
        self.sent = False
        self.include = QCheckBox("送信する")
        self.include.setChecked(True)
        self.status = QLabel("作成中…")
        self.subject = QLineEdit()
        self.body = QPlainTextEdit()
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMaximumHeight(110)
        self.notes.setStyleSheet("QPlainTextEdit { background: #FFF8E1; color: #5D4037; }")
        self.notes_label = QLabel("AIからの確認事項（メールには含まれません）")
        self.regen = QPushButton("この宛先だけ作り直す")

        top = QHBoxLayout()
        top.addWidget(QLabel(f"宛先: {contact.display()}"))
        top.addStretch()
        top.addWidget(self.status)
        top.addWidget(self.include)

        form = QFormLayout()
        form.addRow("件名", self.subject)

        v = QVBoxLayout(self)
        v.addLayout(top)
        v.addLayout(form)
        v.addWidget(self.body, 1)
        v.addWidget(self.notes_label)
        v.addWidget(self.notes)
        self._show_notes("")
        row = QHBoxLayout()
        row.addWidget(self.regen)
        row.addStretch()
        v.addLayout(row)
        self.set_busy(True)

    def set_busy(self, busy: bool):
        self.subject.setReadOnly(busy)
        self.body.setReadOnly(busy)
        self.regen.setEnabled(not busy and not self.sent)
        if busy:
            self.status.setText("作成中…")

    def _show_notes(self, notes: str):
        self.notes.setPlainText(notes)
        self.notes.setVisible(bool(notes.strip()))
        self.notes_label.setVisible(bool(notes.strip()))

    def set_draft(self, subject: str, body: str, notes: str = ""):
        self.subject.setText(subject)
        self.body.setPlainText(body)
        self._show_notes(notes)
        left = find_placeholders(subject + "\n" + body)
        if left:
            self.status.setText(f"作成済み：{len(left)}か所の空欄を埋めてください")
        elif not subject:
            self.status.setText("作成済み：件名を入力してください")
        else:
            self.status.setText("作成済み（確認・編集してください）")
        self.set_busy(False)

    def set_error(self, msg: str):
        self.status.setText("作成失敗")
        self.body.setPlainText(f"【作成に失敗しました】\n{msg}")
        self.include.setChecked(False)
        self.set_busy(False)

    def mark_sent(self):
        self.sent = True
        self.status.setText("送信済み")
        self.include.setChecked(False)
        self.include.setEnabled(False)
        self.subject.setReadOnly(True)
        self.body.setReadOnly(True)
        self.regen.setEnabled(False)


class ComposeTab(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.editors: list[DraftEditor] = []
        self.pending = 0
        self._workers = set()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setSizes([420, 680])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)
        self.reload_genres()
        self.reload_contacts()
        self._restore_form()

    # ---------- 左：条件入力 ----------
    def _build_left(self) -> QWidget:
        inner = QWidget()
        v = QVBoxLayout(inner)

        g1 = QGroupBox("1. ジャンル")
        f1 = QFormLayout(g1)
        self.genre = QComboBox()
        self.genre_hint = QLabel()
        self.genre_hint.setWordWrap(True)
        self.genre_hint.setStyleSheet("color: gray;")
        self.genre.currentIndexChanged.connect(self._update_genre_hint)
        f1.addRow("依頼の種類", self.genre)
        f1.addRow(self.genre_hint)

        g2 = QGroupBox("2. アプリと依頼の内容")
        f2 = QFormLayout(g2)
        self.app_name = QLineEdit()
        self.app_summary = QPlainTextEdit()
        self.app_summary.setFixedHeight(60)
        self.distribution = QLineEdit()
        self.distribution.setPlaceholderText("例：無料（広告あり）／有料 300円")
        self.platforms = QLineEdit()
        self.platforms.setPlaceholderText("例：Windows / iOS / Android")
        self.url = QLineEdit()
        self.usage_scope = QPlainTextEdit()
        self.usage_scope.setFixedHeight(70)
        self.usage_scope.setPlaceholderText("例：貴サイトで配布されている「○○」のアイコン素材を、アプリ内のボタンに使用したい")
        self.credit = QLineEdit()
        self.credit.setPlaceholderText("例：アプリ内のクレジット画面に「素材：○○様」と表記")
        f2.addRow("アプリ名", self.app_name)
        f2.addRow("概要", self.app_summary)
        f2.addRow("配布・収益", self.distribution)
        f2.addRow("対応環境", self.platforms)
        f2.addRow("URL", self.url)
        f2.addRow("使いたいもの・使い方", self.usage_scope)
        f2.addRow("クレジット表記", self.credit)

        g3 = QGroupBox("3. 文体")
        f3 = QFormLayout(g3)
        self.tone = QComboBox()
        self.tone.addItems(TONES)
        self.tone.setCurrentText("丁寧")
        self.length = QComboBox()
        self.length.addItems(LENGTHS)
        self.length.setCurrentText("標準")
        self.extra_instructions = QPlainTextEdit()
        self.extra_instructions.setFixedHeight(60)
        self.extra_instructions.setPlaceholderText("例：返信期限は設けない。リリース予定は来月と伝える。")
        f3.addRow("丁寧さ", self.tone)
        f3.addRow("長さ", self.length)
        f3.addRow("追加の指示", self.extra_instructions)

        g4 = QGroupBox("4. 宛先（チェックした人それぞれに個別の文面を作成）")
        v4 = QVBoxLayout(g4)
        self.recipients = QListWidget()
        self.recipients.setMinimumHeight(120)
        sel = QHBoxLayout()
        all_btn = QPushButton("全選択")
        none_btn = QPushButton("全解除")
        all_btn.clicked.connect(lambda: self._check_all(True))
        none_btn.clicked.connect(lambda: self._check_all(False))
        sel.addWidget(all_btn)
        sel.addWidget(none_btn)
        sel.addStretch()
        v4.addWidget(self.recipients)
        v4.addLayout(sel)

        self.generate_btn = QPushButton("作成")
        self.generate_btn.setMinimumHeight(36)
        self.generate_btn.clicked.connect(self.generate)

        for g in (g1, g2, g3, g4):
            v.addWidget(g)
        v.addWidget(self.generate_btn)
        v.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        return scroll

    # ---------- 右：下書き ----------
    def _build_right(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.drafts = QTabWidget()
        self.empty_label = QLabel("左側で条件と宛先を選んで「作成」を押すと、ここに宛先ごとの下書きが表示されます。")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.progress = QProgressBar()
        self.progress.setVisible(False)

        self.test_btn = QPushButton("自分宛てにテスト送信（表示中の1通）")
        self.send_btn = QPushButton("チェックしたメールを個別に送信")
        self.send_btn.setMinimumHeight(36)
        self.test_btn.clicked.connect(self.send_test)
        self.send_btn.clicked.connect(self.send_selected)
        row = QHBoxLayout()
        row.addWidget(self.test_btn)
        row.addStretch()
        row.addWidget(self.send_btn)

        v.addWidget(self.empty_label)
        v.addWidget(self.drafts, 1)
        v.addWidget(self.progress)
        v.addLayout(row)
        self._update_buttons()
        return w

    # ---------- データ読み込み ----------
    def reload_genres(self):
        current = self.genre.currentText()
        self.genres = self.db.list_genres()
        self.genre.blockSignals(True)
        self.genre.clear()
        self.genre.addItems([g.name for g in self.genres])
        if current:
            self.genre.setCurrentText(current)
        self.genre.blockSignals(False)
        self._update_genre_hint()

    def reload_contacts(self):
        checked = {self.recipients.item(i).data(Qt.UserRole)
                   for i in range(self.recipients.count())
                   if self.recipients.item(i).checkState() == Qt.Checked}
        self.contacts = {c.id: c for c in self.db.list_contacts()}
        self.recipients.clear()
        for c in self.contacts.values():
            item = QListWidgetItem(c.display())
            item.setData(Qt.UserRole, c.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if c.id in checked else Qt.Unchecked)
            self.recipients.addItem(item)

    def _update_genre_hint(self):
        i = self.genre.currentIndex()
        self.genre_hint.setText(self.genres[i].guidance if 0 <= i < len(self.genres) else "")

    def _check_all(self, on: bool):
        for i in range(self.recipients.count()):
            self.recipients.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)

    def _restore_form(self):
        saved = self.db.get_setting("last_compose") or {}
        for name in _FORM_FIELDS:
            w = getattr(self, name)
            val = saved.get(name, "")
            (w.setPlainText if isinstance(w, QPlainTextEdit) else w.setText)(val)
        if saved.get("genre"):
            self.genre.setCurrentText(saved["genre"])
        if saved.get("tone"):
            self.tone.setCurrentText(saved["tone"])
        if saved.get("length"):
            self.length.setCurrentText(saved["length"])

    def _form_values(self) -> dict:
        vals = {}
        for name in _FORM_FIELDS:
            w = getattr(self, name)
            vals[name] = (w.toPlainText() if isinstance(w, QPlainTextEdit) else w.text()).strip()
        vals.update(genre=self.genre.currentText(), tone=self.tone.currentText(),
                    length=self.length.currentText())
        return vals

    # ---------- 作成 ----------
    def _build_request(self) -> ComposeRequest | None:
        i = self.genre.currentIndex()
        if not (0 <= i < len(self.genres)):
            QMessageBox.warning(self, "入力エラー", "ジャンルを選択してください。")
            return None
        vals = self._form_values()
        self.db.set_setting("last_compose", vals)
        s = self.db.all_settings()
        return ComposeRequest(
            genre=self.genres[i],
            app_name=vals["app_name"], app_summary=vals["app_summary"],
            distribution=vals["distribution"], platforms=vals["platforms"], url=vals["url"],
            usage_scope=vals["usage_scope"], credit=vals["credit"],
            tone=vals["tone"], length=vals["length"],
            extra_instructions=vals["extra_instructions"],
            sender_name=s.get("sender_name") or "", sender_email=s.get("sender_email") or "",
        )

    def generate(self):
        targets = [self.contacts[self.recipients.item(i).data(Qt.UserRole)]
                   for i in range(self.recipients.count())
                   if self.recipients.item(i).checkState() == Qt.Checked]
        if not targets:
            QMessageBox.warning(self, "宛先なし", "宛先にチェックを入れてください（宛先は「宛先」タブで登録できます）。")
            return
        if any(not e.sent for e in self.editors) and self.editors:
            if QMessageBox.question(self, "確認", "表示中の未送信の下書きは破棄されます。作成しますか？") != QMessageBox.Yes:
                return
        if not (self.db.get_setting("sender_name") or "").strip():
            if QMessageBox.question(
                self, "差出人名が未設定です",
                "「設定」→「差出人・署名」で差出人名が設定されていません。\n"
                "このまま作成すると、本文の名前の部分が【要確認：差出人名】になります。\n\n"
                "このまま作成しますか？",
            ) != QMessageBox.Yes:
                return
        req = self._build_request()
        if req is None:
            return
        try:
            backend = create_backend(self.db.all_settings())
        except AIError as e:
            QMessageBox.critical(self, "AI接続エラー", str(e))
            return

        self.drafts.clear()
        self.editors = []
        self.request = req
        self.backend = backend
        for c in targets:
            ed = DraftEditor(c)
            ed.regen.clicked.connect(lambda _=False, e=ed: self._start_generation(e))
            self.editors.append(ed)
            self.drafts.addTab(ed, c.name)
            self._start_generation(ed)
        self._update_buttons()

    def _start_generation(self, ed: DraftEditor):
        ed.set_busy(True)
        self.pending += 1
        self._update_buttons()
        prompt = build_compose_prompt(self.request, ed.contact)
        backend = self.backend

        def job(_progress):
            return parse_draft(backend.generate(SYSTEM_PROMPT, prompt))

        worker = Worker(job)
        worker.signals.finished.connect(lambda d, e=ed, w=worker: self._on_draft(e, d, w))
        worker.signals.error.connect(lambda msg, e=ed, w=worker: self._on_draft_error(e, msg, w))
        self._workers.add(worker)
        run_in_background(worker)

    def _signature(self) -> str:
        sig = (self.db.get_setting("signature") or "").strip()
        return f"\n\n{sig}" if sig else ""

    def _on_draft(self, ed: DraftEditor, draft, worker):
        self._workers.discard(worker)
        self.pending -= 1
        ed.set_draft(draft.subject, draft.body + self._signature(), draft.notes)
        self._update_buttons()

    def _on_draft_error(self, ed: DraftEditor, msg: str, worker):
        self._workers.discard(worker)
        self.pending -= 1
        ed.set_error(msg)
        self._update_buttons()

    def _update_buttons(self):
        has = bool(self.editors)
        self.empty_label.setVisible(not has)
        self.drafts.setVisible(has)
        busy = self.pending > 0
        self.generate_btn.setEnabled(not busy)
        self.generate_btn.setText("作成中…" if busy else "作成")
        self.send_btn.setEnabled(has and not busy)
        self.test_btn.setEnabled(has and not busy)

    # ---------- 送信 ----------
    def _validate_editor(self, ed: DraftEditor) -> str | None:
        if not ed.subject.text().strip():
            return f"{ed.contact.name}：件名が空です。"
        body = ed.body.toPlainText()
        if not body.strip():
            return f"{ed.contact.name}：本文が空です。"
        left = find_placeholders(ed.subject.text() + "\n" + body)
        if left:
            return (f"{ed.contact.name}：埋めていない箇所が残っています。\n\n"
                    + "\n".join(f"・{p}" for p in left)
                    + "\n\n内容を書き換えてから送信してください。")
        return None

    def _account_or_warn(self):
        account = account_from_settings(self.db.all_settings())
        if not account.smtp_host or not account.sender_email:
            QMessageBox.warning(self, "設定が必要です", "メニューの「設定」でメールアカウントを設定してください。")
            return None
        return account

    def send_test(self):
        ed = self.drafts.currentWidget()
        if not isinstance(ed, DraftEditor):
            return
        account = self._account_or_warn()
        if account is None:
            return
        subject = "[テスト] " + ed.subject.text().strip()
        body = f"（テスト送信：本番の宛先は {ed.contact.display()}）\n\n" + ed.body.toPlainText()

        def job(_p):
            msg = build_message(account, account.sender_name, account.sender_email, subject, body)
            with SmtpSession(account) as s:
                s.send(msg)
            return account.sender_email

        worker = Worker(job)
        worker.signals.finished.connect(
            lambda addr: QMessageBox.information(self, "テスト送信", f"{addr} に送信しました。"))
        worker.signals.error.connect(lambda m: QMessageBox.critical(self, "送信エラー", m))
        self._workers.add(worker)
        run_in_background(worker)

    def send_selected(self):
        targets = [e for e in self.editors if e.include.isChecked() and not e.sent]
        if not targets:
            QMessageBox.information(self, "送信", "送信対象（「送信する」にチェック）がありません。")
            return
        for ed in targets:
            err = self._validate_editor(ed)
            if err:
                self.drafts.setCurrentWidget(ed)
                QMessageBox.warning(self, "確認してください", err)
                return
        account = self._account_or_warn()
        if account is None:
            return
        names = "\n".join(f"・{e.contact.display()}" for e in targets)
        if QMessageBox.question(
            self, "送信の確認",
            f"次の {len(targets)} 件を、1通ずつ個別に送信します。\n\n{names}\n\nよろしいですか？",
        ) != QMessageBox.Yes:
            return

        items = [(e, e.contact, e.subject.text().strip(), e.body.toPlainText()) for e in targets]
        interval = int(self.db.get_setting("send_interval_sec") or 0)
        genre = self.genre.currentText()

        def job(progress):
            sent, errors, msgs = [], [], []
            with SmtpSession(account) as session:
                for n, (ed, c, subject, body) in enumerate(items):
                    if n > 0 and interval:
                        time.sleep(interval)
                    msg = build_message(account, c.name, c.email, subject, body)
                    try:
                        session.send(msg)
                    except MailError as e:
                        errors.append(str(e))
                        continue
                    msgs.append(msg)
                    sent.append((ed, c, subject, body, msg["Message-ID"]))
                    progress((n + 1, len(items), ed))
            sent_folder_note = ""
            if account.save_to_sent and account.imap_host and msgs:
                try:
                    folder = save_to_sent(account, msgs)
                    sent_folder_note = f"送信済みフォルダ「{folder}」に保存しました。"
                except MailError as e:
                    sent_folder_note = f"送信済みフォルダへの保存に失敗しました: {e}"
            return sent, errors, sent_folder_note

        self.progress.setRange(0, len(items))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.send_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)

        worker = Worker(job)
        worker.signals.progress.connect(self._on_send_progress)
        worker.signals.finished.connect(lambda res, w=worker: self._on_sent(res, genre, w))
        worker.signals.error.connect(lambda m, w=worker: self._on_send_error(m, w))
        self._workers.add(worker)
        run_in_background(worker)

    def _on_send_progress(self, info):
        done, _total, ed = info
        self.progress.setValue(done)
        ed.mark_sent()

    def _on_sent(self, result, genre: str, worker):
        self._workers.discard(worker)
        sent, errors, note = result
        for _ed, c, subject, body, mid in sent:
            self.db.log_sent(SentMessage(None, c.id, c.email, subject, body, mid, genre,
                                         datetime.now().isoformat(timespec="seconds")))
        self.progress.setVisible(False)
        self._update_buttons()
        text = f"{len(sent)} 件を送信しました。"
        if note:
            text += "\n" + note
        if errors:
            text += "\n\n送信できなかったもの:\n" + "\n".join(errors)
            QMessageBox.warning(self, "送信結果", text)
        else:
            QMessageBox.information(self, "送信結果", text)

    def _on_send_error(self, msg: str, worker):
        self._workers.discard(worker)
        self.progress.setVisible(False)
        self._update_buttons()
        QMessageBox.critical(self, "送信エラー", msg)
