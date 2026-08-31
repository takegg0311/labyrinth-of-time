import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { startTimeline } from './timeline';

describe('出題タイムライン', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  /** 偽の時計。fake timer の進みに追随させる */
  const clock = () => {
    let current = 0;
    return {
      now: () => current,
      advance: async (ms: number) => {
        // 1ms 刻みで進めると遅いので、タイマーの発火に合わせて進める
        current += ms;
        await vi.advanceTimersByTimeAsync(ms);
      },
    };
  };

  it('5秒ごとに12回発火して終了する', async () => {
    const c = clock();
    const slots: number[] = [];
    const onFinish = vi.fn();

    startTimeline(
      { onSlot: (index) => slots.push(index), onFinish },
      { now: c.now },
    );

    await c.advance(0);
    expect(slots).toEqual([0]);

    for (let i = 1; i < 12; i += 1) {
      await c.advance(5000);
    }
    expect(slots).toEqual([...Array(12).keys()]);
    expect(onFinish).not.toHaveBeenCalled();

    // 最終問の 5 秒が経過して終了
    await c.advance(5000);
    expect(onFinish).toHaveBeenCalledTimes(1);
  });

  it('各スロットの開始時刻は絶対時刻で決まる', async () => {
    const c = clock();
    const startedAts: number[] = [];

    startTimeline(
      { onSlot: (_index, startedAt) => startedAts.push(startedAt), onFinish: vi.fn() },
      { now: c.now },
    );

    await c.advance(0);
    for (let i = 1; i < 12; i += 1) await c.advance(5000);

    expect(startedAts).toEqual([...Array(12).keys()].map((i) => i * 5000));
  });

  it('タイマーが遅れても後続のスロットは定刻へ戻る', async () => {
    // setTimeout が毎回 200ms 遅れる状況を作る。素朴な積み上げなら
    // 12 問目で 2.4 秒ずれるが、絶対時刻で張り直せばずれない。
    const c = clock();
    const startedAts: number[] = [];

    startTimeline(
      { onSlot: (_i, startedAt) => startedAts.push(startedAt), onFinish: vi.fn() },
      { now: c.now },
    );

    await c.advance(200); // 1 問目が 200ms 遅れて発火
    for (let i = 1; i < 12; i += 1) {
      await c.advance(5000);
    }

    // 発火が遅れても、記録される開始時刻は理論値のまま
    expect(startedAts).toEqual([...Array(12).keys()].map((i) => i * 5000));
    expect(startedAts).toHaveLength(12);
  });

  it('stop すると以降は発火しない', async () => {
    const c = clock();
    const onSlot = vi.fn();
    const onFinish = vi.fn();

    const timeline = startTimeline({ onSlot, onFinish }, { now: c.now });
    await c.advance(0);
    expect(onSlot).toHaveBeenCalledTimes(1);

    timeline.stop();
    await c.advance(60000);

    expect(onSlot).toHaveBeenCalledTimes(1);
    expect(onFinish).not.toHaveBeenCalled();
  });
});
