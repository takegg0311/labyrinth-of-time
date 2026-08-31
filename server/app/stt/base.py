"""STT プロバイダの抽象。

この Issue で実装するのは OpenAI のみだが、後続 Issue で faster-whisper による
ローカル STT を足す予定がある。後から抽象を被せるより、差し替え点を最初から
1 箇所に決めておくほうが安い。

プロバイダは「音声バイト列を受け取って文字列を返す」だけを担う。
正誤判定は answer.py が持ち、プロバイダには持ち込まない。
"""

from __future__ import annotations

from typing import Protocol


class SttError(Exception):
    """文字起こしに失敗した。呼び出し側が 502 へ変換する。"""


class SttProvider(Protocol):
    """音声を文字起こしする。"""

    @property
    def name(self) -> str:
        """プロバイダ名。ログと動作確認用。"""
        ...

    def transcribe(self, audio: bytes, *, filename: str, language: str) -> str:
        """音声バイト列を文字起こしして返す。

        失敗した場合は SttError を送出する。
        """
        ...
