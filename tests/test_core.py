import os
import stat
import sys
import textwrap
from email import message_from_bytes
from email.header import decode_header, make_header

import pytest
from aiosmtpd.controller import Controller

from mailassist import edition
from mailassist.ai import available_backends
from mailassist.ai.prompts import ComposeRequest, build_compose_prompt, parse_draft
from mailassist.db import Contact, Database, Genre, SentMessage
from mailassist.mail.sender import MailAccount, SmtpSession, build_message


def test_parse_draft_basic():
    d = parse_draft("件名: 素材使用のお願い\n---\nはじめまして。\n\nよろしくお願いいたします。")
    assert d.subject == "素材使用のお願い"
    assert d.body.startswith("はじめまして。")


def test_parse_draft_fullwidth_colon_and_fence():
    d = parse_draft("```\n件名：ご相談\n---\n本文です\n```")
    assert d.subject == "ご相談"
    assert d.body == "本文です"


def test_parse_draft_without_subject():
    d = parse_draft("本文だけ")
    assert d.subject == "" and d.body == "本文だけ"


def test_prompt_contains_contact_specifics():
    req = ComposeRequest(genre=Genre(1, "素材・画像の使用許可", "クレジットを確認"),
                         app_name="TestApp", usage_scope="アイコンを使いたい")
    c = Contact(1, "田中", "t@example.com", notes="猫のイラスト作者")
    p = build_compose_prompt(req, c)
    assert "TestApp" in p and "猫のイラスト作者" in p and "クレジットを確認" in p
    assert "URL" not in p  # 空の項目は出さない


def test_db_roundtrip(tmp_path):
    db = Database(tmp_path / "d.sqlite3")
    assert len(db.list_genres()) >= 5
    cid = db.save_contact(Contact(None, "山田", "y@example.com", notes="メモ"))
    assert db.list_contacts()[0].id == cid
    db.set_setting("signature", "署名")
    assert db.get_setting("signature") == "署名"
    assert db.get_setting("smtp_port") == 465  # 既定値
    db.log_sent(SentMessage(None, cid, "y@example.com", "件名", "本文", "<x@y>", "g"))
    assert db.list_sent()[0].subject == "件名"


def test_edition_switch(monkeypatch):
    monkeypatch.setenv("MAILASSIST_EDITION", "commercial")
    assert not edition.is_personal()
    assert [k for k, _ in available_backends()] == ["api"]
    monkeypatch.setenv("MAILASSIST_EDITION", "personal")
    assert [k for k, _ in available_backends()] == ["cli", "api"]
    monkeypatch.delenv("MAILASSIST_EDITION")
    assert edition.is_personal()  # ソース実行時は cli_backend があるので自分用


class _Handler:
    def __init__(self):
        self.messages = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(envelope)
        return "250 OK"


def test_smtp_individual_send():
    handler = _Handler()
    ctrl = Controller(handler, hostname="127.0.0.1", port=8025)
    ctrl.start()
    try:
        acc = MailAccount("差出人", "info@shirakawaroom.com", "127.0.0.1", 8025, "NONE", "", "")
        with SmtpSession(acc) as s:
            for name, addr in [("A", "a@example.com"), ("B", "b@example.com")]:
                s.send(build_message(acc, name, addr, f"{name}様へのご相談", f"{name}様\n本文"))
    finally:
        ctrl.stop()
    assert len(handler.messages) == 2
    assert handler.messages[0].rcpt_tos == ["a@example.com"]  # 1通に1宛先
    msg = message_from_bytes(handler.messages[1].content)
    assert str(make_header(decode_header(msg["Subject"]))) == "B様へのご相談"
    assert msg["Message-ID"].endswith("@shirakawaroom.com>")
    assert "B様" in msg.get_payload(decode=True).decode("utf-8")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell script")
def test_cli_backend_with_fake_claude(tmp_path):
    from mailassist.ai.cli_backend import CliBackend

    fake = tmp_path / "claude"
    fake.write_text(textwrap.dedent("""\
        #!/bin/sh
        cat > /dev/null
        printf '件名: テスト件名\\n---\\n本文テスト\\n'
    """))
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    out = CliBackend(cli_path=str(fake)).generate("sys", "prompt")
    d = parse_draft(out)
    assert d.subject == "テスト件名" and d.body == "本文テスト"
