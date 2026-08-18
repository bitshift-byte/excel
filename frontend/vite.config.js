import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    // 防止浏览器强缓存 index.html：改完代码普通刷新(F5)即可拉到最新，无需 Ctrl+Shift+R 硬刷新
    headers: {
      'Cache-Control': 'no-cache',
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/login': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  // 生产预览模式同样禁止强缓存 index.html
  preview: {
    port: 4173,
    headers: {
      'Cache-Control': 'no-cache',
    },
  },
  build: {
    outDir: resolve(__dirname, '../dist_vue'),
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
  },
})
