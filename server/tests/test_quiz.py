"""問題データの読み込みと検証。"""

from __future__ import annotations

import pytest

from app.quiz import (
    QUESTIONS_PER_GAME,
    QuizDataError,
    load_questions,
    select_questions,
    seq_width,
)

from .conftest import QuizDataBuilder


def test_出題可能な問題を読み込める(builder: QuizDataBuilder) -> None:
    root = builder.add_many(QUESTIONS_PER_GAME).write_csv()

    data = load_questions(root)

    assert len(data.questions) == QUESTIONS_PER_GAME
    assert data.warnings == []
    assert data.questions[0].text == "問題0は？"
    assert data.questions[0].audio_url() == "/audio/20260820/0-20260820.wav"


def test_別解を分解して読み込む(builder: QuizDataBuilder) -> None:
    builder.add("大蛇の名を持つ言語は？", "Python", alt_answers="パイソン|ニシキヘビ")
    root = builder.add_many(QUESTIONS_PER_GAME - 1).write_csv()

    data = load_questions(root)

    assert data.questions[0].answers == ["Python", "パイソン", "ニシキヘビ"]


def test_5秒を超える音声は候補から外し警告する(builder: QuizDataBuilder) -> None:
    """除外しても 12 問残るので起動は続く。"""
    builder.add_many(QUESTIONS_PER_GAME)
    root = builder.add("長すぎる問題は？", seconds=6.0).write_csv()

    data = load_questions(root)

    assert len(data.questions) == QUESTIONS_PER_GAME
    assert len(data.warnings) == 1
    assert "6.00 秒" in data.warnings[0]
    assert "出題候補から外しました" in data.warnings[0]


def test_ちょうど5秒は候補に残る(builder: QuizDataBuilder) -> None:
    """スロット長と同じ長さは、はみ出していないので出題できる。"""
    builder.add("ちょうどの問題は？", seconds=5.0)
    root = builder.add_many(QUESTIONS_PER_GAME - 1).write_csv()

    data = load_questions(root)

    assert len(data.questions) == QUESTIONS_PER_GAME
    assert data.warnings == []


def test_除外の結果12問に満たなければエラーで止まる(builder: QuizDataBuilder) -> None:
    builder.add_many(QUESTIONS_PER_GAME - 1)
    root = builder.add("長すぎる問題は？", seconds=6.0).write_csv()

    with pytest.raises(QuizDataError) as error:
        load_questions(root)

    message = str(error.value)
    assert "11 問しかありません" in message
    # 足りない原因（除外した問題）も併せて示す
    assert "出題候補から外した問題" in message
    assert "スロット長" in message


def test_問題数が最初から足りなければエラーで止まる(builder: QuizDataBuilder) -> None:
    root = builder.add_many(3).write_csv()

    with pytest.raises(QuizDataError, match="3 問しかありません"):
        load_questions(root)


def test_wavだけ置くとエラーになる(builder: QuizDataBuilder) -> None:
    builder.add_many(QUESTIONS_PER_GAME)
    root = builder.add("txt がない問題は？", txt=False).write_csv()

    with pytest.raises(QuizDataError) as error:
        load_questions(root)

    message = str(error.value)
    assert "揃っていません" in message
    assert ".txt" in message


def test_txtだけ置くとエラーになる(builder: QuizDataBuilder) -> None:
    builder.add_many(QUESTIONS_PER_GAME)
    root = builder.add("wav がない問題は？", wav=False).write_csv()

    with pytest.raises(QuizDataError) as error:
        load_questions(root)

    message = str(error.value)
    assert "揃っていません" in message
    assert ".wav" in message


def test_音声が1つも無ければエラーになる(builder: QuizDataBuilder) -> None:
    """音声の再生が出題の前提なので、音声なし問題は認めない。"""
    builder.add_many(QUESTIONS_PER_GAME)
    root = builder.add("音声なしは？", wav=False, txt=False).write_csv()

    with pytest.raises(QuizDataError, match="音声ファイルが見つかりません"):
        load_questions(root)


def test_txtとcsvがズレていればエラーになる(builder: QuizDataBuilder) -> None:
    builder.add_many(QUESTIONS_PER_GAME)
    root = builder.add("CSV の問題文は？", txt_text="別の問題文です").write_csv()

    with pytest.raises(QuizDataError) as error:
        load_questions(root)

    message = str(error.value)
    assert "一致しません" in message
    assert "別の問題文です" in message


def test_問題idの重複を検出する(builder: QuizDataBuilder) -> None:
    builder.add_many(QUESTIONS_PER_GAME)
    # 同じ seq を再度使う。ファイルは 1 問目と同じものを指すため text も揃える
    builder.add("問題0は？", seq=0)
    root = builder.write_csv()

    with pytest.raises(QuizDataError, match="重複しています"):
        load_questions(root)


def test_必須列が空ならエラーになる(builder: QuizDataBuilder) -> None:
    builder.add_many(QUESTIONS_PER_GAME)
    root = builder.write_csv(
        body="\n".join(builder._rows) + "\n20260820,99,,答え,\n"
    )

    with pytest.raises(QuizDataError, match="text が空です"):
        load_questions(root)


def test_ヘッダが欠けていればエラーになる(builder: QuizDataBuilder) -> None:
    root = builder.root
    (root / "questions.csv").write_text("batch,seq,text\n", encoding="utf-8")

    with pytest.raises(QuizDataError, match="ヘッダに answer"):
        load_questions(root)


def test_csvが無ければエラーになる(builder: QuizDataBuilder) -> None:
    with pytest.raises(QuizDataError, match="読み取れませんでした"):
        load_questions(builder.root)


def test_問題文のカンマはクォートで扱える(builder: QuizDataBuilder) -> None:
    text = "日本一の山は富士山ですが、世界一は？"
    builder.add(text)
    root = builder.add_many(QUESTIONS_PER_GAME - 1).write_csv()

    data = load_questions(root)

    assert data.questions[0].text == text


class Test連番のゼロ埋め:
    """VOICEPEAK は同じ接尾語で出力したファイル数に応じて連番をゼロ埋めする。"""

    def test_出力数から桁数を求める(self) -> None:
        # 境界は連番の値ではなく出力数で決まる
        assert seq_width(9) == 1
        assert seq_width(10) == 2
        assert seq_width(99) == 2
        assert seq_width(100) == 3

    def test_12問なら2桁で探す(self, builder: QuizDataBuilder) -> None:
        root = builder.add_many(QUESTIONS_PER_GAME, width=2).write_csv()

        data = load_questions(root)

        assert data.questions[0].wav == "20260820/00-20260820.wav"

    def test_桁数が変わっても既存ファイルを見失わない(
        self, builder: QuizDataBuilder
    ) -> None:
        """9 問（1 桁）に seq=100 を足すと想定桁が 3 になるが、既存は 1 桁のまま。"""
        builder.add_many(QUESTIONS_PER_GAME, width=1)
        root = builder.add("大きな連番の問題は？", seq=100, width=3).write_csv()

        data = load_questions(root)

        assert len(data.questions) == QUESTIONS_PER_GAME + 1
        assert data.questions[0].wav == "20260820/0-20260820.wav"


def test_出題は先頭から固定順で12問選ぶ(builder: QuizDataBuilder) -> None:
    """ランダム化は後続 Issue。ここでは CSV の順序をそのまま使う。"""
    root = builder.add_many(20).write_csv()

    selected = select_questions(load_questions(root).questions)

    assert len(selected) == QUESTIONS_PER_GAME
    assert [q.text for q in selected] == [f"問題{i}は？" for i in range(12)]
