"""テスト用の quiz_data を組み立てるヘルパ。"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

CSV_HEADER = "batch,seq,text,answer,alt_answers\n"


def write_wav(path: Path, seconds: float, rate: int = 24000) -> None:
    """指定した長さの無音 WAV を書く。長さの検査だけが目的なので中身は問わない。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack("<%dh" % frames, *([0] * frames)))


class QuizDataBuilder:
    """1 問分のファイル一式を組み立てる。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._rows: list[str] = []

    def add(
        self,
        text: str,
        answer: str = "答え",
        *,
        batch: str = "20260820",
        seq: int | None = None,
        seconds: float = 3.0,
        width: int = 1,
        wav: bool = True,
        txt: bool = True,
        txt_text: str | None = None,
        alt_answers: str = "",
    ) -> "QuizDataBuilder":
        if seq is None:
            seq = len(self._rows)
        self._rows.append(f"{batch},{seq},{text},{answer},{alt_answers}")

        stem = self.root / batch / f"{seq:0{width}d}-{batch}"
        if wav:
            write_wav(stem.with_suffix(".wav"), seconds)
        if txt:
            stem.parent.mkdir(parents=True, exist_ok=True)
            stem.with_suffix(".txt").write_text(
                txt_text if txt_text is not None else text, encoding="utf-8"
            )
        return self

    def add_many(self, count: int, **kwargs) -> "QuizDataBuilder":
        for _ in range(count):
            self.add(f"問題{len(self._rows)}は？", **kwargs)
        return self

    def write_csv(self, body: str | None = None) -> Path:
        content = CSV_HEADER + (
            body if body is not None else "\n".join(self._rows) + "\n"
        )
        path = self.root / "questions.csv"
        path.write_text(content, encoding="utf-8")
        return self.root


@pytest.fixture
def builder(tmp_path: Path) -> QuizDataBuilder:
    return QuizDataBuilder(tmp_path)
