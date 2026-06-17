'use client'

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'

// ── Types ───────────────────────────────────────────────

interface User {
  username: string
  role: string
}

interface Brand {
  name: string
  copyright: string
  theme: string
  support_url: string
  support_name: string
  website_url: string
  website_name: string
  disclaimer: string
}

interface AuthState {
  user: User | null
  token: string | null
  isAdmin: boolean
  loading: boolean
  login: (token: string, user: User) => void
  logout: () => void
}

interface BrandState {
  brand: Brand
  setTheme: (t: string) => void
}

const defaultBrand: Brand = {
  name: 'szyg',
  copyright: '© 2024',
  theme: 'default',
  support_url: '',
  support_name: '',
  website_url: '',
  website_name: '',
  disclaimer: '',
}

// ── Auth Context ────────────────────────────────────────

const AuthContext = createContext<AuthState | null>(null)

function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedToken = localStorage.getItem('token')
      const savedUser = localStorage.getItem('user')
      if (savedToken) setToken(savedToken)
      if (savedUser) {
        try { setUser(JSON.parse(savedUser)) } catch {}
      }
    }
    setLoading(false)
  }, [])

  const login = useCallback((newToken: string, newUser: User) => {
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
    setToken(newToken)
    setUser(newUser)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('saved_credentials')
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, token, isAdmin: user?.role === 'admin', loading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    // Graceful fallback for tests/SSR — reads localStorage directly
    if (typeof window !== 'undefined') {
      const savedToken = localStorage.getItem('token')
      const savedUser = localStorage.getItem('user')
      let user = null
      if (savedUser) { try { user = JSON.parse(savedUser) } catch {} }
      return {
        user,
        token: savedToken,
        isAdmin: user?.role === 'admin',
        loading: false,
        login: (t, u) => { localStorage.setItem('token', t); localStorage.setItem('user', JSON.stringify(u)) },
        logout: () => { localStorage.removeItem('token'); localStorage.removeItem('user'); localStorage.removeItem('saved_credentials') },
      }
    }
    return { user: null, token: null, isAdmin: false, loading: true, login: () => {}, logout: () => {} }
  }
  return ctx
}

// ── Brand Context ────────────────────────────────────────

const BrandContext = createContext<BrandState | null>(null)

function BrandProvider({ children }: { children: ReactNode }) {
  const [brand, setBrand] = useState<Brand>(defaultBrand)

  useEffect(() => {
    // Dynamic import to avoid SSR circular deps
    import('@/lib/api').then(({ default: api }) => {
      api.get('/api/oem/config/default')
        .then(({ data }: { data: Partial<Brand> }) => {
          setBrand(prev => ({ ...prev, ...data }))
          if (data.theme) {
            document.documentElement.setAttribute('data-theme', data.theme)
          }
        })
        .catch(() => {})
    })
  }, [])

  const setTheme = useCallback((t: string) => {
    document.documentElement.setAttribute('data-theme', t)
    setBrand(prev => ({ ...prev, theme: t }))
  }, [])

  return (
    <BrandContext.Provider value={{ brand, setTheme }}>
      {children}
    </BrandContext.Provider>
  )
}

export function useBrand(): BrandState {
  const ctx = useContext(BrandContext)
  if (!ctx) {
    // Graceful fallback for tests/SSR
    return { brand: defaultBrand, setTheme: () => {} }
  }
  return ctx
}

// ── Combined Provider ────────────────────────────────────

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <BrandProvider>
        {children}
      </BrandProvider>
    </AuthProvider>
  )
}
