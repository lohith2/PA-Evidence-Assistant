import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    historyApiFallback: true,
    proxy: {
      '/appeals/': 'http://localhost:8000',
      '/cases/': 'http://localhost:8000',
      '/eval': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
    },
  },
})
