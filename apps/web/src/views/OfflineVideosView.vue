<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { DataAnalysis, EditPen, Files, FolderOpened, Refresh, VideoPlay } from '@element-plus/icons-vue'
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElMessage,
  ElOption,
  ElProgress,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'

import { useOfflineVideosStore } from '@/stores/offline-videos'
import type {
  OfflineVideo,
  OfflineVideoLabel,
  OfflineVideoOrigin,
} from '@/types/offline-video'

const store = useOfflineVideosStore()
const selectedId = ref<number | null>(null)
const playbackUrl = ref<string | null>(null)
const playbackExpiresAt = ref<string | null>(null)
const playbackProgress = ref(0)
const playbackRate = ref(1)
const videoAspectRatio = ref('16 / 9')
const playbackError = ref<string | null>(null)
const videoElement = ref<HTMLVideoElement | null>(null)
const editVisible = ref(false)

interface OfflineVideoEditForm {
  display_name: string
  dataset_name: string
  origin: OfflineVideoOrigin
  label: OfflineVideoLabel
  source_url: string
  license_note: string
}

const editForm = reactive<OfflineVideoEditForm>({
  display_name: '',
  dataset_name: '',
  origin: 'other',
  label: 'unknown',
  source_url: '',
  license_note: '',
})

const selectedVideo = computed(
  () => store.videos.find((video) => video.id === selectedId.value) ?? null,
)

onMounted(() => {
  void loadLibrary()
})

async function loadLibrary(): Promise<void> {
  try {
    await store.load()
  } catch {
    ElMessage.error('离线视频库加载失败，请确认后端服务正常')
  }
}

async function handleScan(): Promise<void> {
  try {
    const result = await store.scan()
    ElMessage.success(
      `扫描完成：新增 ${result.created}，更新 ${result.updated}，缺失 ${result.missing}`,
    )
  } catch {
    ElMessage.error('目录扫描失败，请检查 data/offline-videos 是否可读')
  }
}

async function handlePlayback(videoRow: unknown): Promise<void> {
  const video = videoRow as OfflineVideo
  try {
    const ticket = await store.playback(video.id)
    selectedId.value = video.id
    playbackUrl.value = ticket.url
    playbackExpiresAt.value = ticket.expires_at
    playbackProgress.value = 0
    playbackError.value = null
    videoAspectRatio.value = '16 / 9'
    await nextTick()
    videoElement.value?.load()
    if (ticket.transcoded) {
      ElMessage.success('原视频已准备为浏览器兼容的 MP4，后续播放将复用缓存')
    }
  } catch (error: unknown) {
    ElMessage.error(readPlaybackError(error))
  }
}

function openEdit(videoRow: unknown): void {
  const video = videoRow as OfflineVideo
  selectedId.value = video.id
  editForm.display_name = video.display_name
  editForm.dataset_name = video.dataset_name ?? ''
  editForm.origin = video.origin
  editForm.label = video.label
  editForm.source_url = video.source_url ?? ''
  editForm.license_note = video.license_note ?? ''
  editVisible.value = true
}

async function saveMetadata(): Promise<void> {
  if (!selectedVideo.value || !editForm.display_name.trim()) {
    ElMessage.warning('显示名称不能为空')
    return
  }
  try {
    await store.update(selectedVideo.value.id, {
      display_name: editForm.display_name,
      dataset_name: editForm.dataset_name || null,
      origin: editForm.origin,
      label: editForm.label,
      source_url: editForm.source_url || null,
      license_note: editForm.license_note || null,
    })
    editVisible.value = false
    ElMessage.success('视频元数据已保存')
  } catch {
    ElMessage.error('元数据保存失败')
  }
}

function handleTimeUpdate(event: Event): void {
  const video = event.target as HTMLVideoElement
  playbackProgress.value = video.duration
    ? Math.min(100, Math.round((video.currentTime / video.duration) * 100))
    : 0
}

function applyPlaybackRate(): void {
  if (videoElement.value) videoElement.value.playbackRate = playbackRate.value
}

function handleLoadedMetadata(event: Event): void {
  const video = event.target as HTMLVideoElement
  if (video.videoWidth > 0 && video.videoHeight > 0) {
    videoAspectRatio.value = `${video.videoWidth} / ${video.videoHeight}`
  }
  applyPlaybackRate()
}

function handleVideoError(event: Event): void {
  const video = event.target as HTMLVideoElement
  const messages: Record<number, string> = {
    1: '视频加载被取消，请重新点击模拟运行。',
    2: '视频数据加载失败，请检查后端服务和临时播放地址。',
    3: '浏览器无法解码该视频，请重新生成兼容格式。',
    4: '浏览器不支持该视频格式或编码。',
  }
  playbackError.value = messages[video.error?.code ?? 0] ?? '视频播放失败，请查看浏览器控制台。'
}

