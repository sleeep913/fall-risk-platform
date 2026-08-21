export type DependencyState = 'ok' | 'error' | 'disabled'

export interface HealthResponse {
  status: 'ok'
  service: string
  version: string
  timestamp: string
}

export interface ReadinessResponse {
  status: 'ready' | 'not_ready'
  mode: 'full' | 'lightweight'
  checks: Record<string, { status: DependencyState; detail?: string }>
  timestamp: string
}
