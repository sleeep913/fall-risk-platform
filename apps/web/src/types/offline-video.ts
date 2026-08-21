export type OfflineVideoOrigin = 'public_dataset' | 'self_recorded' | 'synthetic' | 'other'
export type OfflineVideoLabel = 'fall' | 'adl' | 'near_fall' | 'unknown'

export interface OfflineVideo {
  id: number
  relative_path: string
  file_name: string
  display_name: string
  dataset_name: string | null
  origin: OfflineVideoOrigin
  label: OfflineVideoLabel
  media_type: string
  size_bytes: number
  source_url: string | null
  license_note: string | null
  is_available: boolean
  file_modified_at: string
  last_scanned_at: string
  created_at: string
  updated_at: string
  requires_transcoding: boolean
}

export interface OfflineVideoLibraryStatus {
  root_hint: string
  supported_extensions: string[]
  total_count: number
  available_count: number
  labeled_count: number
  dataset_count: number
  last_scanned_at: string | null
  inference_enabled: boolean
  transcoding_enabled: boolean
}

export interface OfflineVideoScanResult {
  created: number
  updated: number
  missing: number
  total: number
  scanned_at: string
}

export interface OfflineVideoUpdate {
  display_name?: string | null
  dataset_name?: string | null
  origin?: OfflineVideoOrigin
  label?: OfflineVideoLabel
  source_url?: string | null
  license_note?: string | null
}

export interface OfflineVideoPlaybackTicket {
  url: string
  expires_at: string
  transcoded: boolean
}
