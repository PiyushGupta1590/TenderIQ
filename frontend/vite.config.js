import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // PDF processing + OCR + LLM can take several minutes.
        // Without these, Node's http-proxy resets the socket and
        // Vite throws "Error: read ECONNRESET".
        proxyTimeout: 660000,   // 11 min (> backend's 10-min hard cap)
        timeout: 660000,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.socket.setTimeout(660000)
          })
          proxy.on('error', (err, req, res) => {
            console.error('[proxy error]', err.message)
            if (!res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json' })
              res.end(JSON.stringify({ detail: 'Proxy error: ' + err.message }))
            }
          })
        },
      },
    },
  },
})
