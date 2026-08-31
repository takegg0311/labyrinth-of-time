import { QuizView } from './components/QuizView';
import { ReviewView } from './components/ReviewView';
import { useGame } from './state/useGame';

export function App() {
  const { phase, error, results, currentIndex, start, review, reset } = useGame();

  return (
    <main className="app">
      <header className="app__header">
        <h1 className="app__title">labyrinth of time</h1>
        <p className="app__lead">5 秒ごとに 1 問、1 分間で 12 問。声で答える。</p>
      </header>

      {error !== undefined && <p className="app__error">{error}</p>}

      <div className="app__controls">
        {phase === 'idle' && (
          <button type="button" className="button" onClick={() => void start()}>
            スタート
          </button>
        )}
        {phase === 'preparing' && <span className="app__status">準備中…</span>}
        {phase === 'playing' && (
          <span className="app__status app__status--live">
            出題中 {currentIndex + 1} / {results.length}
          </span>
        )}
        {phase === 'finished' && (
          <button type="button" className="button" onClick={() => void review()}>
            答え合わせ
          </button>
        )}
        {phase === 'review' && (
          <button type="button" className="button button--ghost" onClick={reset}>
            もう一度
          </button>
        )}
      </div>

      {(phase === 'playing' || phase === 'finished') && (
        <QuizView results={results} currentIndex={currentIndex} />
      )}
      {phase === 'review' && <ReviewView results={results} />}
    </main>
  );
}
