import { apiClient } from '@/api/client'
import type {
  Device,
  DeviceStatus,
  DeviceSyncResult,
  EzvizIntegrationStatus,
} from '@/types/device'

export async function getDevices(): Promise<Device[]> {
  const { data } = await apiClient.get<Device[]>('/devices')
  return data
}

export async function getEzvizIntegration(): Promise<EzvizIntegrationStatus> {
  const { data } = await apiClient.get<EzvizIntegrationStatus>('/devices/integration')
  return data
}

export async function syncDevices(): Promise<DeviceSyncResult> {
  const { data } = await apiClient.post<DeviceSyncResult>('/devices/sync')
  return data
}

export async function refreshDeviceStatus(deviceId: number): Promise<DeviceStatus> {
  const { data } = await apiClient.get<DeviceStatus>(`/devices/${deviceId}/status`)
  return data
}
