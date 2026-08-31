import { describe, expect, it } from 'vitest';
import {
  MAX_OVERRUN_MS,
  SILENCE_HOLD_MS,
  SLOT_MS,
  advance,
  createSegmentState,
  isAccepted,
  type SegmentState,
} from './segment';

/** フレーム列を流し込む。[経過時間, 発声中か] の並び */
function run(frames: [number, boolean][]): SegmentState {
  return frames.reduce(
    (state, [elapsed, speaking]) => advance(state, elapsed, speaking),
    createSegmentState(),
  );
}

describe('セグメントの切り出し', () => {
  it('発声がないままスロットが終われば切る', () => {
    const state = run([
      [1000, false],
      [3000, false],
      [SLOT_MS, false],
    ]);

    expect(state.closed).toBe(true);
    expect(state.reason).toBe('no-speech');
    expect(isAccepted(state)).toBe(false);
  });

  it('発声後に無音が続けば切る', () => {
    const state = run([
      [1000, true],
      [1500, false],
      [1500 + SILENCE_HOLD_MS, false],
    ]);

    expect(state.closed).toBe(true);
    expect(state.reason).toBe('silence');
    expect(state.speechStartedAt).toBe(1000);
  });

  it('短い無音では切らない', () => {
    const state = run([
      [1000, true],
      [1200, false],
      [1400, true], // 言い直し
      [1600, true],
    ]);

    expect(state.closed).toBe(false);
    expect(state.silenceSince).toBeUndefined();
  });

  describe('5秒目の直前に喋り始めた場合', () => {
    it('スロットを越えて録り続ける', () => {
      // 4.9 秒で喋り始め、5 秒を越えて話し続ける
      const state = run([
        [4900, true],
        [SLOT_MS, true],
        [5500, true],
      ]);

      expect(state.closed).toBe(false);
      expect(isAccepted(state)).toBe(true);
    });

    it('話し終われば次スロットの途中でも切る', () => {
      const state = run([
        [4900, true],
        [5500, true],
        [5800, false],
        [5800 + SILENCE_HOLD_MS, false],
      ]);

      expect(state.closed).toBe(true);
      expect(state.reason).toBe('silence');
      expect(isAccepted(state)).toBe(true);
    });

    it('喋り続けても上限で切る', () => {
      const state = run([
        [4900, true],
        [6000, true],
        [SLOT_MS + MAX_OVERRUN_MS, true],
      ]);

      expect(state.closed).toBe(true);
      expect(state.reason).toBe('overrun');
    });
  });

  describe('有効回答の境界', () => {
    it('5.00秒ちょうどの発声は有効', () => {
      const state = run([[SLOT_MS, true]]);

      expect(isAccepted(state)).toBe(true);
    });

    it('5.00秒を過ぎた発声は無効', () => {
      // スロット内が無音なら no-speech で切れるため、
      // 5 秒超の発声はそもそもこのセグメントには入らない
      const state = run([
        [4000, false],
        [SLOT_MS, false],
      ]);

      expect(state.reason).toBe('no-speech');
      expect(isAccepted(state)).toBe(false);
    });

    it('発声開始が5秒超なら記録しても無効扱い', () => {
      // 判定そのものはサーバが行うが、フロント側の isAccepted も
      // 同じ境界で揃えておく
      const state: SegmentState = { speechStartedAt: 5000.1, closed: true };

      expect(isAccepted(state)).toBe(false);
    });
  });
});
