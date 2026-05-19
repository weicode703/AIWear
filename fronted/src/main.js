/**
 * 应用入口（学生演示项目）
 *
 * 作用：创建 Vue 应用，注册插件，挂载到 index.html 的 #app。
 * 插件顺序注意：Pinia 必须在 Router 之前，因为路由守卫 beforeEach 里会调用 useAuthStore() 判断是否登录。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import './assets/styles/style.css'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

const app = createApp(App)
app.use(createPinia())   // 状态管理（登录态等），务必在 router 前
app.use(router)          // 路由（内部守卫会依赖 Pinia）
app.use(ElementPlus)     // UI 组件库
app.mount('#app')

