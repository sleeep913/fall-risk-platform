import { apiClient } from '@/api/client'
import type {
  OfflineVideo,
  OfflineVideoLibraryStatus,
  OfflineVideoPlaybackTicket,
  OfflineVideoScanResult,
  OfflineVideoUpdate,
} from '@/types/offline-video'

export async function getOfflineVideos(): Promise<OfflineVideo[]> {
  const { data } = await apiClient.get<OfflineVideo[]>('/offline-videos')
  return data
}

export async function getOfflineVideoLibrary(): Promise<OfflineVideoLibraryStatus> {
  const { data } = await apiClient.get<OfflineVideoLibraryStatus>('/offline-videos/library')
  return data
}

export async function scanOfflineVideos(): Promise<OfflineVideoScanResult> {
  const { data } = await apiClient.post<OfflineVideoScanResult>('/offline-videos/scan')
  return data
}

export async function updateOfflineVideo(
  videoId: number,
  update: OfflineVideoUpdate,
): Promise<OfflineVideo> {
  const { data } = await apiClient.patch<OfflineVideo>(`/offline-videos/${videoId}`, update)
  return data
}

export async function createPlaybackTicket(
  videoId: number,
): Promise<OfflineVideoPlaybackTicket> {
  const { data } = await apiClient.post<OfflineVideoPlaybackTicket>(
    `/offline-videos/${videoId}/playback-ticket`,
    undefined,
    { timeout: 300_000 },
  )
  return data
}
