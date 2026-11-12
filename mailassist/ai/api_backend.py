"""Claude API（APIキー）による生成。販売版ではこちらのみ使用する。"""

from __future__ import annotations

import anthropic

from .base import AIBackend, AIError

MODELS = [
    ("claude-opus-5-5", "Claude Opus 5.5（高品質・標準）"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5（低コスト）"),
    ("claude-haiku-5-5", "Claude Haiku 5.5（最安・高速）"),
]

# 安全上の理由で応答が止まった場合に、API 側で別モデルに切り替えて続行させる
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_SUPPORTS_FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5"}


class ApiBackend(AIBackend):
    label = "Claude API"

    def __init__(self, api_key: str, model: str = "claude-opus-5-5"):
        if not api_key:
            raise AIError("APIキーが設定されていません。設定画面で登録してください。")
        self.client = anthropic.Anthropic(api_key=api_key, timeout=120.0)
        self.model = model

    def generate(self, system: str, prompt: str) -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "medium"},
        )
        try:
            if self.model in _SUPPORTS_FALLBACK:
                resp = self.client.beta.messages.create(
                    betas=[_FALLBACK_BETA], fallbacks="default", **kwargs
                )
            else:
                resp = self.client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise AIError("APIキーが正しくありません。設定を確認してください。") from e
        except anthropic.PermissionDeniedError as e:
            raise AIError(f"このAPIキーでは利用できません: {e.message}") from e
        except anthropic.RateLimitError as e:
            raise AIError("利用回数の上限に達しました。しばらく待ってから再度お試しください。") from e
        except anthropic.BadRequestError as e:
            raise AIError(f"リクエストエラー: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise AIError(f"APIエラー（{e.status_code}）: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise AIError("Claude API に接続できませんでした。ネットワークを確認してください。") from e

        if resp.stop_reason == "refusal":
            raise AIError("AIがこの依頼内容の作成を断りました。内容を見直してください。")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            raise AIError("AIから空の応答が返りました。")
        return text
