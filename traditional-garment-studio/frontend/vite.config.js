import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 代理指向 FastAPI 后端（联调时启用，mock 模式下不生效）
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.GARMENT_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/static': { target: process.env.GARMENT_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
