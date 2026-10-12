import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// The built UI is served by the Python service (src/pngsvg_app/static). During `npm run dev`, API calls are
// proxied to a service started with: python -m pngsvg_app --port 8765 --token dev --no-browser
export default defineConfig({
  plugins: [svelte()],
  base: './',
  build: {
    outDir: '../../src/pngsvg_app/static',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true } },
  },
});
