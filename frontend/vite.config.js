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
  preview: {
    port: 4173,
    headers: {
      'Cache-Control': 'no-cache',
    },
  },
  build: {
    outDir: resolve(__dirname, '../dist_vue'),
    emptyOutDir: true,
    chunkSizeWarningLimit: 700,
    cssCodeSplit: true,
    assetsInlineLimit: 4096,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // vue 核心: 所有页面都需要,合并为一个 chunk
          if (id.includes('node_modules/vue/') || id.includes('node_modules/@vue/')) {
            return 'vue-vendor'
          }
          if (id.includes('node_modules/vue-router')) {
            return 'vue-vendor'
          }
          if (id.includes('node_modules/pinia')) {
            return 'vue-vendor'
          }
          // axios 单独
          if (id.includes('node_modules/axios')) {
            return 'axios'
          }
          // vicons 图标
          if (id.includes('node_modules/@vicons/')) {
            return 'vicons'
          }
          // naive-ui: 不再手动拆分,让 Vite 按路由自动拆分
          // 每个页面只加载它用到的 naive-ui 组件
        },
      },
    },
  },
})
