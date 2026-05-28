import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite dev server on 5173 with a proxy forwarding /api -> backend on :8000.
export default defineConfig({
  plugins: [react()],
  // GitHub Pages serves a project site under /<repo>/. The Pages workflow sets
  // VITE_BASE=/Emodeler/; local dev/builds default to '/'.
  base: process.env.VITE_BASE || '/',
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
