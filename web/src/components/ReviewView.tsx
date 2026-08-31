/**
 * 答え合わせ画面。
 *
 * 1 行につき No. / 問題文 / 自分の回答 / 正解 / ○× を並べる。
 *
 * 判定が未着の行は「判定中…」と出し、到着した行から更新する。
 * 全問が揃うまで待たせると、1 問の STT が詰まっただけで何も見られなくなる。
 */

import type { Result } from '../state/useGame';

type Props = {
  results: Result[];
};

/** 自分の回答として表示する文字列 */
function transcriptLabel(result: Result): string {
  if (result.status === 'pending') return '判定中…';
  if (result.status === 'failed') return '判定に失敗';
  if (result.accepted === false) {
    // 5.00 秒を過ぎた発声、あるいは発声そのものが無かった
    return result.transcript ? `${result.transcript}（時間外）` : '（無回答）';
  }
  return result.transcript || '（無回答）';
}

function mark(result: Result): string {
  if (result.status !== 'done') return '';
  return result.correct ? '○' : '×';
}

export function ReviewView({ results }: Props) {
  const decided = results.filter((result) => result.status === 'done');
  const score = decided.filter((result) => result.correct).length;
  const pending = results.length - decided.length;

  return (
    <div className="review">
      <table className="review__table">
        <thead>
          <tr>
            <th>No.</th>
            <th>問題</th>
            <th>あなたの回答</th>
            <th>正解</th>
            <th aria-label="正誤" />
          </tr>
        </thead>
        <tbody>
          {results.map((result, index) => (
            <tr key={result.question.id}>
              <td className="review__no">{index + 1}</td>
              <td>{result.question.text}</td>
              <td
                className={
                  result.status === 'pending' ? 'review__transcript--pending' : undefined
                }
              >
                {transcriptLabel(result)}
              </td>
              <td className="review__answer">{result.answers?.join(' / ') ?? ''}</td>
              <td
                className={`review__mark${
                  result.correct ? ' review__mark--correct' : ''
                }`}
              >
                {mark(result)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="review__score">
        {score} / {results.length} 正解
        {pending > 0 ? `（${pending} 問を判定中）` : ''}
      </p>
    </div>
  );
}
