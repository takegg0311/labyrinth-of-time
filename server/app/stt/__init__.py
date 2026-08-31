"""STT プロバイダの選択。"""

from __future__ import annotations

import os

from .base import SttError, SttProvider
from .openai_provider import OpenAiStt

__all__ = ["SttError", "SttProvider", "build_provider"]


def build_provider(name: str | None = None) -> SttProvider:
    """環境変数 STT_PROVIDER に応じたプロバイダを返す。

    現在は openai のみ。faster-whisper は後続 Issue で足す。
    """
    provider = (name or os.getenv("STT_PROVIDER") or "openai").strip().lower()

    if provider == "openai":
        return OpenAiStt()

    raise SttError(
        f"未知の STT_PROVIDER です: {provider}。現在は openai のみ対応しています。"
    )
