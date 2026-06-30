import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/v1': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    }
  },
  build: {
    rollupOptions: {
      output: {
        // Split large vendor libs into separate chunks (Rolldown requires function)
        manualChunks(id) {
          if (id.includes('node_modules/element-plus') || id.includes('node_modules/@element-plus'))
            return 'vendor-element'
          if (id.includes('node_modules/vue') || id.includes('node_modules/pinia'))
            return 'vendor-vue'
          if (id.includes('node_modules/axios'))
            return 'vendor-axios'
        },
      },
    },
    chunkSizeWarningLimit: 500,
  },
})
