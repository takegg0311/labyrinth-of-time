# labyrinth of time

5 秒ごとに 1 問、1 分間で 12 問を出題する「タイムショック」形式のクイズ。
回答は音声で行い、Speech-to-Text で文字起こしして正誤を判定する。

出題中は正解を伏せ、出題が終わってから答え合わせを行う。

## 構成

```
labyrinth-of-time/
├── quiz_data/     問題データ（CSV と VOICEPEAK の出力）
├── server/        バックエンド（Python / FastAPI）。問題の配信・STT・正誤判定
├── web/           フロントエンド（TypeScript / React）。出題の進行と録音
└── docs/          詳細ドキュメント
```

| ディレクトリ | 内容 |
| --- | --- |
| `quiz_data/` | 問題データ。[詳細](docs/quiz-data.md) |
| `server/` | 問題データの検証、音声の配信、文字起こしと正誤判定 |
| `web/` | 出題タイムライン、問題音声の再生、録音とセグメント切り出し |

## 必要なもの

- Node.js 22 以上
- Python 3.12 以上と [uv](https://docs.astral.sh/uv/)
- OpenAI の API キー（文字起こしに使う）
- 問題データ（[docs/quiz-data.md](docs/quiz-data.md) を参照）

## 準備

```bash
npm install
```

```bash
uv sync --project server
```

サンプルの問題は 1 問しか含まれていない。1 ゲームには 12 問が要るので、
自分で問題データを用意する（[docs/quiz-data.md](docs/quiz-data.md)）。

API キーを設定する。

```bash
cp server/.env.example server/.env
```

`server/.env` の `OPENAI_API_KEY` を自分のキーに書き換える。

## 起動

バックエンドを起動する。

```bash
uv run --project server uvicorn app.main:app --port 8000
```

問題データに不備があれば、ここで理由を表示して起動が止まる。
5 秒を超える問題音声は警告を出して出題候補から外す。

別のターミナルでフロントエンドを起動する。

```bash
npm run dev -w web
```

http://localhost:5273 を開き、「スタート」を押す。
マイクの使用許可を求められるので許可する。

## 遊びかた

1. 「スタート」を押すと 5 秒ごとに 1 問ずつ、計 12 問が読み上げられる
2. 問題文は読み上げに合わせて 1 行ずつ表示される
3. 出題から 5 秒以内に声で答える。最初の発声が 5.00 秒以内なら有効
4. 60 秒経ったら「答え合わせ」を押すと、正解と自分の回答が並ぶ

文字起こしには時間がかかるため、判定は出題中（次の問題の読み上げ中）に
行われる。答え合わせを開いた時点で間に合っていない問題は「判定中…」と
表示され、届き次第その行だけが更新される。

## テスト

```bash
uv run --project server pytest
```

```bash
npm run test -w web
```
