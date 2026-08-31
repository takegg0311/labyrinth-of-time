import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// render は body へ追記していくため、テストごとに片付ける。
// 残したままだと document から引く問い合わせが前のテストの DOM を拾う。
afterEach(cleanup);
