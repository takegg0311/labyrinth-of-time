"""quiz_data/questions.csv の読み込みと検証。

問題文と正解は CSV で管理し、VOICEPEAK の出力ファイルはリネームせず
バッチ（日付）フォルダにそのまま置く。サーバがある以上 CSV を直接読めばよく、
manifest.json のような中間生成物は介さない。

本アプリはタイムショック形式であり、5 秒スロットに 1 問ずつ音声を流す。
そのため音声は必須で、trans-ai-quiz にあった「音声なし問題」は設けない。
また .lab（音素タイミング）は 1 文字ずつの文字送りのために必要だったもので、
本アプリは 1 問分を一括表示するため使わない。

ズレたまま出題されるとクイズを遊ぶまで気づけないため、問題があれば
QuizDataError を送出する（main.py がこれを捕まえて起動を止める）。
"""

from __future__ import annotations

import contextlib
import csv
import io
import os
import wave
from dataclasses import dataclass, field
from pathlib import Path

# 1 問につきこの 2 つが揃っている必要がある。
# .lab は文字送り用なので本アプリでは参照しない（置いてあっても無視する）。
AUDIO_EXTENSIONS = (".wav", ".txt")

# ファイル探索で試すゼロ埋め桁数。VOICEPEAK は出力数に応じて 1〜3 桁を使う。
CANDIDATE_WIDTHS = (1, 2, 3)

# 1 問あたりのスロット長（秒）。これを超える音声は次問の再生に食い込むため
# 出題候補から外す。
SLOT_SECONDS = 5.0

# 1 ゲームの出題数。これだけ揃わなければタイムショックとして成立しない。
QUESTIONS_PER_GAME = 12

# alt_answers 列の区切り文字
ALT_ANSWER_SEPARATOR = "|"

CSV_COLUMNS = ("batch", "seq", "text", "answer", "alt_answers")

# quiz_data はリポジトリルートに置く
REPO_ROOT = Path(__file__).resolve().parents[2]
QUIZ_DATA_DIR = REPO_ROOT / "quiz_data"


def quiz_data_dir() -> Path:
    """問題データの場所を返す。

    毎回読むのは、テストで環境変数を差し替えられるようにするため。
    """
    override = os.getenv("QUIZ_DATA_DIR")
    if override is None or override.strip() == "":
        return QUIZ_DATA_DIR
    return Path(override).expanduser().resolve()


def seq_width(count: int) -> int:
    """出力数から、連番のゼロ埋め桁数を求める。

    VOICEPEAK は同じ接尾語で出力したファイル数に応じて連番をゼロ埋めする。
    10 個以上なら 2 桁、100 個以上なら 3 桁。境界は連番の値ではなく出力数で
    決まるため、9 個（0〜8）は 1 桁、10 個（00〜09）は 2 桁になる。
    """
    return len(str(max(count, 1)))


def question_file_path(batch: str, seq: int, ext: str, width: int = 1) -> str:
    """1 問分のファイルの、quiz_data からの相対パスを組み立てる。

    VOICEPEAK は連番だけの出力ができず接尾語が必須のため、接尾語にバッチ名
    （日付）を指定する運用とし、`{batch}/{seq}-{batch}.{ext}` を期待する。
    接尾語がフォルダ名と一致することで、別バッチのファイルを取り違えて
    置いた場合にファイルが見つからず検出できる。
    """
    return f"{batch}/{seq:0{width}d}-{batch}{ext}"


class QuizDataError(Exception):
    """questions.csv の内容に問題がある。起動を止めるために送出する。"""


@dataclass(frozen=True)
class Question:
    """出題 1 問分。"""

    # `{batch}/{seq}` 形式の問題 ID
    id: str
    batch: str
    seq: int
    # quiz_data からの相対パス
    wav: str
    txt: str
    text: str
    # 読み上げ音声の長さ（秒）
    duration: float
    # 正解と別解。先頭が主たる正解。
    answers: list[str]

    def audio_url(self) -> str:
        return f"/audio/{self.wav}"


