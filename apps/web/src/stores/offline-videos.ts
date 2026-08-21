import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as offlineVideosApi from '@/api/offline-videos'
import type {
  OfflineVideo,
  OfflineVideoLibraryStatus,
  OfflineVideoPlaybackTicket,
  OfflineVideoScanResult,
  OfflineVideoUpdate,
} from '@/types/offline-video'

export const useOfflineVideosStore = defineStore('offline-videos', () => {
  const videos = ref<OfflineVideo[]>([])
  const library = ref<OfflineVideoLibraryStatus | null>(null)
  const lastScanResult = ref<OfflineVideoScanResult | null>(null)
  const loading = ref(false)
  const scanning = ref(false)
  const savingVideoId = ref<number | null>(null)
  const preparingVideoId = ref<number | null>(null)

  const availableVideos = computed(() => videos.value.filter((video) => video.is_available))

  async function load(): Promise<void> {
    loading.value = true
    try {
      const [items, status] = await Promise.all([
        offlineVideosApi.getOfflineVideos(),
        offlineVideosApi.getOfflineVideoLibrary(),
      ])
      videos.value = items
      library.value = status
    } finally {
      loading.value = false
    }
  }

  async function scan(): Promise<OfflineVideoScanResult> {
    scanning.value = true
    try {
      const result = await offlineVideosApi.scanOfflineVideos()
      lastScanResult.value = result
      await load()
      return result
    } finally {
      scanning.value = false
    }
  }

  async function update(videoId: number, updateData: OfflineVideoUpdate): Promise<OfflineVideo> {
    savingVideoId.value = videoId
    try {
      const updated = await offlineVideosApi.updateOfflineVideo(videoId, updateData)
      const index = videos.value.findIndex((video) => video.id === videoId)
      if (index >= 0) videos.value[index] = updated
      library.value = await offlineVideosApi.getOfflineVideoLibrary()
      return updated
    } finally {
      savingVideoId.value = null
    }
  }

  async function playback(videoId: number): Promise<OfflineVideoPlaybackTicket> {
    preparingVideoId.value = videoId
    try {
      return await offlineVideosApi.createPlaybackTicket(videoId)
    } finally {
      preparingVideoId.value = null
    }
  }

  return {
    videos,
    library,
    lastScanResult,
    loading,
    scanning,
    savingVideoId,
    preparingVideoId,
    availableVideos,
    load,
    scan,
    update,
    playback,
  }
})
