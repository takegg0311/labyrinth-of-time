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

export async function fetchQuestions(): Promise<Question[]> {
  const response = await fetch('/api/questions');
  if (!response.ok) {
    throw new Error(`問題を取得できませんでした (${response.status})`);
  }
  const payload = (await response.json()) as { questions: Question[] };
  return payload.questions;
}

/** 答え合わせ用の正解。出題中は呼ばない。 */
export async function fetchAnswers(): Promise<AnswerEntry[]> {
  const response = await fetch('/api/answers');
  if (!response.ok) {
    throw new Error(`正解を取得できませんでした (${response.status})`);
  }
  const payload = (await response.json()) as { answers: AnswerEntry[] };
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