def wav_duration(path: Path) -> float:
    """WAV の再生時間を秒で返す。

    標準ライブラリの wave で読む。長さを知るためだけに音声ライブラリを
    足す必要はなく、VOICEPEAK が出力するのは非圧縮 PCM の WAV であるため。
    """
    with contextlib.closing(wave.open(str(path), "rb")) as handle:
        frame_rate = handle.getframerate()
        if frame_rate <= 0:
            raise wave.Error("サンプリングレートが 0 です")
        return handle.getnframes() / float(frame_rate)


@dataclass
class _RowResult:
    """1 行分の検証結果。エラーがあれば entry は None になる。"""

    entry: Question | None = None
    messages: list[str] = field(default_factory=list)
    # 出題候補から外した理由（エラーではないので起動は止めない）
    warnings: list[str] = field(default_factory=list)


def _to_answers(row: dict[str, str]) -> list[str]:
    """正解と別解をまとめる。空要素は落とす。"""
    alternatives = [
        value.strip()
        for value in row["alt_answers"].split(ALT_ANSWER_SEPARATOR)
        if value.strip() != ""
    ]
    return [row["answer"], *alternatives]


def _probe_width(
    batch: str, seq: int, directory: Path, width: int
) -> tuple[dict[str, str], list[str]]:
    """指定した桁数で 1 問分のファイルを探す。"""
    found: dict[str, str] = {}
    missing: list[str] = []

    for ext in AUDIO_EXTENSIONS:
        relative_path = question_file_path(batch, seq, ext, width)
        if (directory / relative_path).exists():
            found[ext] = relative_path
        else:
            missing.append(ext)

    return found, missing


def _find_audio_paths(
    batch: str, seq: int, directory: Path, width: int
) -> tuple[dict[str, str], list[str]]:
    """1 問分のファイルを探す。見つかった分と、見つからなかった拡張子を返す。

    まず想定桁数 width で探し、1 つも見つからなければ他の桁数でも試す。

    他の桁数まで見るのは、バッチ内の連番の最大値が変わると想定桁数も変わり、
    以前の桁数で出力した既存ファイルを見失うため。例えば 0〜8 の 9 問（1 桁）に
    seq=9 を足すと width が 2 になり、`0-....wav` を `00-....wav` として
    探して全問が見つからなくなる。
    """
    at_width = _probe_width(batch, seq, directory, width)

    # 想定桁に 1 つでもあれば、その結果をそのまま返す。想定桁は本来ファイルが
    # 置かれるべき場所なので、そこに一部だけあるなら置き忘れとみなす。
    # ここで他の桁へ逃がすと、置き忘れの検出が甘くなる。
    if at_width[0]:
        return at_width

    # 想定桁が空の場合だけ、他の桁を見る。ここでは 2 点揃いを優先する。
    # 1 つでも見つかった桁を採る方式だと、古い桁数で作ったファイルの残骸が
    # 揃っている側より先に当たり、実際には揃っているのに一部欠けとして弾いてしまう。
    partial: tuple[dict[str, str], list[str]] | None = None

    for candidate in CANDIDATE_WIDTHS:
        if candidate == width:
            continue

        found, missing = _probe_width(batch, seq, directory, candidate)
        if found and not missing:
            return found, missing
        if found and partial is None:
            partial = (found, missing)

    if partial is not None:
        return partial

    return {}, list(AUDIO_EXTENSIONS)


