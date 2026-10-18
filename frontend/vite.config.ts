import { fileURLToPath, URL } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import autoprefixer from 'autoprefixer'

const BUILD_ID_PATH = '/build_id.json'

/**
 * 本次构建的 ID —— 在**配置求值时**生成一次，进程活多久就固定多久。
 *
 * ⇒ 「dev server 重启」和「重新 build」都会换新 ID，而普通热更新**不会**。
 * 这正是探针需要的语义：它要回答的是「服务端手上的代码，还是我加载时那份吗」，
 * 而不是「刚刚有没有文件变动」。
 */
const BUILD_ID = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

/**
 * 版本探针——把 build ID 暴露成一个**普通 HTTP 资源**。
 *
 * 背景：dev server 重启不会让已打开的标签页换代码，若热更新连接又断了，
 * 标签页会**静默停在旧版本**上（2026-10-16 实况，界面完全看不出来）。
 * 前端定期取回 `/build_id.json` 与自己的 ID 比对，不一致就弹横幅提示刷新。
 *
 * 🔴 路径只有一条（`/build_id.json`）：dev 由中间件现给、build 由产物带上。
 *    刻意不为两种环境起两个名字 —— 那会制造「只在一种环境才通」的静默分叉。
 */
function buildIdPlugin(): Plugin {
  const body = JSON.stringify({ buildId: BUILD_ID })

  return {
    name: 'sycamore-build-id',
    configureServer(server) {
      // 直接注册（不返回函数）⇒ 挂在 Vite 内部中间件**之前**，不会被 HTML fallback 抢走
      server.middlewares.use(BUILD_ID_PATH, (_req, res) => {
        res.setHeader('Content-Type', 'application/json; charset=utf-8')
        // 这份答案必须永远是最新的，缓存住就等于探针失效
        res.setHeader('Cache-Control', 'no-store')
        res.end(body)
      })
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'build_id.json', source: body })
    },
  }
}

export default defineConfig({
  plugins: [vue(), vueDevTools(), buildIdPlugin()],
  define: {
    // 编译期替换成字符串字面量 ⇒ 每个页面从此记住「我是哪一次构建」
    __BUILD_ID__: JSON.stringify(BUILD_ID),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  css: {
    postcss: {
      plugins: [
        autoprefixer({
          overrideBrowserslist: ['last 2 versions', 'Safari >= 14'],
        }),
      ],
    },
  },
})
