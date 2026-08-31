/** @vitest-environment jsdom */
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReviewView } from './ReviewView';
import type { Result } from '../state/useGame';

function makeResult(index: number, patch: Partial<Result> = {}): Result {
  return {
    question: {
      id: `20260820/${index}`,
      index,
      text: `問題${index}は？`,
      audioUrl: `/audio/20260820/${index}-20260820.wav`,
      duration: 3,
    },
    status: 'done',
    answers: [`答え${index}`],
    ...patch,
  };
}

/** n 行目（0 起点、ヘッダを除く）のセルを読む */
function row(index: number) {
  const body = document.querySelector('tbody');
  if (body === null) throw new Error('tbody がありません');
  return within(body).getAllByRole('row')[index].querySelectorAll('td');
}

describe('答え合わせ画面', () => {
  it('No. 問題文 回答 正解 正誤を並べる', () => {
    render(
      <ReviewView
        results={[makeResult(0, { transcript: '答え0', correct: true, accepted: true })]}
      />,
    );

    const cells = row(0);
    expect(cells[0]).toHaveTextContent('1');
    expect(cells[1]).toHaveTextContent('問題0は？');
    expect(cells[2]).toHaveTextContent('答え0');
    expect(cells[3]).toHaveTextContent('答え0');
    expect(cells[4]).toHaveTextContent('○');
  });

  it('未着の行は判定中と出す', () => {
    render(
      <ReviewView
        results={[
          makeResult(0, { status: 'pending' }),
          makeResult(1, { transcript: '答え1', correct: true, accepted: true }),
        ]}
      />,
    );

    expect(row(0)[2]).toHaveTextContent('判定中…');
    // 未着の行には正誤を出さない
    expect(row(0)[4]).toHaveTextContent('');
    // 届いている行はそのまま表示する
    expect(row(1)[2]).toHaveTextContent('答え1');
    expect(row(1)[4]).toHaveTextContent('○');
  });

  it('スコアは判定済みだけで数え、残りの件数を添える', () => {
    render(
      <ReviewView
        results={[
          makeResult(0, { transcript: '答え0', correct: true, accepted: true }),
          makeResult(1, { transcript: 'ちがう', correct: false, accepted: true }),
          makeResult(2, { status: 'pending' }),
        ]}
      />,
    );

    expect(screen.getByText(/1 \/ 3 正解/)).toBeDefined();
    expect(screen.getByText(/1 問を判定中/)).toBeDefined();
  });

  it('全問揃えば判定中の表示は消える', () => {
    render(
      <ReviewView
        results={[makeResult(0, { transcript: '答え0', correct: true, accepted: true })]}
      />,
    );

    expect(screen.queryByText(/判定中/)).toBeNull();
  });

  it('時間外の発声は無回答と区別して示す', () => {
    render(
      <ReviewView
        results={[
          makeResult(0, { transcript: 'エベレスト', correct: false, accepted: false }),
          makeResult(1, { transcript: '', correct: false, accepted: false }),
        ]}
      />,
    );

    expect(row(0)[2]).toHaveTextContent('エベレスト（時間外）');
    expect(row(1)[2]).toHaveTextContent('（無回答）');
  });

  it('判定に失敗した行はその旨を出す', () => {
    render(<ReviewView results={[makeResult(0, { status: 'failed' })]} />);

    expect(row(0)[2]).toHaveTextContent('判定に失敗');
  });

  it('正解は全行に表示する', () => {
    render(
      <ReviewView
        results={[makeResult(0, { status: 'pending' }), makeResult(1, { status: 'done' })]}
      />,
    );

    // 判定が未着でも正解そのものは出す
    expect(row(0)[3]).toHaveTextContent('答え0');
    expect(row(1)[3]).toHaveTextContent('答え1');
  });
});
