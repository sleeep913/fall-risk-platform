import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as devicesApi from '@/api/devices'
import { useDevicesStore } from '@/stores/devices'

vi.mock('@/api/devices', () => ({
  getDevices: vi.fn(),
  getEzvizIntegration: vi.fn(),
  syncDevices: vi.fn(),
  refreshDeviceStatus: vi.fn(),
}))

const device = {
  id: 1,
  provider: 'ezviz',
  serial_masked: 'ABC*****6789',
  name: '客厅摄像机',
  model: 'CS-C6N',
  online_status: 'online' as const,
  is_encrypted: true,
  channel_count: 1,
  is_present: true,
  last_online_at: '2026-08-13T03:00:00Z',
  last_synced_at: '2026-08-13T03:00:00Z',
  channels: [],
}

describe('devices store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(devicesApi.getDevices).mockResolvedValue([device])
    vi.mocked(devicesApi.getEzvizIntegration).mockResolvedValue({
      configured: true,
      token_cache: 'memory',
      token_status: 'valid',
      token_expires_at: '2026-08-13T05:00:00Z',
      token_refreshed_at: '2026-08-13T03:00:00Z',
      device_count: 1,
      online_count: 1,
      last_synced_at: '2026-08-13T03:00:00Z',
    })
  })

  it('loads synchronized devices and integration state', async () => {
    const store = useDevicesStore()

    await store.load()

    expect(store.devices).toHaveLength(1)
    expect(store.devices[0].serial_masked).toBe('ABC*****6789')
    expect(store.onlineCount).toBe(1)
    expect(store.integration?.token_cache).toBe('memory')
  })

  it('reloads device inventory after a successful sync', async () => {
    vi.mocked(devicesApi.syncDevices).mockResolvedValue({
      created: 1,
      updated: 0,
      missing: 0,
      channel_count: 1,
      synced_at: '2026-08-13T03:00:00Z',
    })
    const store = useDevicesStore()

    const result = await store.sync()

    expect(result.created).toBe(1)
    expect(store.lastSyncResult).toEqual(result)
    expect(devicesApi.getDevices).toHaveBeenCalledOnce()
    expect(devicesApi.getEzvizIntegration).toHaveBeenCalledOnce()
    expect(store.syncing).toBe(false)
  })

  it('updates one device after a live status query', async () => {
    vi.mocked(devicesApi.refreshDeviceStatus).mockResolvedValue({
      id: 1,
      serial_masked: 'ABC*****6789',
      online_status: 'offline',
      is_encrypted: false,
      is_present: true,
      last_online_at: '2026-08-13T03:00:00Z',
      last_synced_at: '2026-08-13T04:00:00Z',
    })
    const store = useDevicesStore()
    await store.load()

    await store.refreshStatus(1)

    expect(store.devices[0].online_status).toBe('offline')
    expect(store.devices[0].is_encrypted).toBe(false)
    expect(store.refreshingDeviceId).toBeNull()
  })
})
