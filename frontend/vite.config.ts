import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
const API_PORT = process.env.VITE_API_PORT ?? '8742'
const API_HOST = process.env.VITE_API_HOST ?? '127.0.0.1'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': `http://${API_HOST}:${API_PORT}`,
      '/ws': {
        target: `http://${API_HOST}:${API_PORT}`,
        ws: true,
      },
    },
  },
})
