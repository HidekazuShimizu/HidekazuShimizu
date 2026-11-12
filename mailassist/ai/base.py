"""AI 接続の共通インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AIError(Exception):
    pass


class AIBackend(ABC):
    label = ""

    @abstractmethod
    def generate(self, system: str, prompt: str) -> str:
        """system と prompt から生成テキストを返す。失敗時は AIError。"""
