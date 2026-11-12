"""Claude Code（CLI）経由の生成。自分用版のみ。

PC にインストール・ログイン済みの Claude Code を呼び出すため、
Pro / Max プランの利用枠で動作する。販売版のビルドではこのファイルを除外する。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

from .base import AIBackend, AIError

# Claude Code の --model に渡す別名
CLI_MODELS = [
    ("opus", "Opus（高品質）"),
    ("sonnet", "Sonnet（速い）"),
    ("haiku", "Haiku（最速）"),
]


def find_claude(custom_path: str = "") -> str | None:
    if custom_path and os.path.exists(custom_path):
        return custom_path
    for name in ("claude", "claude.cmd", "claude.exe"):
        p = shutil.which(name)
        if p:
            return p
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        candidate = os.path.join(appdata, "npm", "claude.cmd")
        if os.path.exists(candidate):
            return candidate
    return None


class CliBackend(AIBackend):
    label = "Claude Code（今のプラン）"

    def __init__(self, cli_path: str = "", model: str = "opus", timeout: int = 300):
        path = find_claude(cli_path)
        if not path:
            raise AIError(
                "Claude Code が見つかりません。インストールしてログインするか、"
                "設定画面で claude の場所を指定してください。"
            )
        self.path = path
        self.model = model if model in {m for m, _ in CLI_MODELS} else "opus"
        self.timeout = timeout

    def generate(self, system: str, prompt: str) -> str:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW  # 黒い窓を出さない
        # プロジェクト用の設定（CLAUDE.md 等）を読み込ませないよう空のフォルダで実行する。
        # 指示文はファイルで渡す：Windows では claude.cmd 経由になるため、
        # 引数に改行があると1行目より後ろが切り捨てられてしまう。
        with tempfile.TemporaryDirectory() as workdir:
            sp_file = os.path.join(workdir, "system_prompt.txt")
            with open(sp_file, "w", encoding="utf-8") as f:
                f.write(system)
            args = [
                self.path, "-p",
                "--output-format", "text",
                "--model", self.model,
                "--system-prompt-file", sp_file,
                "--tools", "",
            ]
            assert not any("\n" in a for a in args)
            try:
                proc = subprocess.run(
                    args,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout,
                    cwd=workdir,
                    creationflags=creationflags,
                )
            except subprocess.TimeoutExpired as e:
                raise AIError("Claude Code の応答がタイムアウトしました。") from e
            except OSError as e:
                raise AIError(f"Claude Code を起動できませんでした: {e}") from e
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip()
            raise AIError(f"Claude Code がエラーを返しました: {msg[:500]}")
        text = proc.stdout.strip()
        if not text:
            raise AIError("Claude Code から空の応答が返りました。")
        return text
