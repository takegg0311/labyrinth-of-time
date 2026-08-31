"""OpenAI API による文字起こし。"""

from __future__ import annotations

import io
import os

from .base import SttError

DEFAULT_MODEL = "gpt-4o-transcribe"


class OpenAiStt:
    """OpenAI の音声文字起こし API を叩く。"""

    def __init__(self, model: str | None = None, client: object | None = None) -> None:
        self._model = model or os.getenv("STT_MODEL") or DEFAULT_MODEL
        # client を差し込めるようにしているのは、テストで API を叩かないため
        self._client = client

    @property
    def name(self) -> str:
        return f"openai:{self._model}"

    def _ensure_client(self) -> object:
        if self._client is not None:
            return self._client

        if not os.getenv("OPENAI_API_KEY"):
            raise SttError(
                "OPENAI_API_KEY が設定されていません。server/.env に設定してください。"
            )

        # import をここまで遅らせるのは、STT を使わないテストや起動で
        # SDK の読み込みコストを払わないため。
        from openai import OpenAI

        self._client = OpenAI()
        return self._client

    def transcribe(self, audio: bytes, *, filename: str, language: str) -> str:
        client = self._ensure_client()

        # SDK はファイル名から形式を判断するため、名前を保ったまま渡す
        payload = io.BytesIO(audio)
        payload.name = filename

        try:
            result = client.audio.transcriptions.create(  # type: ignore[attr-defined]
                model=self._model,
                file=payload,
                language=language,
            )
        except Exception as error:  # noqa: BLE001 - SDK の例外階層に依存しない
            raise SttError(f"文字起こしに失敗しました: {error}") from error

        return (result.text or "").strip()
