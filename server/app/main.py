"""FastAPI エントリポイント。

起動時に問題データを検証する。不備があれば例外を送出して起動を止める。
出題中に問題データの不備が露見しても手遅れなので、遊ぶ前に落とす。
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .answer import is_correct
from .quiz import (
    SLOT_SECONDS,
    QuizData,
    Question,
    load_questions,
    quiz_data_dir,
    select_questions,
)
from .stt import SttError, SttProvider, build_provider

load_dotenv()

logger = logging.getLogger("labyrinth")

# 有効回答の境界（ミリ秒）。発声開始がこれ以内なら受け付ける。
SLOT_MS = SLOT_SECONDS * 1000

app = FastAPI(title="labyrinth-of-time")

# 起動時に読み込んだ問題データ。検証に失敗した場合、load_questions が
# QuizDataError を送出して起動そのものが止まる。
_quiz_data: QuizData = load_questions()

for warning in _quiz_data.warnings:
    logger.warning("%s", warning)
logger.info("出題候補 %d 問を読み込みました。", len(_quiz_data.questions))

# STT プロバイダは遅延生成する。ここで API キーの有無を確かめて起動を止めると、
# 問題データの確認や画面の動作確認まで API キー無しにはできなくなる。
_stt_provider: SttProvider | None = None


def stt_provider() -> SttProvider:
    global _stt_provider
    if _stt_provider is None:
        _stt_provider = build_provider()
    return _stt_provider


def _find_question(question_id: str) -> Question:
    for question in _quiz_data.questions:
        if question.id == question_id:
            return question
    raise HTTPException(status_code=404, detail=f"問題が見つかりません: {question_id}")


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


@app.post("/api/stt")
async def stt(
    audio: UploadFile = File(...),
    question_id: str = Form(...),
    speech_offset_ms: float = Form(...),
) -> dict[str, object]:
    """1 問分の録音を文字起こしし、正誤を判定して返す。

    speech_offset_ms は、出題開始から最初の発声を検出するまでの経過時間。
    フロントが送ってくるのは、有効・無効にかかわらず発声を拾った場合である。

    5.00 秒を過ぎてからの発声開始は、次の問題に対する発声とみなして無効とする。
    この判定をサーバで行うのは、判定ロジックを 1 箇所へ集約するため。
    """
    question = _find_question(question_id)

    # 無効回答は文字起こしする必要がない。API を叩かず即座に返す。
    if speech_offset_ms > SLOT_MS:
        return {
            "questionId": question_id,
            "transcript": "",
            "correct": False,
            "accepted": False,
            "reason": "発声が 5.00 秒を過ぎたため無効",
        }

    payload = await audio.read()
    if not payload:
        raise HTTPException(status_code=400, detail="音声が空です。")

    try:
        transcript = stt_provider().transcribe(
            payload,
            filename=audio.filename or "answer.webm",
            language="ja",
        )
    except SttError as error:
        logger.warning("STT に失敗しました (%s): %s", question_id, error)
        raise HTTPException(status_code=502, detail=str(error)) from error

    return {
        "questionId": question_id,
        "transcript": transcript,
        "correct": is_correct(transcript, question.answers),
        "accepted": True,
    }


@app.get("/api/answers")
def answers() -> dict[str, object]:
    """答え合わせ用に正解を返す。

    出題中は呼ばない。フロントは出題終了後の答え合わせでのみ取得する。
    """
    return {
        "answers": [
            {"id": question.id, "index": index, "answers": question.answers}
            for index, question in enumerate(select_questions(_quiz_data.questions))
        ]
    }
