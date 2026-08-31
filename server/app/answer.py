"""正誤判定。

正解と別解は questions.csv の `answer` / `alt_answers` 列で管理する。

判定は正規化した上での部分一致とする。音声入力を STT にかけた文字列が
相手なので、句読点や助詞が前後に付く（「えーっと、エベレストです」）ことを
前提に緩く取る必要がある。
"""

from __future__ import annotations

import re
import unicodedata

# 比較時に落とす文字。空白・中黒・各種ハイフンと長音記号。
# 「ニュー・ヨーク」「ニューヨーク」「ニユーヨーク」を同一視するため。
_IGNORED = re.compile(r"[\s・･\-ー―‐]")

# 文末に付きやすい語。STT は「エベレストです」のように拾うため、
# 正解「エベレスト」との部分一致を取れるようにこれ自体は消さない
# （部分一致で吸収できる）。ここでは句読点だけ落とす。
_PUNCTUATION = re.compile(r"[、。,.！？!?]")


def normalize(value: str) -> str:
    """比較用の正規化。全角/半角・大文字小文字・記号の揺れを吸収する。"""
    # NFKC で全角英数字やカタカナの互換文字を寄せる
    normalized = unicodedata.normalize("NFKC", value).lower()
    normalized = _PUNCTUATION.sub("", normalized)
    return _IGNORED.sub("", normalized)


def is_correct(transcript: str, answers: list[str]) -> bool:
    """文字起こし結果が正解候補のいずれかと部分一致するか。

    双方向の部分一致を取る。STT が「エベレストです」と拾った場合は
    入力が正解を含み、正解が「アメリカ合衆国」で「アメリカ」と答えた場合は
    正解が入力を含む。どちらも正解として扱いたい。
    """
    normalized_input = normalize(transcript)
    if normalized_input == "":
        return False

    for answer in answers:
        normalized_answer = normalize(answer)
        if normalized_answer == "":
            continue
        if normalized_answer in normalized_input or normalized_input in normalized_answer:
            return True

    return False
