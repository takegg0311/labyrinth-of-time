import { describe, expect, it, vi, afterEach } from 'vitest';
import { fetchQuestions, fetchAnswers } from './api';

const origFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = origFetch; });

/** Vite プロキシがバックエンド未起動時に返す応答（実測: 500 / 本文空） */
function proxyDown() {
  globalThis.fetch = vi.fn(async () => new Response('', { status: 500 })) as never;
}

describe('バックエンド未起動の案内', () => {
  it('プロキシの 500（本文空）は起動手順を案内する', async () => {
    proxyDown();
    await expect(fetchQuestions()).rejects.toThrow(/バックエンドに接続できません/);
    await expect(fetchQuestions()).rejects.toThrow(/uvicorn app\.main:app --port 8000/);
  });

  it('答え合わせでも同じ案内を出す', async () => {
    proxyDown();
    await expect(fetchAnswers()).rejects.toThrow(/バックエンドに接続できません/);
  });

  it('接続そのものが失敗した場合も案内する', async () => {
    globalThis.fetch = vi.fn(async () => { throw new TypeError('Failed to fetch'); }) as never;
    await expect(fetchQuestions()).rejects.toThrow(/バックエンドに接続できません/);
  });

  it('バックエンドが返した 500 は取り違えない', async () => {
    // FastAPI は本文に JSON を載せるため、空本文と区別できる
    globalThis.fetch = vi.fn(async () =>
      new Response('{"detail":"内部エラー"}', { status: 500 })) as never;
    const err = await fetchQuestions().then(
      () => new Error('エラーになるはずが成功した'),
      (cause: Error) => cause,
    );
    expect(err.message).toContain('問題を取得できませんでした (500)');
    expect(err.message).not.toContain('バックエンドに接続できません');
  });

  it('404 は通常のエラーとして扱う', async () => {
    globalThis.fetch = vi.fn(async () => new Response('', { status: 404 })) as never;
    await expect(fetchQuestions()).rejects.toThrow(/問題を取得できませんでした \(404\)/);
  });
});
