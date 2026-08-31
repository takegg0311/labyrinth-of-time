"""FastAPI エントリポイント。

起動時に問題データを検証する。不備があれば例外を送出して起動を止める。
出題中に問題データの不備が露見しても手遅れなので、遊ぶ前に落とす。
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .quiz import QuizData, load_questions, quiz_data_dir, select_questions

load_dotenv()

logger = logging.getLogger("labyrinth")

app = FastAPI(title="labyrinth-of-time")

# 起動時に読み込んだ問題データ。検証に失敗した場合、load_questions が
# QuizDataError を送出して起動そのものが止まる。
_quiz_data: QuizData = load_questions()

for warning in _quiz_data.warnings:
    logger.warning("%s", warning)
logger.info("出題候補 %d 問を読み込みました。", len(_quiz_data.questions))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/questions")
def questions() -> dict[str, object]:
    """1 ゲーム分の問題を返す。

    正解（answers）は含めない。出題中に正解が画面へ出ないことを、
    そもそもクライアントへ送らないことで保証する。
    """
    selected = select_questions(_quiz_data.questions)
    return {
        "questions": [
            {
                "id": question.id,
                "index": index,
                "text": question.text,
                "audioUrl": question.audio_url(),
                "duration": question.duration,
            }
            for index, question in enumerate(selected)
        ]
    }


@app.get("/audio/{batch}/{filename}")
def audio(batch: str, filename: str) -> FileResponse:
    """問題音声を配信する。

    quiz_data はリポジトリルートに置いたまま参照する。フロントの public/ へ
    コピーする運用にすると、データ更新のたびに同期が要る。
    """
    root = quiz_data_dir().resolve()
    path = (root / batch / filename).resolve()

    # batch や filename に .. を混ぜて quiz_data の外へ出るのを防ぐ
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="音声が見つかりません。")
    if path.suffix.lower() != ".wav":
        raise HTTPException(status_code=404, detail="音声が見つかりません。")

    return FileResponse(path, media_type="audio/wav")
