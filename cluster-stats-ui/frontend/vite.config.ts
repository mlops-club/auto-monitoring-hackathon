import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(() => {
  const frontendPort = Number(process.env.FRONTEND_PORT ?? '5173')
  const backendPort = Number(process.env.BACKEND_PORT ?? '3000')

  return {
    build: {
      outDir: '../backend/src/cs_backend/static',
      emptyOutDir: true,
    },
    server: {
      host: '0.0.0.0',
      port: frontendPort,
      proxy: {
        '/api': `http://127.0.0.1:${backendPort}`,
        '/health': `http://127.0.0.1:${backendPort}`,
        '/openapi.json': `http://127.0.0.1:${backendPort}`,
      },
    },
    plugins: [react()],
  }
})
