import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as packageApi from '@/api/device-packages'
import type {
  PackageActivation,
  PackageActivationRequest,
  PackageEntitlementSummary,
  PackageSlot,
} from '@/types/device-package'

export const useDevicePackagesStore = defineStore('device-packages', () => {
  const slots = ref<PackageSlot[]>([])
  const entitlements = ref<PackageEntitlementSummary | null>(null)
  const loading = ref(false)
  const activatingSlot = ref<number | null>(null)

  const configuredCount = computed(() => slots.value.filter((slot) => slot.configured).length)
  const succeededCount = computed(
    () => slots.value.filter((slot) => slot.activation?.activation_status === 'succeeded').length,
  )

  async function load(): Promise<void> {
    loading.value = true
    try {
      const [loadedSlots, loadedEntitlements] = await Promise.all([
        packageApi.getPackageSlots(),
        packageApi.getPackageEntitlements(),
      ])
      slots.value = loadedSlots
      entitlements.value = loadedEntitlements
    } finally {
      loading.value = false
    }
  }

  async function activate(request: PackageActivationRequest): Promise<PackageActivation> {
    activatingSlot.value = request.package_slot
    try {
      const result = await packageApi.activatePackage(request)
      await load()
      return result
    } finally {
      activatingSlot.value = null
    }
  }

  return {
    slots,
    entitlements,
    loading,
    activatingSlot,
    configuredCount,
    succeededCount,
    load,
    activate,
  }
})
