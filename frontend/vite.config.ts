import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5085',
        changeOrigin: true,
      },
      '/ml': {
        target: 'http://localhost:5085',
        changeOrigin: true,
      },
    },
  },
});
