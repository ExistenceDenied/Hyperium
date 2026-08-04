import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Business logic lives in @af/core (pure TS). Alias to its source so Vite/esbuild transpiles it.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@af/core': path.resolve(import.meta.dirname, '../core/src/index.ts') },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8930', changeOrigin: true },
    },
  },
})
