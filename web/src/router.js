import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from './components/AppLayout.vue'

const SuperAgent = () => import('./pages/SuperAgent.vue')

const routes = [
  { path: '/login', redirect: '/' },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', redirect: '/super-agent' },
      { path: 'super-agent', component: SuperAgent, meta: { title: '超级员工', fullBleed: true } },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - szyg`
  }
  next()
})

export default router
