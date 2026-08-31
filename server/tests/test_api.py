"""HTTP エンドポイント。

main.py はモジュール読み込み時に問題データを読むため、QUIZ_DATA_DIR を
差し替えてから import する必要がある。importlib で読み直して切り離す。
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.quiz import QUESTIONS_PER_GAME

from .conftest import QuizDataBuilder


@pytest.fixture
def client(builder: QuizDataBuilder, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    root = builder.add_many(QUESTIONS_PER_GAME + 3).write_csv()
    monkeypatch.setenv("QUIZ_DATA_DIR", str(root))

    import app.main

    module = importlib.reload(app.main)
    return TestClient(module.app)


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_問題は12問返る(client: TestClient) -> None:
    payload = client.get("/api/questions").json()

    assert len(payload["questions"]) == QUESTIONS_PER_GAME
    assert payload["questions"][0]["index"] == 0


def test_問題に正解を含めない(client: TestClient) -> None:
    """出題中に正解が画面へ出ないことを、送らないことで保証する。"""
    payload = client.get("/api/questions").json()

    for question in payload["questions"]:
        assert "answers" not in question
        assert "answer" not in question


def test_音声を配信する(client: TestClient) -> None:
    response = client.get("/audio/20260820/0-20260820.wav")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"


def test_quiz_dataの外は配信しない(client: TestClient) -> None:
    response = client.get("/audio/20260820/..%2F..%2Fquestions.csv")

    assert response.status_code == 404


def test_wav以外は配信しない(client: TestClient, tmp_path: Path) -> None:
    response = client.get("/audio/20260820/0-20260820.txt")

    assert response.status_code == 404
