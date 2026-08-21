import { apiClient } from '@/api/client'
import type {
  PackageActivation,
  PackageActivationRequest,
  PackageEntitlementSummary,
  PackageSlot,
} from '@/types/device-package'

export async function getPackageSlots(): Promise<PackageSlot[]> {
  const { data } = await apiClient.get<PackageSlot[]>('/admin/ezviz/packages')
  return data
}

export async function getPackageEntitlements(): Promise<PackageEntitlementSummary> {
  const { data } = await apiClient.get<PackageEntitlementSummary>(
    '/admin/ezviz/packages/entitlements',
  )
  return data
}

export async function activatePackage(
  request: PackageActivationRequest,
): Promise<PackageActivation> {
  const { data } = await apiClient.post<PackageActivation>(
    '/admin/ezviz/packages/activate',
    request,
  )
  return data
}
