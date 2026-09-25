import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/gridloop-api': { target: 'http://localhost:4173', rewrite: path => path.replace(/^\/gridloop-api/, '/api') },
      '/minesweeper-api': { target: 'http://localhost:4174', rewrite: path => path.replace(/^\/minesweeper-api/, '/api') },
    },
  },
});
