import './api.js'
import { autoLogin } from './api.js'
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './style.css'
import './tech-theme.css'

// Auto-login on app startup
autoLogin().catch(() => {})

const app = createApp(App)
app.use(router)
app.use(ElementPlus)
app.mount('#app')
