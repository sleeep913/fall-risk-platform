import { apiClient } from './client'

import type { LoginPayload, TokenResponse, User } from '@/types/auth'

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', payload)
  return data
}

export async function refreshSession(): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/refresh')
  return data
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>('/auth/me')
  return data
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout')
}

