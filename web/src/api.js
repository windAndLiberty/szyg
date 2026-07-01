import axios from 'axios'

let isRefreshing = false
let refreshSubscribers = []

function subscribeTokenRefresh(cb) {
  refreshSubscribers.push(cb)
}

function onRefreshed(token) {
  refreshSubscribers.forEach(cb => cb(token))
  refreshSubscribers = []
}

async function autoLogin() {
  try {
    const { data } = await axios.post('/api/auth/login', {
      username: 'admin',
      password: 'admin123'
    })
    if (data.access_token) {
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user || { username: 'admin' }))
      return data.access_token
    }
  } catch (e) {
    console.error('Auto login failed:', e)
  }
  return null
}

// ── Request interceptor: auto-attach JWT Bearer token ──
axios.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: 401 → auto re-login ──
axios.interceptors.response.use(
  res => res,
  async err => {
    const originalRequest = err.config
    if (err.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise(resolve => {
          subscribeTokenRefresh(token => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(axios(originalRequest))
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const newToken = await autoLogin()
      isRefreshing = false

      if (newToken) {
        onRefreshed(newToken)
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return axios(originalRequest)
      }
    }
    return Promise.reject(err)
  }
)

// ── Utility: unified error message extraction ──
export function getErrorMessage(err, fallback = '请求失败') {
  return err?.response?.data?.detail || err?.message || fallback
}

// ── Export auto-login for app initialization ──
export { autoLogin }
