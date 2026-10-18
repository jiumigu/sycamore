import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import App from './App.vue'
import router from './router'
import { startBuildVersionWatch } from './shared/utils/buildVersion'
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

// 🔴 版本探针：让「这个页面在跑旧代码」自己现形。
//    背景：dev server 重启**不会**刷新已打开的标签页；热更新 WS 一断，
//    页面就静默停在旧版本上 —— 此时任何「已修好的 bug」都会以「还是不行」回来。
//    放在 mount 之后：横幅要往 body 里插，不需要也不能等着组件树。
startBuildVersionWatch()
