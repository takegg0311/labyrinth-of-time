/**
 * ゲーム進行の状態。
 *
 * タイムライン・音声再生・録音・判定の呼び出しをここでまとめる。
 *
 * 判定結果（正誤・文字起こし）は出題中も届くが、画面には出さない。
 * 正解そのものは answers を取りに行くまでクライアントに存在しない。
 */

import { useCallback, useRef, useState } from 'react';
import {
  fetchAnswers,
  fetchQuestions,
  postAnswer,
  type AnswerEntry,
  type Question,
} from '../lib/api';
import { createPlayer } from '../lib/player';
import { createRecorder } from '../lib/recorder';
import { QUESTION_COUNT, startTimeline } from '../lib/timeline';

export type Phase = 'idle' | 'preparing' | 'playing' | 'finished' | 'review';

/** 1 問分の結果。判定が届くまで status は 'pending' */
export type Result = {
  question: Question;
  status: 'pending' | 'done' | 'failed';
  transcript?: string;
  correct?: boolean;
  /** 5.00 秒以内の発声として受理されたか */
  accepted?: boolean;
  /** 答え合わせで取得する正解。それまでは undefined */
  answers?: string[];
};

export function useGame() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string>();
  const [results, setResults] = useState<Result[]>([]);
  /** 出題中の問題の位置。未出題は -1 */
  const [currentIndex, setCurrentIndex] = useState(-1);

  const playerRef = useRef<ReturnType<typeof createPlayer>>(undefined);
  const recorderRef = useRef<Awaited<ReturnType<typeof createRecorder>>>(undefined);

  /** 1 問分の判定結果を、その行だけ差し替える */
  const patchResult = useCallback((index: number, patch: Partial<Result>) => {
    setResults((current) =>
      current.map((result, position) =>
        position === index ? { ...result, ...patch } : result,
      ),
    );
  }, []);

  const start = useCallback(async () => {
    setError(undefined);
    setPhase('preparing');

    let questions: Question[];
    try {
      questions = await fetchQuestions();
      if (questions.length < QUESTION_COUNT) {
        throw new Error(`問題が ${questions.length} 問しかありません。`);
      }

      const player = createPlayer();
      await player.preload(questions.map((question) => question.audioUrl));
      playerRef.current = player;

      // マイクの許可はここで取る。出題が始まってからでは間に合わない。
      recorderRef.current = await createRecorder();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setPhase('idle');
      return;
    }

    setResults(
      questions.map((question) => ({ question, status: 'pending' as const })),
    );
    setPhase('playing');

    const onSlot = (index: number) => {
      setCurrentIndex(index);
      playerRef.current?.play(questions[index].audioUrl);

      // 録音は待たずに走らせる。セグメントの確定はスロットを越えうるので、
      // ここで待つとタイムラインが止まってしまう。
      void (async () => {
        const recorder = recorderRef.current;
        if (recorder === undefined) return;

        try {
          const segment = await recorder.record();

          // 発声が無ければ送らない。無回答として扱う。
          if (segment.speechOffsetMs === undefined) {
            patchResult(index, { status: 'done', transcript: '', correct: false, accepted: false });
            return;
          }

          const result = await postAnswer({
            questionId: questions[index].id,
            audio: segment.audio,
            speechOffsetMs: segment.speechOffsetMs,
          });
          patchResult(index, {
            status: 'done',
            transcript: result.transcript,
            correct: result.correct,
            accepted: result.accepted,
          });
        } catch {
          // 1 問の失敗で全体を止めない。その行だけ失敗として残す。
          patchResult(index, { status: 'failed' });
        }
      })();
    };

    startTimeline({
      onSlot,
      onFinish: () => {
        setCurrentIndex(-1);
        setPhase('finished');
        playerRef.current?.stopAll();
      },
    });
  }, [patchResult]);

  /** 答え合わせへ進む。ここで初めて正解を取りに行く */
  const review = useCallback(async () => {
    try {
      const entries: AnswerEntry[] = await fetchAnswers();
      setResults((current) =>
        current.map((result, index) => ({
          ...result,
          answers: entries[index]?.answers,
        })),
      );
      setPhase('review');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, []);

  const reset = useCallback(() => {
    recorderRef.current?.close();
    recorderRef.current = undefined;
    void playerRef.current?.close();
    playerRef.current = undefined;
    setResults([]);
    setCurrentIndex(-1);
    setError(undefined);
    setPhase('idle');
  }, []);

  return { phase, error, results, currentIndex, start, review, reset };
}
