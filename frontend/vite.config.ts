import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite dev server on 5173 with a proxy forwarding /api -> backend on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // API_PROXY lets docker-compose point at the `api` service; defaults
        // to the local backend for `npm run dev`.
        target: process.env.API_PROXY || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