def _validate_row(
    row: dict[str, str], line_number: int, directory: Path, width: int
) -> _RowResult:
    """1 行を検証して Question にする。

    width はバッチ内の連番のゼロ埋め桁数。バッチ全体を見ないと決まらないため
    呼び出し側から渡す。
    """
    label = f"{line_number} 行目"
    result = _RowResult()

    for column in ("batch", "seq", "text", "answer"):
        if row[column] == "":
            result.messages.append(f"{label}: {column} が空です。")

    seq: int | None = None
    if row["seq"] != "":
        try:
            seq = int(row["seq"])
            if seq < 0:
                raise ValueError
        except ValueError:
            result.messages.append(
                f"{label}: seq は 0 以上の整数である必要があります（{row['seq']}）。"
            )
            seq = None

    # 1 問 1 ブロックが前提。改行があると seq が複数消費され対応が崩れる
    if "\n" in row["text"]:
        result.messages.append(
            f"{label}: text に改行を含められません（1 問 1 ブロック）。"
        )

    if result.messages or seq is None:
        return result

    question_id = f"{row['batch']}/{seq}"
    paths, missing = _find_audio_paths(row["batch"], seq, directory, width)

    # 本アプリは音声の再生が出題の前提。1 つも無い場合も出題できないので止める。
    if not paths:
        expected = question_file_path(row["batch"], seq, "", width)
        result.messages.append(
            f"{label} ({question_id}): 音声ファイルが見つかりません。"
            f"{expected}.wav と {expected}.txt を配置してください。"
        )
        return result

    # 一部だけある場合はファイルの置き忘れ・置き間違いとして止める。
    # ここを黙って見逃すと、音声を用意したはずの問題が無音で出題され、
    # 本番で初めて気づくことになる。
    if missing:
        found_names = ", ".join(sorted(paths.values()))
        missing_names = ", ".join(missing)
        result.messages.append(
            f"{label} ({question_id}): 音声ファイルが揃っていません。"
            f"{missing_names} が見つかりません（{found_names} はあります）。\n"
            f"    .wav と .txt の 2 点を揃えてください。"
        )
        return result

    # CSV の text と VOICEPEAK が出力した txt を突き合わせる。
    # ズレたまま出題されるとクイズを遊ぶまで気づけないため、ここで止める。
    txt_content = (directory / paths[".txt"]).read_text(encoding="utf-8").strip()
    if txt_content != row["text"]:
        result.messages.append(
            f"{label} ({question_id}): text が {paths['.txt']} と一致しません。\n"
            f"    CSV: {row['text']}\n"
            f"    TXT: {txt_content}"
        )
        return result

    try:
        duration = wav_duration(directory / paths[".wav"])
    except (wave.Error, OSError) as error:
        result.messages.append(
            f"{label} ({question_id}): {paths['.wav']} を WAV として読めません（{error}）。"
        )
        return result

    # スロットに収まらない音声は次問の再生に食い込むため出題候補から外す。
    # ここで起動を止めないのは、5 秒超が「音声を作り直せば直る」だけの状態であり、
    # 残りの問題で動作確認や試遊ができるほうが有用なため。
    if duration > SLOT_SECONDS:
        result.warnings.append(
            f"{label} ({question_id}): {paths['.wav']} が {duration:.2f} 秒あり、"
            f"スロット長 {SLOT_SECONDS:.0f} 秒を超えるため出題候補から外しました。"
        )
        return result

    result.entry = Question(
        id=question_id,
        batch=row["batch"],
        seq=seq,
        wav=paths[".wav"],
        txt=paths[".txt"],
        text=row["text"],
        duration=duration,
        answers=_to_answers(row),
    )
    return result


@dataclass(frozen=True)
class QuizData:
    """出題候補と、候補から外した問題の理由。"""

    questions: list[Question]
    warnings: list[str]


