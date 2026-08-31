/**
 * マイク録音と発声検出。
 *
 * 12 問分を 1 本の MediaRecorder で録り続け、スロットごとに
 * セグメントを切り出す方式は取らない。MediaRecorder が吐く chunk の
 * 境界は指定した時刻と一致せず、WebM のヘッダも先頭 chunk にしか
 * 付かないため、途中で切った断片は単体でデコードできない。
 *
 * 代わりに、スロットごとに MediaRecorder を起動・停止する。
 * 1 問 1 ファイルとして完結するので、そのまま STT へ送れる。
 *
 * 発声検出は AnalyserNode の RMS で行い、判定そのものは segment.ts が持つ。
 */

import {
  advance,
  createSegmentState,
  isAccepted,
  type SegmentState,
} from './segment';

/** RMS がこの値を超えたフレームを発声とみなす */
const SPEECH_THRESHOLD = 0.02;

/** 音量を見る間隔（ms） */
const POLL_MS = 50;

export type Segment = {
  audio: Blob;
  /** 出題開始から最初の発声までの経過時間（ms）。未検出なら undefined */
  speechOffsetMs?: number;
  accepted: boolean;
};

export type Recorder = {
  /** 1 問分を録る。セグメントが確定したら解決する */
  record: () => Promise<Segment>;
  close: () => void;
};

/** マイクを開いて録音器を作る。呼び出し側で権限エラーを扱う。 */
export async function createRecorder(): Promise<Recorder> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      // 自動ゲイン調整は無音時のノイズを持ち上げ、発声検出を誤らせる
      autoGainControl: false,
    },
  });

  const context = new AudioContext();
  const analyser = context.createAnalyser();
  analyser.fftSize = 1024;
  context.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);

  /** 現在のフレームが発声とみなせるか */
  const isSpeaking = (): boolean => {
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (const value of samples) sum += value * value;
    return Math.sqrt(sum / samples.length) > SPEECH_THRESHOLD;
  };

  return {
    record() {
      return new Promise<Segment>((resolve, reject) => {
        const chunks: Blob[] = [];
        let recorder: MediaRecorder;
        try {
          recorder = new MediaRecorder(stream);
        } catch (error) {
          reject(error);
          return;
        }

        const startedAt = performance.now();
        let state: SegmentState = createSegmentState();
        let poll: ReturnType<typeof setInterval>;

        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) chunks.push(event.data);
        };

        recorder.onstop = () => {
          clearInterval(poll);
          resolve({
            audio: new Blob(chunks, { type: recorder.mimeType }),
            speechOffsetMs: state.speechStartedAt,
            accepted: isAccepted(state),
          });
        };

        recorder.onerror = () => {
          clearInterval(poll);
          reject(new Error('録音に失敗しました。'));
        };

        recorder.start();

        poll = setInterval(() => {
          state = advance(state, performance.now() - startedAt, isSpeaking());
          if (state.closed && recorder.state !== 'inactive') {
            recorder.stop();
          }
        }, POLL_MS);
      });
    },

    close() {
      for (const track of stream.getTracks()) track.stop();
      void context.close();
    },
  };
}
