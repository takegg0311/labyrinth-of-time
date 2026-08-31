/**
 * 出題タイムライン。
 *
 * 5 秒 × 12 スロットの進行を、開始時刻からの絶対差分で駆動する。
 * setInterval で 5 秒を積み上げる方式は、1 回ごとの誤差が蓄積して
 * 終盤ほど実時間からずれるため使わない。
 *
 * 各スロットの発火時刻は「開始時刻 + index * 5000ms」で定まる。
 * タイマーは常に「次のスロットまでの残り時間」を実測して張り直すので、
 * 個々のタイマーが遅れても後続のスロットは定刻に戻る。
 */

export const SLOT_MS = 5000;
export const QUESTION_COUNT = 12;

export type TimelineHandlers = {
  /** スロット開始。index は 0 起点 */
  onSlot: (index: number, startedAt: number) => void;
  /** 全スロットの終了（最終問の 5 秒経過後） */
  onFinish: () => void;
};

export type Timeline = {
  /** 出題を止める。すでに止まっていれば何もしない */
  stop: () => void;
};

/**
 * 出題を開始する。
 *
 * now は現在時刻を返す関数。既定は performance.now で、テストから差し替える。
 * performance.now を使うのは、システム時刻の変更に影響されない単調増加の
 * 時計が要るため。
 */
export function startTimeline(
  handlers: TimelineHandlers,
  options: { count?: number; slotMs?: number; now?: () => number } = {},
): Timeline {
  const count = options.count ?? QUESTION_COUNT;
  const slotMs = options.slotMs ?? SLOT_MS;
  const now = options.now ?? (() => performance.now());

  const startedAt = now();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;

  // 次に発火すべきスロット。すでに発火した分は進める
  let next = 0;

  const scheduleNext = () => {
    if (stopped) return;

    if (next >= count) {
      // 最終問のスロットが終わるまで待ってから終了する
      const remaining = startedAt + count * slotMs - now();
      timer = setTimeout(() => {
        if (stopped) return;
        stopped = true;
        handlers.onFinish();
      }, Math.max(0, remaining));
      return;
    }

    // 絶対時刻との差分で待ち時間を決める。前のタイマーが遅れた分は
    // ここで吸収され、後続のスロットは定刻へ戻る。
    const dueAt = startedAt + next * slotMs;
    const wait = Math.max(0, dueAt - now());

    timer = setTimeout(() => {
      if (stopped) return;
      const index = next;
      next += 1;
      handlers.onSlot(index, startedAt + index * slotMs);
      scheduleNext();
    }, wait);
  };

  scheduleNext();

  return {
    stop: () => {
      stopped = true;
      if (timer !== undefined) clearTimeout(timer);
    },
  };
}
