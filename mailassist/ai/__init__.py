"""設定に応じて AI 接続を作る。"""

from __future__ import annotations

from .. import edition
from ..secrets_store import ANTHROPIC_API_KEY, get_secret
from .base import AIBackend, AIError


def available_backends() -> list[tuple[str, str]]:
    items = []
    if edition.is_personal():
        items.append(("cli", "Claude Code 経由（今のClaudeプラン）"))
    items.append(("api", "Claude API（APIキー）"))
    return items


def create_backend(settings: dict) -> AIBackend:
    kind = settings.get("ai_backend") or "api"
    if kind == "cli" and edition.is_personal():
        from .cli_backend import CliBackend

        return CliBackend(cli_path=settings.get("cli_path") or "",
                          model=settings.get("cli_model") or "opus")
    from .api_backend import ApiBackend

    return ApiBackend(api_key=get_secret(ANTHROPIC_API_KEY),
                      model=settings.get("ai_model") or "claude-opus-5-5")


__all__ = ["AIBackend", "AIError", "available_backends", "create_backend"]
