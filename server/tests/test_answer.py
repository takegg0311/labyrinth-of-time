"""正誤判定。"""

from __future__ import annotations

import pytest

from app.answer import is_correct, normalize


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("エベレスト", True),
        # STT は文末表現ごと拾う
        ("エベレストです", True),
        ("えーっと、エベレスト", True),
        # 表記の揺れ
        ("えべれすと", False),  # ひらがなは別語として扱う
        ("ｴﾍﾞﾚｽﾄ", True),  # 半角カナは NFKC で寄る
        ("エベレ スト", True),  # 空白は落とす
        ("キリマンジャロ", False),
        ("", False),
    ],
)
def test_部分一致で判定する(transcript: str, expected: bool) -> None:
    assert is_correct(transcript, ["エベレスト"]) is expected


def test_別解でも正解になる() -> None:
    answers = ["Python", "パイソン", "ニシキヘビ"]

    assert is_correct("パイソンです", answers) is True
    assert is_correct("にしきへび", answers) is False
    assert is_correct("ニシキヘビ", answers) is True


def test_大文字小文字を区別しない() -> None:
    assert is_correct("python", ["Python"]) is True
    assert is_correct("ＰＹＴＨＯＮ", ["Python"]) is True


def test_正解より短い回答も部分一致で拾う() -> None:
    """「アメリカ合衆国」に対し「アメリカ」と答えた場合。"""
    assert is_correct("アメリカ", ["アメリカ合衆国"]) is True


def test_長音や中黒の揺れを吸収する() -> None:
    assert is_correct("ニューヨーク", ["ニュー・ヨーク"]) is True


def test_空の正解候補は無視する() -> None:
    assert is_correct("なにか", ["", "エベレスト"]) is False


def test_正規化() -> None:
    assert normalize("エベレスト、です。") == "エベレストです"
    assert normalize("Ｐｙｔｈｏｎ") == "python"
