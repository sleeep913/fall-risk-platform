export type PackageActivationStatus = 'pending' | 'succeeded' | 'rejected' | 'failed'

export interface PackageActivation {
  id: number
  package_slot: number
  package_code_suffix: string
  device_id: number
  device_name: string
  device_serial_masked: string
  channel_no: number
  activation_status: PackageActivationStatus
  official_code: string | null
  official_message: string | null
  activated_at: string | null
  activated_by: number
  retry_count: number
  created_at: string
  updated_at: string
}

export interface PackageSlot {
  slot: number
  configured: boolean
  activation: PackageActivation | null
}

export type PackageEntitlementBlocker =
  | 'ezviz_credentials_not_configured'
  | 'token_not_authenticated'
  | 'no_package_codes_configured'
  | 'no_online_devices'

export interface PackageEntitlementSummary {
  source: 'competition_notice'
  package_slots_total: number
  configured_slot_count: number
  activated_slot_count: number
  validity_months: number
  coupon_redeemed: boolean
  token_status: 'not_configured' | 'not_cached' | 'valid' | 'refresh_required'
  online_device_count: number
  activation_ready: boolean
  blockers: PackageEntitlementBlocker[]
}

export interface PackageActivationRequest {
  package_slot: number
  device_id: number
  channel_no: number
  confirmed: true
}
