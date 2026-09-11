import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import App from './App.vue'
import router from './router'
import './shared/styles/main.scss'

const app = createApp(App)

// 全局错误兜底：组件渲染/setup 抛错时打出明确日志，
// 避免页面静默渲染成空白却查不到原因
app.config.errorHandler = (err, instance, info) => {
  console.error('[Sycamore 全局错误]', info, err)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
