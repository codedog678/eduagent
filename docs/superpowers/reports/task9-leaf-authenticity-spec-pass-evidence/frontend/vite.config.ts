import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  cacheDir: '/tmp/m3-task9-leaf-spec-9efac2fb-3201-4499-9be6-a10cde0023e7/vite-cache',
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        learning: resolve(rootDir, 'index.html'),
        ops: resolve(rootDir, 'ops/index.html'),
      },
    },
  },
  server: {
    port: 51477,
    proxy: {
      '/ops-api': {
        target: 'http://localhost:8890',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/ops-api/, ''),
      },
      '/api/distributed': 'http://localhost:8890',
      '/api': 'http://localhost:8888',
      '/ws': { target: 'ws://localhost:8888', ws: true },
    },
  },
})
