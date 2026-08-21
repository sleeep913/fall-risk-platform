<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Connection, Key, Refresh, VideoCamera } from '@element-plus/icons-vue'
import {
  ElAlert,
  ElButton,
  ElEmpty,
  ElIcon,
  ElMessage,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'

import { useDevicesStore } from '@/stores/devices'
import type { DeviceOnlineStatus } from '@/types/device'

const devicesStore = useDevicesStore()

const lastSyncText = computed(() =>
  devicesStore.integration?.last_synced_at
    ? formatDateTime(devicesStore.integration.last_synced_at)
    : '尚未同步',
)

const tokenStatusText = computed(() => {
  const status = devicesStore.integration?.token_status
  return {
    not_configured: '未配置',
    not_cached: '等待首次认证',
    valid: '认证有效',
    refresh_required: '等待自动刷新',
  }[status ?? 'not_configured']
})

onMounted(() => {
  void loadDevices()
})

async function loadDevices(): Promise<void> {
  try {
    await devicesStore.load()
  } catch {
    ElMessage.error('设备数据加载失败，请确认后端服务正常')
  }
}

async function handleSync(): Promise<void> {
  try {
    const result = await devicesStore.sync()
    ElMessage.success(
      `同步完成：新增 ${result.created}，更新 ${result.updated}，通道 ${result.channel_count}`,
    )
  } catch (error: unknown) {
    ElMessage.error(readSyncError(error))
  }
}

async function handleRefreshStatus(deviceId: number): Promise<void> {
  try {
    await devicesStore.refreshStatus(deviceId)
    ElMessage.success('设备状态已更新')
  } catch (error: unknown) {
    ElMessage.error(readSyncError(error))
  }
}

function statusLabel(status: DeviceOnlineStatus): string {
  return { online: '在线', offline: '离线', unknown: '未知' }[status]
}

function statusType(status: DeviceOnlineStatus): 'success' | 'danger' | 'info' {
  return { online: 'success', offline: 'danger', unknown: 'info' }[status] as
    | 'success'
    | 'danger'
    | 'info'
}

function formatDateTime(value: string | null): string {
  if (!value) return '--'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function encryptionLabel(value: boolean | null): string {
  if (value === null) return '未知'
  return value ? '已加密' : '未加密'
}

function readSyncError(error: unknown): string {
  const detail = (
    error as {
      response?: { data?: { detail?: { code?: string; message?: string } | string } }
    }
  ).response?.data?.detail
  if (typeof detail === 'object' && detail?.code === 'ezviz_not_configured') {
    return '尚未配置萤石 AppKey 和 AppSecret，请先修改后端 .env 并重启 API'
  }
  if (typeof detail === 'object' && detail?.message) return detail.message
  if (typeof detail === 'string') return detail
  return '设备同步失败，请稍后重试并查看后端日志'
}
</script>

<template>
  <div class="devices-page page-container">
    <section class="devices-heading">
      <div>
        <p class="eyebrow">PHASE 02 · EZVIZ DEVICES</p>
        <h1>萤石设备管理</h1>
        <p>从服务端同步设备和通道状态，敏感平台凭证不会发送到浏览器。</p>
      </div>
      <div class="devices-heading__actions">
        <el-button :icon="Refresh" :loading="devicesStore.loading" @click="loadDevices">
          刷新本地数据
        </el-button>
        <el-button
          type="primary"
          :icon="Connection"
          :loading="devicesStore.syncing"
          :disabled="!devicesStore.integration?.configured"
          @click="handleSync"
        >
          同步萤石设备
        </el-button>
      </div>
    </section>

    <el-alert
      v-if="devicesStore.integration && !devicesStore.integration.configured"
      title="尚未配置萤石开放平台凭证"
      description="请在 services/api/.env 中配置 EZVIZ_APP_KEY 与 EZVIZ_APP_SECRET，重启 API 后再同步。凭证仅保留在后端。"
      type="warning"
      :closable="false"
      show-icon
      class="devices-alert"
    />

    <section class="device-metrics" aria-label="设备接入概况">
      <article class="device-metric">
        <el-icon><Key /></el-icon>
        <div><span>萤石认证</span><strong>{{ tokenStatusText }}</strong></div>
      </article>
      <article class="device-metric">
        <el-icon><VideoCamera /></el-icon>
        <div><span>已同步设备</span><strong>{{ devicesStore.integration?.device_count ?? 0 }}</strong></div>
      </article>
      <article class="device-metric">
        <el-icon><Connection /></el-icon>
        <div><span>在线设备</span><strong>{{ devicesStore.onlineCount }}</strong></div>
      </article>
      <article class="device-metric">
        <el-icon><Refresh /></el-icon>
        <div><span>最近同步</span><strong class="device-metric__time">{{ lastSyncText }}</strong></div>
      </article>
    </section>

    <section class="panel devices-panel">
      <div class="panel__heading devices-panel__heading">
        <div>
          <span class="panel__kicker">SYNCED INVENTORY</span>
          <h2>设备与通道</h2>
        </div>
        <el-tag type="info" effect="plain">
          Token 缓存：{{ devicesStore.integration?.token_cache === 'redis' ? 'Redis' : '本机内存' }}
        </el-tag>
      </div>

      <el-alert
        v-if="devicesStore.integration?.configured"
        :title="`Token 状态：${tokenStatusText}`"
        :description="devicesStore.integration.token_expires_at
          ? `最近获取：${formatDateTime(devicesStore.integration.token_refreshed_at)}；到期时间：${formatDateTime(devicesStore.integration.token_expires_at)}。页面不会返回 Token 正文。`
          : '首次同步设备时，后端会自动申请并缓存 accessToken；页面不会返回 Token 正文。'"
        :type="devicesStore.integration.token_status === 'valid' ? 'success' : 'info'"
        :closable="false"
        show-icon
        class="devices-alert"
      />

      <el-table
        v-if="devicesStore.devices.length"
        v-loading="devicesStore.loading"
        :data="devicesStore.devices"
        row-key="id"
        class="devices-table"
      >
        <el-table-column type="expand">
          <template #default="scope">
            <div class="channel-list">
              <div v-for="channel in scope.row.channels" :key="channel.id" class="channel-row">
                <div>
                  <strong>{{ channel.name }}</strong>
                  <span>通道 {{ channel.channel_no }} · {{ encryptionLabel(channel.is_encrypted) }}</span>
                </div>
                <el-tag :type="statusType(channel.online_status)" size="small" effect="light">
                  {{ statusLabel(channel.online_status) }}
                </el-tag>
              </div>
              <el-empty v-if="!scope.row.channels.length" description="该设备暂无同步通道" :image-size="54" />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="设备名称" min-width="160" />
        <el-table-column prop="serial_masked" label="设备序列号" min-width="150" />
        <el-table-column prop="model" label="型号" min-width="130">
          <template #default="scope">{{ scope.row.model ?? '--' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="scope">
            <el-tag
              :type="scope.row.is_present ? statusType(scope.row.online_status) : 'warning'"
              size="small"
              effect="light"
            >
              {{ scope.row.is_present ? statusLabel(scope.row.online_status) : '本次未发现' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="视频加密" width="100">
          <template #default="scope">{{ encryptionLabel(scope.row.is_encrypted) }}</template>
        </el-table-column>
        <el-table-column prop="channel_count" label="通道数" width="80" />
        <el-table-column label="最后同步" min-width="170">
          <template #default="scope">{{ formatDateTime(scope.row.last_synced_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="scope">
            <el-button
              text
              type="primary"
              :loading="devicesStore.refreshingDeviceId === scope.row.id"
              @click="handleRefreshStatus(scope.row.id)"
            >
              刷新状态
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-else
        :description="devicesStore.integration?.configured ? '尚未同步设备' : '配置萤石凭证后即可同步设备'"
      />
    </section>

    <p class="devices-privacy-note">
      页面仅展示脱敏设备序列号。AppSecret、完整 accessToken 与设备验证码不会通过本接口返回。
    </p>
  </div>
</template>
