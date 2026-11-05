import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { api, tokenStore } from './api'
import type { Role, User } from './types'

interface AuthCtx {
  user: User | null
  login: (username: string, password: string) => Promise<User>
  logout: () => void
}

const Ctx = createContext<AuthCtx | null>(null)
const USER_KEY = 'tf_user'

export const HOME: Record<Role, string> = {
  hr_admin: '/hr',
  hiring_manager: '/hm',
  employee: '/me',
  leadership: '/insights',
}

export const ROLE_LABEL: Record<Role, string> = {
  hr_admin: 'HR Admin',
  hiring_manager: 'Hiring Manager',
  employee: 'Employee',
  leadership: 'Leadership',
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const raw = sessionStorage.getItem(USER_KEY)
    return raw && tokenStore.get() ? (JSON.parse(raw) as User) : null
  })

  const login = useCallback(async (username: string, password: string) => {
    const r = await api<{ token: string; user: User }>('/auth/login', { method: 'POST', json: { username, password } })
    tokenStore.set(r.token)
    sessionStorage.setItem(USER_KEY, JSON.stringify(r.user))
    setUser(r.user)
    return r.user
  }, [])

  const logout = useCallback(() => {
    tokenStore.clear()
    sessionStorage.removeItem(USER_KEY)
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useAuth outside AuthProvider')
  return c
}
