import { createRouter, createWebHistory } from 'vue-router'
import Login from './pages/Login.vue'
import AppLayout from './components/AppLayout.vue'
import Dashboard from './pages/Dashboard.vue'
import Tools from './pages/Tools.vue'
import Admin from './pages/Admin.vue'
import Hub from './pages/Hub.vue'
import Agents from './pages/Agents.vue'
import Publisher from './pages/Publisher.vue'
import Scheduler from './pages/Scheduler.vue'
import Platforms from './pages/Platforms.vue'

const routes = [
  // Login — standalone, no AppLayout wrapper
  { path: '/login', component: Login },
  // All other pages — wrapped in AppLayout with header/menu/footer
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: Dashboard, meta: { requiresAuth: true } },
      { path: 'tools', component: Tools, meta: { requiresAuth: true } },
      { path: 'tools/:category', component: Tools, meta: { requiresAuth: true } },
      { path: 'hub', component: Hub, meta: { requiresAuth: true } },
      { path: 'agents', component: Agents, meta: { requiresAuth: true } },
      { path: 'publisher', component: Publisher, meta: { requiresAuth: true } },
      { path: 'scheduler', component: Scheduler, meta: { requiresAuth: true } },
      { path: 'platforms', component: Platforms, meta: { requiresAuth: true } },
      { path: 'admin', component: Admin, meta: { requiresAuth: true, requiresAdmin: true } },
      { path: 'chat', component: () => import('./pages/Chat.vue'), meta: { requiresAuth: true } },
      { path: 'image', component: () => import('./pages/ImageGen.vue'), meta: { requiresAuth: true } },
      { path: 'video', component: () => import('./pages/VideoGen.vue'), meta: { requiresAuth: true } },
      { path: 'oem', component: () => import('./pages/OEM.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || 'null')

  if (to.meta.requiresAuth && !token) {
    return next('/login')
  }
  if (to.meta.requiresAdmin && user?.role !== 'admin') {
    return next('/dashboard')
  }
  next()
})

export default router
