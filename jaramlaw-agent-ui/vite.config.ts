import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modifyâfile watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {
        /* 산출물·테스트 부산물은 감시하지 않는다. feature-coverage.spec 가 실행 도중
           `npm run build` 로 dist/ 를 다시 쓰는데, 그때 dev 서버가 리로드를 걸어
           그 시점에 진행 중이던 다른 테스트의 로그인 상태가 날아갔다 (2026-08-12).
           빌드 결과물은 dev 서버가 읽지도 않으므로 감시할 이유가 없다. */
        ignored: ['**/dist/**', '**/test-results/**', '**/playwright-report/**', '**/.playwright-data/**'],
      },
    },
  };
});
