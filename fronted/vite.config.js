import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  /** 后端 API 地址，开发时将所有 /api 请求代理到此地址（可在 .env.development 中设置 PROXY_TARGET） */
  const proxyTarget = env.PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      open: true,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
