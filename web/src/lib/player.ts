/**
 * 問題音声の再生。
 *
 * AudioContext で鳴らす。HTMLAudioElement では再生開始の遅延がばらつき、
 * 5 秒スロットの先頭を守れないため。あらかじめ全問をデコードしておき、
 * スロットの発火と同時に鳴らす。
 */

export type QuestionPlayer = {
  /** 事前デコード。出題開始前に呼ぶ */
  preload: (urls: string[]) => Promise<void>;
  play: (url: string) => void;
  /** 鳴っている音を止める */
  stopAll: () => void;
  close: () => Promise<void>;
};

export function createPlayer(): QuestionPlayer {
  const context = new AudioContext();
  const buffers = new Map<string, AudioBuffer>();
  let playing: AudioBufferSourceNode[] = [];

  return {
    async preload(urls) {
      // 出題中に取りに行くとネットワーク待ちでスロットの先頭がずれる。
      // 開始前にまとめて取得・デコードしておく。
      await Promise.all(
        urls.map(async (url) => {
          if (buffers.has(url)) return;
          const response = await fetch(url);
          if (!response.ok) {
            throw new Error(`音声を取得できませんでした: ${url}`);
          }
          buffers.set(url, await context.decodeAudioData(await response.arrayBuffer()));
        }),
      );
      // ユーザー操作きっかけで resume しないと、自動再生の制限で鳴らない
      if (context.state === 'suspended') await context.resume();
    },

    play(url) {
      const buffer = buffers.get(url);
      if (buffer === undefined) return;

      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(context.destination);
      source.onended = () => {
        playing = playing.filter((node) => node !== source);
      };
      source.start();
      playing.push(source);
    },

    stopAll() {
      for (const source of playing) {
        try {
          source.stop();
        } catch {
          // すでに停止済み。停止できていれば十分なので握りつぶす
        }
      }
      playing = [];
    },

    async close() {
      this.stopAll();
      await context.close();
    },
  };
}
