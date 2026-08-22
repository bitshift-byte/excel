import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { setUnauthorizedHandler } from './api'
import './styles/global.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

// 不再全局注册 Naive UI 组件
// 各 .vue 文件通过 import { NXxx } from 'naive-ui' 按需引入
// Vite 会自动按路由拆分,登录页只加载它用到的组件

// 设置未认证处理：401 时跳转登录页（去重，避免重复跳转）并清理本地用户状态
setUnauthorizedHandler(() => {
  if (router.currentRoute.value.name === 'login') return
  localStorage.removeItem('user')
  router.push({ name: 'login' })
})

app.use(router)
app.mount('#app')
