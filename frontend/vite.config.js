import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
    include: ['src/**/*.test.{js,jsx}']
  },
  server: {
    port: 5173,
    proxy: {
      '/auth': {
        target: 'http://localhost:8001',
        changeOrigin: true
      }
    }
  }
})
