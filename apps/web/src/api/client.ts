import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

import type { TokenResponse } from '@/types/auth'

interface RetryableRequest extends InternalAxiosRequestConfig {
  _retry?: boolean
}

let accessToken: string | null = null
let refreshPromise: Promise<string> | null = null

export const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 10_000,
  withCredentials: true,
})

export const systemClient = axios.create({
  baseURL: '/',
  timeout: 4_000,
  withCredentials: true,
})

export function setAccessToken(token: string | null): void {
  accessToken = token
}

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as RetryableRequest | undefined
    const url = request?.url ?? ''
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh')
    if (error.response?.status !== 401 || !request || request._retry || isAuthEndpoint) {
      return Promise.reject(error)
    }

    request._retry = true
    refreshPromise ??= apiClient
      .post<TokenResponse>('/auth/refresh')
      .then(({ data }) => {
        setAccessToken(data.access_token)
        return data.access_token
      })
      .finally(() => {
        refreshPromise = null
      })

    try {
      const token = await refreshPromise
      request.headers.Authorization = `Bearer ${token}`
      return apiClient(request)
    } catch (refreshError) {
      setAccessToken(null)
      return Promise.reject(refreshError)
    }
  },
)

