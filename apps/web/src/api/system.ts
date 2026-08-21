import { systemClient } from './client'

import type { HealthResponse, ReadinessResponse } from '@/types/system'

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await systemClient.get<HealthResponse>('/health')
  return data
}

export async function getReadiness(): Promise<ReadinessResponse> {
  const { data } = await systemClient.get<ReadinessResponse>('/ready', {
    validateStatus: (status) => status === 200 || status === 503,
  })
  return data
}
