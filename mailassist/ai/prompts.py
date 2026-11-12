"""メール文面生成用のプロンプト組み立てと出力の解析。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..db import Contact, Genre

SYSTEM_PROMPT = """\
あなたは、個人のアプリ開発者に代わって日本語のビジネスメールを書くアシスタントです。
開発者が、権利者や関係者に許可取り・依頼・相談の連絡をするためのメールを作成します。

方針:
- 相手との関係性に合った敬語を使い、丁寧だが回りくどくない文面にする。
- 冒頭で名乗り、用件を早めに示す。相手が判断に必要な情報（何を・どこで・どの範囲で使うか）を具体的に書く。
- 相手が返信しやすいよう、確認したい事項は箇条書きなどで整理する。
- 相手が断りやすい配慮（ご都合が合わない場合はお知らせください 等）を入れ、圧をかけない。
- 入力にない事実（実績、数値、日付、約束、金額）を作らない。不足している情報は【要確認：○○】の形で本文に残す。
- 宛先ごとのメモがあれば、その相手に合わせた一文（作品への言及など）を自然に入れる。ただしメモにないことで相手を褒めたり、知り合いであるかのように書いたりしない。
- 署名は本文に含めない（アプリ側で付け足す）。

出力形式（この形式以外の文章は出力しない）:
件名: <件名>
---
<本文>
"""


@dataclass
class ComposeRequest:
    genre: Genre
    app_name: str = ""
    app_summary: str = ""
    distribution: str = ""  # 無料 / 有料 / 広告あり など
    platforms: str = ""
    usage_scope: str = ""  # 使いたいもの・使い方
    credit: str = ""  # クレジット表記の案
    url: str = ""
    tone: str = "丁寧"
    length: str = "標準"
    extra_instructions: str = ""
    sender_name: str = ""
    sender_email: str = ""


@dataclass
class ReplyRequest:
    """返信作成用（フェーズ2で使用）。"""
    original_subject: str
    original_body: str
    their_reply: str
    instructions: str = ""
    sender_name: str = ""
    history: list[str] = field(default_factory=list)


def _line(label: str, value: str) -> str:
    value = (value or "").strip()
    return f"- {label}: {value}\n" if value else ""


def build_compose_prompt(req: ComposeRequest, contact: Contact) -> str:
    length_hint = {
        "短め": "本文は300字程度に収める。",
        "標準": "本文は400〜700字程度。",
        "詳しめ": "本文は700〜1000字程度で、背景も含めて丁寧に説明する。",
    }.get(req.length, "")
    tone_hint = {
        "かなり丁寧": "最上級の丁寧さ（初めての企業・公的機関向け）。",
        "丁寧": "標準的なビジネスメールの丁寧さ。",
        "やわらかめ": "丁寧語は保ちつつ、やわらかく親しみのある書き方（個人クリエイター向け）。",
    }.get(req.tone, "")

    parts = [
        "以下の情報をもとに、この宛先1名に送るメールを作成してください。\n",
        f"## 依頼のジャンル\n{req.genre.name}\n",
        f"## このジャンルで押さえる点\n{req.genre.guidance}\n" if req.genre.guidance else "",
        "## 差出人\n",
        _line("名前", req.sender_name),
        _line("メールアドレス", req.sender_email),
        "\n## アプリの情報\n",
        _line("アプリ名", req.app_name),
        _line("概要", req.app_summary),
        _line("配布形態・収益化", req.distribution),
        _line("対応プラットフォーム", req.platforms),
        _line("URL", req.url),
        "\n## 依頼内容\n",
        _line("使いたいもの・使い方", req.usage_scope),
        _line("クレジット表記の案", req.credit),
        "\n## 宛先\n",
        _line("名前", f"{contact.name} {contact.honorific}".strip()),
        _line("所属", contact.organization),
        _line("関係性", contact.relationship),
        _line("この宛先についてのメモ", contact.notes),
        "\n## 文体\n",
        f"- {tone_hint}\n" if tone_hint else "",
        f"- {length_hint}\n" if length_hint else "",
    ]
    if req.extra_instructions.strip():
        parts.append(f"\n## 追加の指示\n{req.extra_instructions.strip()}\n")
    return "".join(parts)


def build_reply_prompt(req: ReplyRequest) -> str:
    parts = [
        "以下のやり取りに対する返信メールを作成してください。"
        "相手の回答（許可・条件付き許可・お断り・質問など）を正確に読み取り、それに沿った返信にすること。"
        "お断りの場合は丁寧にお礼を述べて引き下がること。条件がある場合は条件を復唱して確認すること。\n\n",
        f"## こちらが送ったメール\n件名: {req.original_subject}\n{req.original_body}\n\n",
        f"## 相手からの返信\n{req.their_reply}\n",
    ]
    if req.instructions.strip():
        parts.append(f"\n## 返信の方針（差出人より）\n{req.instructions.strip()}\n")
    return "".join(parts)


@dataclass
class Draft:
    subject: str
    body: str


_SUBJECT_RE = re.compile(r"^\s*件名\s*[:：]\s*(.+?)\s*$", re.MULTILINE)


def parse_draft(text: str) -> Draft:
    text = text.strip()
    # ```で囲まれて返ってきた場合に外す
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    m = _SUBJECT_RE.search(text)
    if not m:
        return Draft(subject="", body=text)
    subject = m.group(1)
    rest = text[m.end():]
    rest = re.sub(r"^\s*-{3,}\s*\n", "", rest.lstrip("\n"), count=1)
    return Draft(subject=subject, body=rest.strip())
