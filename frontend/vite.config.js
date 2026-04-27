import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Dev/preview proxy: by default, Vite forwards backend routes to
// http://127.0.0.1:8000 so the browser sees same-origin and avoids CORS.
// Override the upstream with VITE_API_PROXY_TARGET in .env if needed.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = (env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000').replace(
    /\/+$/,
    '',
  );
  const proxy = {
    '/api': { target, changeOrigin: true },
    '/health': { target, changeOrigin: true },
    '/test-console': { target, changeOrigin: true },
    '/static': { target, changeOrigin: true },
  };
  return {
    plugins: [react()],
    server: { host: '127.0.0.1', port: 5173, proxy },
    preview: { host: '127.0.0.1', port: 4173, proxy },
  };
});