function labelText(label: OfflineVideoLabel): string {
  return { fall: '跌倒', adl: '日常活动', near_fall: '近跌倒', unknown: '待标注' }[label]
}

function labelType(label: OfflineVideoLabel): 'danger' | 'success' | 'warning' | 'info' {
  return { fall: 'danger', adl: 'success', near_fall: 'warning', unknown: 'info' }[label] as
    | 'danger'
    | 'success'
    | 'warning'
    | 'info'
}

function originText(origin: OfflineVideoOrigin): string {
  return {
    public_dataset: '公开数据集',
    self_recorded: '自行采集',
    synthetic: '合成数据',
    other: '未确认',
  }[origin]
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

function formatDateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚未扫描'
}

function readPlaybackError(error: unknown): string {
  const detail = (
    error as { response?: { data?: { detail?: { code?: string; message?: string } | string } } }
  ).response?.data?.detail
  if (typeof detail === 'object' && detail?.code === 'video_unavailable') {
    return '视频文件已移动或删除，请重新扫描目录'
  }
  if (typeof detail === 'object' && detail?.code === 'video_transcode_failed') {
    return detail.message || '视频兼容格式转换失败，请检查源文件是否完整'
  }
  return '无法创建播放地址，请刷新后重试'
}
</script>

<template>
  <div class="offline-page page-container">
    <section class="offline-heading">
      <div>
        <p class="eyebrow">PHASE 02A · OFFLINE VIDEO SOURCE</p>
        <h1>离线视频模拟</h1>
        <p>使用公开数据集或已获授权的本地视频验证系统链路，与真实萤石设备数据明确分离。</p>
      </div>
      <div class="offline-heading__actions">
        <el-button :icon="Refresh" :loading="store.loading" @click="loadLibrary">
          刷新列表
        </el-button>
        <el-button type="primary" :icon="FolderOpened" :loading="store.scanning" @click="handleScan">
          扫描视频目录
        </el-button>
      </div>
    </section>

    <el-alert
      title="当前是离线模拟模式，不代表萤石平台实测"
      description="本阶段仅提供媒体登记与回放，AI 推理、风险评分和真实告警尚未启用。最终比赛验证仍需保留萤石云取流链路。"
      type="warning"
      :closable="false"
      show-icon
      class="offline-alert"
    />

    <section class="offline-metrics" aria-label="离线视频库概况">
      <article class="offline-metric">
        <el-icon><Files /></el-icon>
        <div><span>可用视频</span><strong>{{ store.library?.available_count ?? 0 }}</strong></div>
      </article>
      <article class="offline-metric">
        <el-icon><FolderOpened /></el-icon>
        <div><span>数据集</span><strong>{{ store.library?.dataset_count ?? 0 }}</strong></div>
      </article>
      <article class="offline-metric">
        <el-icon><EditPen /></el-icon>
        <div><span>已标注</span><strong>{{ store.library?.labeled_count ?? 0 }}</strong></div>
      </article>
      <article class="offline-metric">
        <el-icon><DataAnalysis /></el-icon>
        <div><span>AI 推理</span><strong class="offline-metric__disabled">未启用</strong></div>
      </article>
    </section>

    <section class="offline-workspace">
      <article class="panel offline-player-panel">
        <div class="panel__heading offline-panel__heading">
          <div>
            <span class="panel__kicker">LOCAL PLAYBACK</span>
            <h2>{{ selectedVideo?.display_name ?? '选择一个视频开始模拟' }}</h2>
          </div>
          <el-tag type="warning" effect="plain">离线来源</el-tag>
        </div>

        <div
          v-if="playbackUrl && selectedVideo"
          class="offline-player"
          :style="{ aspectRatio: videoAspectRatio }"
        >
          <video
            ref="videoElement"
            :src="playbackUrl"
            controls
            preload="metadata"
            @timeupdate="handleTimeUpdate"
            @loadedmetadata="handleLoadedMetadata"
            @error="handleVideoError"
          />
        </div>

        <el-alert
          v-if="playbackError"
          :title="playbackError"
          type="error"
          :closable="false"
          show-icon
          class="offline-playback-error"
        />
        <div v-if="!playbackUrl || !selectedVideo" class="offline-player offline-player--empty">
          <el-icon><VideoPlay /></el-icon>
          <strong>尚未选择回放视频</strong>
          <span>从下方列表选择“模拟运行”</span>
        </div>

        <div class="offline-playback-status">
          <div>
            <span>回放进度</span>
            <el-progress :percentage="playbackProgress" :stroke-width="7" />
          </div>
          <el-select v-model="playbackRate" aria-label="播放速度" @change="applyPlaybackRate">
            <el-option :value="0.5" label="0.5×" />
            <el-option :value="1" label="1.0× 实时" />
            <el-option :value="1.5" label="1.5×" />
            <el-option :value="2" label="2.0×" />
          </el-select>
        </div>
        <p v-if="playbackExpiresAt" class="offline-ticket-note">
          临时播放地址有效至 {{ formatDateTime(playbackExpiresAt) }}；过期后重新点击模拟运行即可。
        </p>
      </article>

      <article class="panel offline-guide-panel">
        <div class="panel__heading offline-panel__heading">
          <div>
            <span class="panel__kicker">DATASET WORKFLOW</span>
            <h2>导入方式</h2>
          </div>
        </div>
        <ol class="offline-steps">
          <li><i>1</i><div><strong>下载合规数据</strong><span>优先使用作者、高校或 Zenodo 官方来源。</span></div></li>
          <li><i>2</i><div><strong>放入本地目录</strong><span>{{ store.library?.root_hint ?? 'data/offline-videos' }}/数据集名称/标签/视频。</span></div></li>
          <li><i>3</i><div><strong>扫描并校对</strong><span>检查跌倒、日常活动、数据来源与许可说明。</span></div></li>
          <li><i>4</i><div><strong>模拟运行</strong><span>AVI、MKV、MOV 首次播放会自动生成兼容 MP4；后续直接复用。</span></div></li>
        </ol>
        <div class="offline-scan-note">
          <span>最近扫描</span>
          <strong>{{ formatDateTime(store.library?.last_scanned_at ?? null) }}</strong>
          <small>支持 {{ store.library?.supported_extensions.join('、') || '.mp4、.webm、.mov、.mkv、.avi' }}</small>
        </div>
      </article>
    </section>

    <section class="panel offline-table-panel">
      <div class="panel__heading offline-panel__heading">
        <div>
          <span class="panel__kicker">REGISTERED MEDIA</span>
          <h2>本地视频清单</h2>
        </div>
        <el-tag type="info" effect="plain">视频文件不会进入 Git</el-tag>
      </div>

      <el-table
        v-if="store.videos.length"
        v-loading="store.loading"
        :data="store.videos"
        row-key="id"
        class="offline-table"
      >
        <el-table-column prop="display_name" label="名称" min-width="170" />
        <el-table-column prop="dataset_name" label="数据集" min-width="130">
          <template #default="scope">{{ scope.row.dataset_name ?? '未分类' }}</template>
        </el-table-column>
        <el-table-column label="标签" width="105">
          <template #default="scope">
            <el-tag :type="labelType(scope.row.label)" size="small" effect="light">
              {{ labelText(scope.row.label) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="110">
          <template #default="scope">{{ originText(scope.row.origin) }}</template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="scope">{{ formatBytes(scope.row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column label="浏览器播放" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.requires_transcoding ? 'warning' : 'success'" size="small" effect="plain">
              {{ scope.row.requires_transcoding ? '首次转码' : '直接播放' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="文件状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_available ? 'success' : 'danger'" size="small" effect="plain">
              {{ scope.row.is_available ? '可用' : '已缺失' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="scope">
            <el-button
              text
              type="primary"
              :loading="store.preparingVideoId === scope.row.id"
              :disabled="!scope.row.is_available"
              @click="handlePlayback(scope.row)"
            >
              模拟运行
            </el-button>
            <el-button text :icon="EditPen" @click="openEdit(scope.row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-else description="目录中尚未登记视频。放入视频后点击“扫描视频目录”。" />
    </section>

    <el-dialog v-model="editVisible" title="修订视频元数据" width="560px">
      <el-form label-position="top">
        <div class="offline-edit-grid">
          <el-form-item label="显示名称" class="offline-edit-grid__wide">
            <el-input v-model="editForm.display_name" maxlength="200" />
          </el-form-item>
          <el-form-item label="数据集名称">
            <el-input v-model="editForm.dataset_name" maxlength="120" />
          </el-form-item>
          <el-form-item label="数据来源">
            <el-select v-model="editForm.origin">
              <el-option value="public_dataset" label="公开数据集" />
              <el-option value="self_recorded" label="自行采集" />
              <el-option value="synthetic" label="合成数据" />
              <el-option value="other" label="未确认" />
            </el-select>
          </el-form-item>
          <el-form-item label="动作标签">
            <el-select v-model="editForm.label">
              <el-option value="fall" label="跌倒" />
              <el-option value="adl" label="日常活动" />
              <el-option value="near_fall" label="近跌倒" />
              <el-option value="unknown" label="待标注" />
            </el-select>
          </el-form-item>
          <el-form-item label="官方来源地址" class="offline-edit-grid__wide">
            <el-input v-model="editForm.source_url" maxlength="500" placeholder="https://..." />
          </el-form-item>
          <el-form-item label="许可与引用说明" class="offline-edit-grid__wide">
            <el-input v-model="editForm.license_note" type="textarea" :rows="3" maxlength="1000" show-word-limit />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="store.savingVideoId === selectedVideo?.id"
          @click="saveMetadata"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
