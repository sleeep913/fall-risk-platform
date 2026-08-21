import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as offlineVideosApi from '@/api/offline-videos'
import { useOfflineVideosStore } from '@/stores/offline-videos'
import type { OfflineVideo } from '@/types/offline-video'

vi.mock('@/api/offline-videos', () => ({
  getOfflineVideos: vi.fn(),
  getOfflineVideoLibrary: vi.fn(),
  scanOfflineVideos: vi.fn(),
  updateOfflineVideo: vi.fn(),
  createPlaybackTicket: vi.fn(),
}))

const video: OfflineVideo = {
  id: 1,
  relative_path: 'GMDCSA-24/Fall/fall-01.mp4',
  file_name: 'fall-01.mp4',
  display_name: 'fall 01',
  dataset_name: 'GMDCSA-24',
  origin: 'public_dataset',
  label: 'fall',
  media_type: 'video/mp4',
  size_bytes: 1024,
  source_url: null,
  license_note: null,
  is_available: true,
  file_modified_at: '2026-08-15T03:00:00Z',
  last_scanned_at: '2026-08-15T03:00:00Z',
  created_at: '2026-08-15T03:00:00Z',
  updated_at: '2026-08-15T03:00:00Z',
  requires_transcoding: false,
}

const library = {
  root_hint: 'data/offline-videos',
  supported_extensions: ['.mp4', '.webm'],
  total_count: 1,
  available_count: 1,
  labeled_count: 1,
  dataset_count: 1,
  last_scanned_at: '2026-08-15T03:00:00Z',
  inference_enabled: false,
  transcoding_enabled: true,
}

describe('offline videos store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(offlineVideosApi.getOfflineVideos).mockResolvedValue([video])
    vi.mocked(offlineVideosApi.getOfflineVideoLibrary).mockResolvedValue(library)
  })

  it('loads the offline inventory and explicit inference status', async () => {
    const store = useOfflineVideosStore()

    await store.load()

    expect(store.availableVideos).toHaveLength(1)
    expect(store.videos[0].relative_path).toBe('GMDCSA-24/Fall/fall-01.mp4')
    expect(store.library?.inference_enabled).toBe(false)
  })

  it('reloads the inventory after scanning the configured directory', async () => {
    vi.mocked(offlineVideosApi.scanOfflineVideos).mockResolvedValue({
      created: 1,
      updated: 0,
      missing: 0,
      total: 1,
      scanned_at: '2026-08-15T03:00:00Z',
    })
    const store = useOfflineVideosStore()

    const result = await store.scan()

    expect(result.created).toBe(1)
    expect(store.lastScanResult).toEqual(result)
    expect(offlineVideosApi.getOfflineVideos).toHaveBeenCalledOnce()
    expect(store.scanning).toBe(false)
  })

  it('updates metadata without removing the video from the inventory', async () => {
    vi.mocked(offlineVideosApi.updateOfflineVideo).mockResolvedValue({
      ...video,
      display_name: '客厅跌倒样本',
    })
    const store = useOfflineVideosStore()
    await store.load()

    await store.update(1, { display_name: '客厅跌倒样本' })

    expect(store.videos[0].display_name).toBe('客厅跌倒样本')
    expect(store.savingVideoId).toBeNull()
  })

  it('requests a short-lived playback ticket for native video playback', async () => {
    vi.mocked(offlineVideosApi.createPlaybackTicket).mockResolvedValue({
      url: '/api/v1/offline-videos/1/stream?ticket=signed',
      expires_at: '2026-08-15T03:30:00Z',
      transcoded: false,
    })
    const store = useOfflineVideosStore()

    const ticket = await store.playback(1)

    expect(ticket.url).toContain('ticket=signed')
    expect(offlineVideosApi.createPlaybackTicket).toHaveBeenCalledWith(1)
  })
})
