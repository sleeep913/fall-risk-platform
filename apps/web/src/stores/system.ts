import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getHealth, getReadiness } from '@/api/system'
import type { HealthResponse, ReadinessResponse } from '@/types/system'

export const useSystemStore = defineStore('system', () => {
  const health = ref<HealthResponse | null>(null)
  const readiness = ref<ReadinessResponse | null>(null)
  const loading = ref(false)
  const checkedAt = ref<Date | null>(null)

  const isReady = computed(() => readiness.value?.status === 'ready')
  const isLightweight = computed(() => readiness.value?.mode === 'lightweight')

  async function check(): Promise<void> {
    loading.value = true
    try {
      const [healthResult, readinessResult] = await Promise.allSettled([
        getHealth(),
        getReadiness(),
      ])
      health.value = healthResult.status === 'fulfilled' ? healthResult.value : null
      if (readinessResult.status === 'fulfilled') {
        readiness.value = readinessResult.value
      } else {
        const response = (
          readinessResult.reason as {
            response?: { data?: ReadinessResponse }
          }
        ).response?.data
        readiness.value = response ?? null
      }
      checkedAt.value = new Date()
    } finally {
      loading.value = false
    }
  }

  return { health, readiness, loading, checkedAt, isReady, isLightweight, check }
})
