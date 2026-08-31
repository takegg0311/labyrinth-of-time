/** バックエンドとのやり取り。 */

export type Question = {
  id: string;
  index: number;
  text: string;
  audioUrl: string;
  duration: number;
};

export type SttResult = {
  questionId: string;
  transcript: string;
  correct: boolean;
  /** 5.00 秒以内の発声として受理されたか */
  accepted: boolean;
  reason?: string;
};

export type AnswerEntry = {
  id: string;
  index: number;
  answers: string[];
};

/** バックエンドが起動していないときに出す案内 */
const BACKEND_DOWN =
  'バックエンドに接続できません。別のターミナルで次を実行してください:\n' +
  '  uv run --directory server uvicorn app.main:app --port 8000';

/**
 * バックエンドへの GET をまとめる。
 *
 * dev では Vite のプロキシ越しに叩くため、バックエンドが起動していなくても
 * fetch 自体は成功し、プロキシが 500 を返す。状態コードだけでは
 * 「サーバが落ちている」と「サーバがエラーを返した」を区別できない。
 *
 * プロキシの 500 は本文が空になる（実測で確認）。バックエンドが自分で返す
 * エラーは FastAPI が JSON を載せるため、本文の有無で振り分けられる。
 */
async function getJson<T>(path: string, label: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path);
  } catch {
    // プロキシを介さない構成では、接続失敗がここに来る
    throw new Error(BACKEND_DOWN);
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    if (response.status === 500 && detail.trim() === '') {
      throw new Error(BACKEND_DOWN);
    }
    throw new Error(
      detail.trim() === '' ? `${label} (${response.status})` : `${label} (${response.status}): ${detail}`,
    );
  }

  return (await response.json()) as T;
}

export async function fetchQuestions(): Promise<Question[]> {
  const payload = await getJson<{ questions: Question[] }>(
    '/api/questions',
    '問題を取得できませんでした',
  );
  return payload.questions;
}

/** 答え合わせ用の正解。出題中は呼ばない。 */
export async function fetchAnswers(): Promise<AnswerEntry[]> {
  const payload = await getJson<{ answers: AnswerEntry[] }>(
    '/api/answers',
    '正解を取得できませんでした',
  );
  return payload.answers;
}

/**
 * 1 問分の録音を送って文字起こしと判定を受け取る。
 *
 * speechOffsetMs は出題開始から最初の発声までの経過時間。
 * 有効・無効の判定はサーバが行うため、無効そうな場合もそのまま送る。
 */
export async function postAnswer(params: {
  questionId: string;
  audio: Blob;
  speechOffsetMs: number;
}): Promise<SttResult> {
  const form = new FormData();
  // 拡張子は MIME から決める。SDK が形式をファイル名から判断するため。
  const extension = params.audio.type.includes('ogg') ? 'ogg' : 'webm';
  form.append('audio', params.audio, `answer.${extension}`);
  form.append('question_id', params.questionId);
  form.append('speech_offset_ms', String(params.speechOffsetMs));

  const response = await fetch('/api/stt', { method: 'POST', body: form });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`判定に失敗しました (${response.status}): ${detail}`);
  }
  return (await response.json()) as SttResult;
}
