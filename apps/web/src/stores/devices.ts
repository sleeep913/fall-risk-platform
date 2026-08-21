import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as devicesApi from '@/api/devices'
import type { Device, DeviceSyncResult, EzvizIntegrationStatus } from '@/types/device'

export const useDevicesStore = defineStore('devices', () => {
  const devices = ref<Device[]>([])
  const integration = ref<EzvizIntegrationStatus | null>(null)
  const lastSyncResult = ref<DeviceSyncResult | null>(null)
  const loading = ref(false)
  const syncing = ref(false)
  const refreshingDeviceId = ref<number | null>(null)

  const onlineCount = computed(
    () => devices.value.filter((device) => device.online_status === 'online').length,
  )

  async function load(): Promise<void> {
    loading.value = true
    try {
      const [deviceList, status] = await Promise.all([
        devicesApi.getDevices(),
        devicesApi.getEzvizIntegration(),
      ])
      devices.value = deviceList
      integration.value = status
    } finally {
      loading.value = false
    }
  }

  async function sync(): Promise<DeviceSyncResult> {
    syncing.value = true
    try {
      const result = await devicesApi.syncDevices()
      lastSyncResult.value = result
      await load()
      return result
    } finally {
      syncing.value = false
    }
  }

  async function refreshStatus(deviceId: number): Promise<void> {
    refreshingDeviceId.value = deviceId
    try {
      const status = await devicesApi.refreshDeviceStatus(deviceId)
      const device = devices.value.find((item) => item.id === deviceId)
      if (device) {
        device.online_status = status.online_status
        device.is_encrypted = status.is_encrypted
        device.is_present = status.is_present
        device.last_online_at = status.last_online_at
        device.last_synced_at = status.last_synced_at
      }
    } finally {
      refreshingDeviceId.value = null
    }
  }

  return {
    devices,
    integration,
    lastSyncResult,
    loading,
    syncing,
    refreshingDeviceId,
    onlineCount,
    load,
    sync,
    refreshStatus,
  }
})
