import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as systemApi from '@/api/system'
import { useSystemStore } from '@/stores/system'

vi.mock('@/api/system', () => ({
  getHealth: vi.fn(),
  getReadiness: vi.fn(),
}))

describe('system store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('keeps dependency details when the platform is not ready', async () => {
    vi.mocked(systemApi.getHealth).mockResolvedValue({
      status: 'ok',
      service: 'Fall Risk Platform',
      version: '0.1.0',
      timestamp: '2026-08-07T00:00:00Z',
    })
    vi.mocked(systemApi.getReadiness).mockResolvedValue({
      status: 'not_ready',
      mode: 'full',
      checks: {
        database: { status: 'ok' },
        redis: { status: 'error', detail: 'unavailable' },
        minio: { status: 'error', detail: 'unavailable' },
      },
      timestamp: '2026-08-07T00:00:00Z',
    })
    const store = useSystemStore()

    await store.check()

    expect(store.isReady).toBe(false)
    expect(store.readiness?.checks.database.status).toBe('ok')
    expect(store.readiness?.checks.redis.status).toBe('error')
    expect(store.checkedAt).toBeInstanceOf(Date)
  })

  it('recognizes the no-Docker lightweight mode', async () => {
    vi.mocked(systemApi.getHealth).mockResolvedValue({
      status: 'ok',
      service: 'Fall Risk Platform',
      version: '0.1.0',
      timestamp: '2026-08-11T00:00:00Z',
    })
    vi.mocked(systemApi.getReadiness).mockResolvedValue({
      status: 'ready',
      mode: 'lightweight',
      checks: {
        database: { status: 'ok' },
        redis: { status: 'disabled', detail: 'disabled_in_local_lightweight_mode' },
        minio: { status: 'disabled', detail: 'disabled_in_local_lightweight_mode' },
      },
      timestamp: '2026-08-11T00:00:00Z',
    })
    const store = useSystemStore()

    await store.check()

    expect(store.isReady).toBe(true)
    expect(store.isLightweight).toBe(true)
    expect(store.readiness?.checks.redis.status).toBe('disabled')
  })
})
