import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// In development the API runs on port 8000 and Vite proxies to it.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    proxy: { '/api': 'http://localhost:8000' },
  },
})
