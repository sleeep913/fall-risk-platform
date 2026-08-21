import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as authApi from '@/api/auth'
import { setAccessToken } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import type { TokenResponse } from '@/types/auth'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  refreshSession: vi.fn(),
  logout: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  setAccessToken: vi.fn(),
}))

const session: TokenResponse = {
  access_token: 'access-token',
  token_type: 'bearer',
  expires_in: 900,
  user: {
    id: 1,
    username: 'admin',
    display_name: '系统管理员',
    role: 'admin',
    is_active: true,
    created_at: '2026-08-07T00:00:00Z',
  },
}

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('stores an authenticated user after login', async () => {
    vi.mocked(authApi.login).mockResolvedValue(session)
    const store = useAuthStore()

    await store.login({ username: 'admin', password: 'a-password' })

    expect(setAccessToken).toHaveBeenCalledWith('access-token')
    expect(store.user?.username).toBe('admin')
    expect(store.isAuthenticated).toBe(true)
  })

  it('restores a session only once', async () => {
    vi.mocked(authApi.refreshSession).mockResolvedValue(session)
    const store = useAuthStore()

    await store.restoreSession()
    await store.restoreSession()

    expect(authApi.refreshSession).toHaveBeenCalledTimes(1)
    expect(store.initialized).toBe(true)
  })

  it('clears local state when refresh is rejected', async () => {
    vi.mocked(authApi.refreshSession).mockRejectedValue(new Error('expired'))
    const store = useAuthStore()

    await store.restoreSession()

    expect(setAccessToken).toHaveBeenCalledWith(null)
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })

  it('clears local state even when logout request fails', async () => {
    vi.mocked(authApi.login).mockResolvedValue(session)
    vi.mocked(authApi.logout).mockRejectedValue(new Error('offline'))
    const store = useAuthStore()
    await store.login({ username: 'admin', password: 'a-password' })

    await expect(store.logout()).rejects.toThrow('offline')
    expect(store.user).toBeNull()
    expect(setAccessToken).toHaveBeenLastCalledWith(null)
  })
})

