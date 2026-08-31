/**
 * 1 問分の録音セグメントを、いつ切るかを決める状態機械。
 *
 * 固定 5 秒で切ると、5 秒目の直前に喋り始めた回答が途中で切断される。
 * そこで発声を検出した後は、無音になるまで（最大 +3 秒）次スロットへ
 * 食い込んで録音を続ける。
 *
 * MediaRecorder や AnalyserNode から切り離した純粋な判定にしてある。
 * 時間と音量を入れると「まだ録る / もう切る」を返すだけなので、
 * 実機の音声なしで境界条件を検証できる。
 */

/** スロット長。発声開始がこれ以内なら有効回答 */
export const SLOT_MS = 5000;

/** 発声検出後、無音を待つ上限。これを過ぎたら喋り続けていても切る */
export const MAX_OVERRUN_MS = 3000;

/** この時間だけ連続で無音なら、発話が終わったとみなす */
export const SILENCE_HOLD_MS = 600;

export type SegmentState = {
  /** 出題開始からの、最初の発声を検出した時刻（ms）。未検出なら undefined */
  speechStartedAt?: number;
  /** 無音が続き始めた時刻（ms）。発声中なら undefined */
  silenceSince?: number;
  /** 確定済みか */
  closed: boolean;
  /** 確定した理由 */
  reason?: 'silence' | 'overrun' | 'no-speech';
};

export function createSegmentState(): SegmentState {
  return { closed: false };
}

/**
 * 1 フレーム分の観測を与えて状態を進める。
 *
 * elapsedMs は出題開始からの経過時間、speaking はそのフレームが
 * 発声とみなせる音量かどうか。
 */
export function advance(
  state: SegmentState,
  elapsedMs: number,
  speaking: boolean,
): SegmentState {
  if (state.closed) return state;

  if (state.speechStartedAt === undefined) {
    if (speaking) {
      // 最初の発声。この時刻が 5.00 秒以内かどうかで有効・無効が決まる。
      // 5 秒を過ぎた発声も記録して送る（無効と判定するのはサーバ）。
      return { ...state, speechStartedAt: elapsedMs, silenceSince: undefined };
    }
    // 発声のないままスロットが終わったら、そこで切る。
    // 無回答なので次スロットへ食い込ませる理由がない。
    if (elapsedMs >= SLOT_MS) {
      return { ...state, closed: true, reason: 'no-speech' };
    }
    return state;
  }

  // 発声を検出した後。まず上限を見る。喋り続けている間も切れるよう、
  // speaking の分岐より先に判定する必要がある（後ろに置くと、話し続ける
  // 限り上限に到達せず、次の問題の読み上げを録り続けてしまう）。
  if (elapsedMs >= SLOT_MS + MAX_OVERRUN_MS) {
    return { ...state, closed: true, reason: 'overrun' };
  }

  // 無音が続いたら、話し終わったとみなして切る。
  if (speaking) {
    return { ...state, silenceSince: undefined };
  }

  const silenceSince = state.silenceSince ?? elapsedMs;
  if (elapsedMs - silenceSince >= SILENCE_HOLD_MS) {
    return { ...state, silenceSince, closed: true, reason: 'silence' };
  }

  return { ...state, silenceSince };
}

/** 発声開始が有効回答の範囲内だったか。 */
export function isAccepted(state: SegmentState): boolean {
  return state.speechStartedAt !== undefined && state.speechStartedAt <= SLOT_MS;
}
