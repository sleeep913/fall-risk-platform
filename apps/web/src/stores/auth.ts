import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as authApi from '@/api/auth'
import { setAccessToken } from '@/api/client'
import type { LoginPayload, User } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const initialized = ref(false)
  const loading = ref(false)

  const isAuthenticated = computed(() => user.value !== null)

  async function login(payload: LoginPayload): Promise<void> {
    loading.value = true
    try {
      const session = await authApi.login(payload)
      setAccessToken(session.access_token)
      user.value = session.user
      initialized.value = true
    } finally {
      loading.value = false
    }
  }

  async function restoreSession(): Promise<void> {
    if (initialized.value) return
    try {
      const session = await authApi.refreshSession()
      setAccessToken(session.access_token)
      user.value = session.user
    } catch {
      clearSession()
    } finally {
      initialized.value = true
    }
  }

  async function logout(): Promise<void> {
    try {
      if (user.value) await authApi.logout()
    } finally {
      clearSession()
      initialized.value = true
    }
  }

  function clearSession(): void {
    setAccessToken(null)
    user.value = null
  }

  return {
    user,
    initialized,
    loading,
    isAuthenticated,
    login,
    restoreSession,
    logout,
    clearSession,
  }
})

