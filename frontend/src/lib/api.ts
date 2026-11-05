// Typed API client: bearer auth, JSON, consistent error handling.
const TOKEN_KEY = 'tf_token'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (t: string) => sessionStorage.setItem(TOKEN_KEY, t),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let body = init.body
  if (init.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(init.json)
  }
  const res = await fetch(`/api${path}`, { ...init, headers, body })
  if (res.status === 401 && !path.startsWith('/auth/login')) {
    tokenStore.clear()
    window.location.assign('/login')
  }
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : j.detail?.message ?? JSON.stringify(j.detail ?? j)
    } catch { /* non-JSON error */ }
    throw new ApiError(res.status, msg)
  }
  return res.json() as Promise<T>
}

export const withToken = (path: string) => `/api${path}${path.includes('?') ? '&' : '?'}token=${encodeURIComponent(tokenStore.get() ?? '')}`
