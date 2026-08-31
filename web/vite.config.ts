/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 問題音声（quiz_data/）はリポジトリルートに置き、サーバ経由で配信する。
// dev では /api と /audio をバックエンドへ中継する。
export default defineConfig({
  plugins: [react()],
  test: {
    setupFiles: ['./src/test-setup.ts'],
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/audio': 'http://127.0.0.1:8000',
    },
  },
});
