/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The API runs on :8002 (`examiner serve`); the dev server proxies /api to it.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://localhost:8002' } },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], css: false },
})
