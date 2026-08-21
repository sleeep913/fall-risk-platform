export type DeviceOnlineStatus = 'online' | 'offline' | 'unknown'

export interface DeviceChannel {
  id: number
  channel_no: number
  name: string
  online_status: DeviceOnlineStatus
  is_encrypted: boolean | null
  video_level: number | null
  is_present: boolean
  last_online_at: string | null
  last_synced_at: string
}

export interface Device {
  id: number
  provider: string
  serial_masked: string
  name: string
  model: string | null
  online_status: DeviceOnlineStatus
  is_encrypted: boolean | null
  channel_count: number
  is_present: boolean
  last_online_at: string | null
  last_synced_at: string
  channels: DeviceChannel[]
}

export interface DeviceSyncResult {
  created: number
  updated: number
  missing: number
  channel_count: number
  synced_at: string
}

export interface DeviceStatus {
  id: number
  serial_masked: string
  online_status: DeviceOnlineStatus
  is_encrypted: boolean | null
  is_present: boolean
  last_online_at: string | null
  last_synced_at: string
}

export interface EzvizIntegrationStatus {
  configured: boolean
  token_cache: 'memory' | 'redis'
  token_status: 'not_configured' | 'not_cached' | 'valid' | 'refresh_required'
  token_expires_at: string | null
  token_refreshed_at: string | null
  device_count: number
  online_count: number
  last_synced_at: string | null
}
