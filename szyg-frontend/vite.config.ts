import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const backendUrl = `http://127.0.0.1:${Number(process.env.SZYG_DEV_BACKEND_PORT || 8000)}`

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      '/api': backendUrl,
      '/v1': backendUrl,
      '/health': backendUrl,
    },
  },
})

