import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as packageApi from '@/api/device-packages'
import { useDevicePackagesStore } from '@/stores/device-packages'

vi.mock('@/api/device-packages', () => ({
  getPackageSlots: vi.fn(),
  getPackageEntitlements: vi.fn(),
  activatePackage: vi.fn(),
}))

const entitlements = {
  source: 'competition_notice' as const,
  package_slots_total: 5,
  configured_slot_count: 1,
  activated_slot_count: 0,
  validity_months: 6,
  coupon_redeemed: false,
  token_status: 'valid' as const,
  online_device_count: 0,
  activation_ready: false,
  blockers: ['no_online_devices' as const],
}

const activation = {
  id: 1,
  package_slot: 1,
  package_code_suffix: '0001',
  device_id: 1,
  device_name: '客厅摄像机',
  device_serial_masked: 'ABC*****6789',
  channel_no: 1,
  activation_status: 'succeeded' as const,
  official_code: '0',
  official_message: '激活成功',
  activated_at: '2026-08-18T05:00:00Z',
  activated_by: 1,
  retry_count: 0,
  created_at: '2026-08-18T05:00:00Z',
  updated_at: '2026-08-18T05:00:00Z',
}

describe('device packages store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(packageApi.getPackageSlots).mockResolvedValue([
      { slot: 1, configured: true, activation: null },
      { slot: 2, configured: false, activation: null },
    ])
    vi.mocked(packageApi.getPackageEntitlements).mockResolvedValue(entitlements)
  })

  it('loads configured package slots without package codes', async () => {
    const store = useDevicePackagesStore()

    await store.load()

    expect(store.slots).toHaveLength(2)
    expect(store.configuredCount).toBe(1)
    expect(store.entitlements).toEqual(entitlements)
    expect(JSON.stringify(store.slots)).not.toContain('sensitive-package-code')
  })

  it('activates a slot and reloads audit state', async () => {
    vi.mocked(packageApi.activatePackage).mockResolvedValue(activation)
    vi.mocked(packageApi.getPackageSlots)
      .mockResolvedValueOnce([{ slot: 1, configured: true, activation: null }])
      .mockResolvedValueOnce([{ slot: 1, configured: true, activation }])
    const store = useDevicePackagesStore()
    await store.load()

    const result = await store.activate({
      package_slot: 1,
      device_id: 1,
      channel_no: 1,
      confirmed: true,
    })

    expect(result.activation_status).toBe('succeeded')
    expect(store.succeededCount).toBe(1)
    expect(store.activatingSlot).toBeNull()
  })
})
