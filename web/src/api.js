import axios from 'axios'

// ── Request interceptor: auto-attach JWT Bearer token ──
axios.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: 401 → clear auth & redirect to login ──
axios.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Utility: unified error message extraction ──
export function getErrorMessage(err, fallback = '请求失败') {
  return err?.response?.data?.detail || err?.message || fallback
}
