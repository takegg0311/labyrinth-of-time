/**
 * 出題画面。
 *
 * 出題済みの問題文を上から積んでいく。文字送りはせず 1 問を一括表示する。
 * 正解・正誤・文字起こしはここでは一切出さない。
 */

import type { Result } from '../state/useGame';

type Props = {
  results: Result[];
  currentIndex: number;
};

export function QuizView({ results, currentIndex }: Props) {
  return (
    <ol className="quiz">
      {results.map((result, index) => {
        // 未出題の問題文は伏せる。先に見えると読み上げの意味がなくなる。
        const revealed = index <= currentIndex || currentIndex === -1;
        return (
          <li
            key={result.question.id}
            className={`quiz__row${index === currentIndex ? ' quiz__row--current' : ''}`}
          >
            <span className="quiz__no">{index + 1}</span>
            <span className="quiz__text">
              {revealed ? result.question.text : ''}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
