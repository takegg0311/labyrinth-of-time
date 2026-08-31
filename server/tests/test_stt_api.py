"""/api/stt と /api/answers。

実際の API は叩かず、プロバイダを差し替えて検証する。
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.quiz import QUESTIONS_PER_GAME
from app.stt import SttError

from .conftest import QuizDataBuilder


class FakeStt:
    """呼ばれた回数と引数を記録する STT。"""

    def __init__(self, transcript: str = "エベレスト") -> None:
        self.transcript = transcript
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    @property
    def name(self) -> str:
        return "fake"

    def transcribe(self, audio: bytes, *, filename: str, language: str) -> str:
        self.calls.append({"audio": audio, "filename": filename, "language": language})
        if self.error is not None:
            raise self.error
        return self.transcript


@pytest.fixture
def module(builder: QuizDataBuilder, monkeypatch: pytest.MonkeyPatch):
    builder.add("世界一高い山は？", "エベレスト")
    root = builder.add_many(QUESTIONS_PER_GAME - 1).write_csv()
    monkeypatch.setenv("QUIZ_DATA_DIR", str(root))

    import app.main

    return importlib.reload(app.main)


@pytest.fixture
def stt(module) -> FakeStt:
    fake = FakeStt()
    module._stt_provider = fake
    return fake


@pytest.fixture
def client(module) -> TestClient:
    return TestClient(module.app)


def _post(client: TestClient, *, offset: float, question_id: str = "20260820/0"):
    return client.post(
        "/api/stt",
        files={"audio": ("answer.webm", b"fake-audio-bytes", "audio/webm")},
        data={"question_id": question_id, "speech_offset_ms": str(offset)},
    )


def test_文字起こしして正誤を返す(client: TestClient, stt: FakeStt) -> None:
    payload = _post(client, offset=1200.0).json()

    assert payload["transcript"] == "エベレスト"
    assert payload["correct"] is True
    assert payload["accepted"] is True
    assert stt.calls[0]["language"] == "ja"


def test_誤答は正誤だけ偽になる(client: TestClient, stt: FakeStt) -> None:
    stt.transcript = "キリマンジャロ"

    payload = _post(client, offset=1200.0).json()

    assert payload["transcript"] == "キリマンジャロ"
    assert payload["correct"] is False
    assert payload["accepted"] is True


class Test有効回答の境界:
    """発声開始が 5.00 秒以内なら受け付ける。"""

    def test_5秒ちょうどは有効(self, client: TestClient, stt: FakeStt) -> None:
        payload = _post(client, offset=5000.0).json()

        assert payload["accepted"] is True
        assert len(stt.calls) == 1

    def test_5秒を過ぎたら無効(self, client: TestClient, stt: FakeStt) -> None:
        payload = _post(client, offset=5000.1).json()

        assert payload["accepted"] is False
        assert payload["correct"] is False
        assert payload["transcript"] == ""

    def test_無効な回答はsttを呼ばない(self, client: TestClient, stt: FakeStt) -> None:
        """判定するまでもないので API のコストを払わない。"""
        _post(client, offset=6000.0)

        assert stt.calls == []


def test_未知の問題idは404(client: TestClient, stt: FakeStt) -> None:
    assert _post(client, offset=100.0, question_id="なにか/9").status_code == 404


def test_空の音声は400(client: TestClient, stt: FakeStt) -> None:
    response = client.post(
        "/api/stt",
        files={"audio": ("answer.webm", b"", "audio/webm")},
        data={"question_id": "20260820/0", "speech_offset_ms": "100"},
    )

    assert response.status_code == 400


def test_sttの失敗は502(client: TestClient, stt: FakeStt) -> None:
    stt.error = SttError("APIが落ちています")

    response = _post(client, offset=100.0)

    assert response.status_code == 502
    assert "APIが落ちています" in response.json()["detail"]


def test_答え合わせで正解を返す(client: TestClient) -> None:
    payload = client.get("/api/answers").json()

    assert len(payload["answers"]) == QUESTIONS_PER_GAME
    assert payload["answers"][0]["answers"] == ["エベレスト"]