def load_questions(directory: Path | None = None) -> QuizData:
    """questions.csv を読んで検証し、出題候補を返す。

    検証に失敗した場合、および出題候補が 1 ゲーム分に満たない場合は
    QuizDataError を送出する。
    """
    target = directory if directory is not None else quiz_data_dir()
    csv_path = target / "questions.csv"

    try:
        source = csv_path.read_text(encoding="utf-8")
    except OSError as error:
        raise QuizDataError(
            f"{csv_path} を読み取れませんでした。"
            "batch,seq,text,answer,alt_answers の 5 列を持つ CSV を配置してください。"
        ) from error

    # 問題文に `,` が含まれるためクォートの解釈が要る。csv モジュールは
    # クォート内の改行も 1 フィールドとして読むので、行番号はレコード単位でズレない。
    reader = csv.reader(io.StringIO(source))
    try:
        header = next(reader)
    except StopIteration:
        raise QuizDataError("questions.csv が空です。") from None

    header_names = [name.strip() for name in header]
    absent = [name for name in CSV_COLUMNS if name not in header_names]
    if absent:
        raise QuizDataError(
            f"questions.csv のヘッダに {', '.join(absent)} がありません。"
            f"期待する列: {', '.join(CSV_COLUMNS)}"
        )

    column_index = {name: header_names.index(name) for name in CSV_COLUMNS}

    errors: list[str] = []
    warnings: list[str] = []
    questions: list[Question] = []
    seen_ids: dict[str, int] = {}

    # ファイル名のゼロ埋め桁数はバッチ内の出力数で決まるため、行ごとの検証に入る前に
    # 全行を読んでバッチごとの連番の最大値を集める。
    rows: list[tuple[int, dict[str, str]]] = []
    max_seq: dict[str, int] = {}

    for index, cells in enumerate(reader):
        # 空行は読み飛ばす
        if not any(cell.strip() for cell in cells):
            continue

        # ヘッダ行があるため、CSV 上の行番号は +2
        line_number = index + 2
        row = {
            name: (cells[position].strip() if position < len(cells) else "")
            for name, position in column_index.items()
        }
        rows.append((line_number, row))

        # 桁数の集計。ここでは検証せず、数として読めるものだけを見る。
        # 不正な値は _validate_row が行番号つきで報告する。
        try:
            seq = int(row["seq"])
        except ValueError:
            continue
        if seq < 0:
            continue
        if seq > max_seq.get(row["batch"], -1):
            max_seq[row["batch"]] = seq

    # 連番は 0 起点なので、出力数は最大値 + 1。
    # CSV の行数を使わないのは、行を削っても実ファイル名の桁数は変わらないため。
    widths = {batch: seq_width(largest + 1) for batch, largest in max_seq.items()}

    for line_number, row in rows:
        result = _validate_row(row, line_number, target, widths.get(row["batch"], 1))
        errors.extend(result.messages)
        warnings.extend(result.warnings)
        if result.entry is None:
            continue

        duplicated_at = seen_ids.get(result.entry.id)
        if duplicated_at is not None:
            errors.append(
                f"{line_number} 行目: {result.entry.id} が {duplicated_at} 行目と重複しています。"
            )
            continue

        seen_ids[result.entry.id] = line_number
        questions.append(result.entry)

    if errors:
        joined = "\n  - ".join(errors)
        raise QuizDataError(f"questions.csv に問題があります。\n  - {joined}")

    # 除外は候補プールの掃除、ここは出題成立の最低条件という二段構え。
    # 中途半端な問題数で遊べてしまうと、データの不備に気づけない。
    if len(questions) < QUESTIONS_PER_GAME:
        detail = ""
        if warnings:
            joined = "\n  - ".join(warnings)
            detail = f"\n出題候補から外した問題:\n  - {joined}"
        raise QuizDataError(
            f"出題可能な問題が {len(questions)} 問しかありません。"
            f"1 ゲームに {QUESTIONS_PER_GAME} 問必要です。{detail}"
        )

    return QuizData(questions=questions, warnings=warnings)


def select_questions(questions: list[Question]) -> list[Question]:
    """1 ゲーム分を選ぶ。

    この Issue では先頭から固定順とする。固定順のほうが動作確認・再現・
    デバッグが容易で、ランダム化は出題ロジックの差し替えだけで足りるため
    後続 Issue へ分ける。
    """
    return questions[:QUESTIONS_PER_GAME]
