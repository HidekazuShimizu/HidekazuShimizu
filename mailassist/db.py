"""SQLite によるデータ保存（宛先・ジャンル・設定・送信履歴）。"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import APP_ID


def default_data_dir() -> Path:
    base = os.environ.get("MAILASSIST_DATA_DIR")
    if base:
        return Path(base)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_ID
    return Path.home() / f".{APP_ID.lower()}"


SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    organization TEXT DEFAULT '',
    honorific TEXT DEFAULT '様',
    relationship TEXT DEFAULT '初めて連絡',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    guidance TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    to_addr TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    message_id TEXT NOT NULL,
    genre TEXT DEFAULT '',
    sent_at TEXT NOT NULL
);
"""

DEFAULT_GENRES: list[tuple[str, str]] = [
    (
        "素材・画像の使用許可",
        "使用したい素材（画像・イラスト・アイコン・写真など）を具体的に特定する。"
        "使用箇所（アプリ内のどこで使うか）、使用範囲（商用/非商用、配布形態）、"
        "加工の有無、クレジット表記の方法、使用料の有無について確認する。",
    ),
    (
        "楽曲・音源の使用許可",
        "使用したい楽曲・効果音を特定する。BGM/効果音などの用途、ループ再生や編集の有無、"
        "配信プラットフォーム、クレジット表記、使用料・JASRAC等の管理状況を確認する。",
    ),
    (
        "名称・商標・ロゴの使用確認",
        "使用したい名称・ロゴ・商標と、その使い方（アプリ名、説明文、連携表記など）を明確にする。"
        "誤認を招かない表記方法や、公式ガイドラインの有無を確認する。",
    ),
    (
        "作品・キャラクターの二次利用許可",
        "対象の作品・キャラクターを特定し、二次創作・ファンアプリとしての利用可否、"
        "収益化の可否、ガイドラインの有無、権利表記の方法を確認する。",
    ),
    (
        "データ・APIの利用許可",
        "利用したいデータやAPIを特定し、利用目的、アクセス頻度、データの保存・再配布の有無、"
        "商用利用の可否、出典表記を確認する。",
    ),
    (
        "掲載・紹介のお願い",
        "アプリの紹介・掲載（Webサイト、SNS、メディア等）をお願いする。"
        "相手のメリット、紹介してほしい内容、提供できる素材（スクリーンショット、紹介文）を伝える。",
    ),
    (
        "協業・提携のご相談",
        "協業・提携の提案をする。目的、相手にとってのメリット、想定する役割分担、"
        "次のステップ（オンライン面談の打診など）を簡潔に伝える。",
    ),
    (
        "その他（自由記述）",
        "追加の指示欄に書かれた内容に従って依頼文を作成する。",
    ),
]

DEFAULT_SETTINGS: dict[str, object] = {
    "sender_name": "",
    "sender_email": "info@shirakawaroom.com",
    "signature": "",
    "smtp_host": "",
    "smtp_port": 465,
    "smtp_security": "SSL",  # SSL / STARTTLS
    "smtp_user": "info@shirakawaroom.com",
    "imap_host": "",
    "imap_port": 993,
    "imap_user": "info@shirakawaroom.com",
    "save_to_sent": True,
    "sent_folder": "",  # 空なら自動検出
    "send_interval_sec": 5,
    "ai_backend": "cli",  # cli（Claude Code 経由・自分用版のみ）/ api
    "ai_model": "claude-opus-5-5",
    "cli_path": "",
    "cli_model": "opus",
    "last_compose": {},
}


@dataclass
class Contact:
    id: int | None
    name: str
    email: str
    organization: str = ""
    honorific: str = "様"
    relationship: str = "初めて連絡"
    notes: str = ""

    def display(self) -> str:
        org = f"（{self.organization}）" if self.organization else ""
        return f"{self.name}{org} <{self.email}>"


@dataclass
class Genre:
    id: int | None
    name: str
    guidance: str = ""
    sort_order: int = 0


@dataclass
class SentMessage:
    id: int | None
    contact_id: int | None
    to_addr: str
    subject: str
    body: str
    message_id: str
    genre: str = ""
    sent_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class Database:
    def __init__(self, path: Path | str | None = None):
        if path is None:
            d = default_data_dir()
            d.mkdir(parents=True, exist_ok=True)
            path = d / "data.sqlite3"
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._seed()

    def _seed(self) -> None:
        cur = self.conn.execute("SELECT COUNT(*) FROM genres")
        if cur.fetchone()[0] == 0:
            self.conn.executemany(
                "INSERT INTO genres(name, guidance, sort_order) VALUES (?,?,?)",
                [(n, g, i) for i, (n, g) in enumerate(DEFAULT_GENRES)],
            )
            self.conn.commit()

    # ---- settings ----
    def get_setting(self, key: str):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if row is None:
            return DEFAULT_SETTINGS.get(key)
        return json.loads(row["value"])

    def set_setting(self, key: str, value) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        self.conn.commit()

    def all_settings(self) -> dict:
        return {k: self.get_setting(k) for k in DEFAULT_SETTINGS}

    # ---- contacts ----
    def list_contacts(self) -> list[Contact]:
        rows = self.conn.execute(
            "SELECT id, name, email, organization, honorific, relationship, notes "
            "FROM contacts ORDER BY name"
        ).fetchall()
        return [Contact(**dict(r)) for r in rows]

    def save_contact(self, c: Contact) -> int:
        if c.id is None:
            cur = self.conn.execute(
                "INSERT INTO contacts(name, email, organization, honorific, relationship, notes, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (c.name, c.email, c.organization, c.honorific, c.relationship, c.notes,
                 datetime.now().isoformat(timespec="seconds")),
            )
            c.id = cur.lastrowid
        else:
            self.conn.execute(
                "UPDATE contacts SET name=?, email=?, organization=?, honorific=?, relationship=?, notes=? "
                "WHERE id=?",
                (c.name, c.email, c.organization, c.honorific, c.relationship, c.notes, c.id),
            )
        self.conn.commit()
        return c.id

    def delete_contact(self, contact_id: int) -> None:
        self.conn.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        self.conn.commit()

    # ---- genres ----
    def list_genres(self) -> list[Genre]:
        rows = self.conn.execute(
            "SELECT id, name, guidance, sort_order FROM genres ORDER BY sort_order, id"
        ).fetchall()
        return [Genre(**dict(r)) for r in rows]

    def save_genre(self, g: Genre) -> int:
        if g.id is None:
            cur = self.conn.execute(
                "INSERT INTO genres(name, guidance, sort_order) VALUES (?,?,?)",
                (g.name, g.guidance, g.sort_order),
            )
            g.id = cur.lastrowid
        else:
            self.conn.execute(
                "UPDATE genres SET name=?, guidance=?, sort_order=? WHERE id=?",
                (g.name, g.guidance, g.sort_order, g.id),
            )
        self.conn.commit()
        return g.id

    def delete_genre(self, genre_id: int) -> None:
        self.conn.execute("DELETE FROM genres WHERE id=?", (genre_id,))
        self.conn.commit()

    # ---- sent log ----
    def log_sent(self, m: SentMessage) -> int:
        cur = self.conn.execute(
            "INSERT INTO sent_messages(contact_id, to_addr, subject, body, message_id, genre, sent_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (m.contact_id, m.to_addr, m.subject, m.body, m.message_id, m.genre, m.sent_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_sent(self, limit: int = 200) -> list[SentMessage]:
        rows = self.conn.execute(
            "SELECT id, contact_id, to_addr, subject, body, message_id, genre, sent_at "
            "FROM sent_messages ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [SentMessage(**dict(r)) for r in rows]
