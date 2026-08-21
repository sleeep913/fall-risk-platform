<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Connection, Files, Lock, Refresh, Warning } from '@element-plus/icons-vue'
import { ElButton, ElIcon } from 'element-plus'

import StatusPill from '@/components/StatusPill.vue'
import { useAuthStore } from '@/stores/auth'
import { useDevicePackagesStore } from '@/stores/device-packages'
import { useDevicesStore } from '@/stores/devices'
import { useOfflineVideosStore } from '@/stores/offline-videos'
import { useSystemStore } from '@/stores/system'

const system = useSystemStore()
const auth = useAuthStore()
const devicePackages = useDevicePackagesStore()
const devices = useDevicesStore()
const offlineVideos = useOfflineVideosStore()

const dependencyLabels: Record<string, string> = {
  database: 'MySQL 数据库',
  redis: 'Redis 缓存',
  minio: 'MinIO 存储',
}

function dependencyLabel(key: string): string {
  if (key === 'database' && system.isLightweight) return 'SQLite 本地数据库'
  return dependencyLabels[key] ?? key
}

const readinessLabel = computed(() => {
  if (!system.readiness) return '等待检查'
  if (system.isLightweight && system.isReady) return '轻量本地模式就绪'
  return system.isReady ? '基础设施就绪' : '部分服务异常'
})

const readinessStatus = computed(() => {
  if (!system.readiness) return 'pending'
  if (!system.isReady) return 'error'
  return system.isLightweight ? 'disabled' : 'ok'
})

const ezvizAuthLabel = computed(() => {
  const integration = devices.integration
  if (!integration?.configured) return '待配置'
  return integration.token_status === 'valid' ? '认证有效' : '等待认证'
})

onMounted(() => {
  void system.check()
  if (auth.user?.role === 'admin') {
    void devices.load()
    void devicePackages.load()
    void offlineVideos.load()
  }
})
</script>

<template>
  <div class="dashboard page-container">
    <section class="dashboard__heading">
      <div>
        <p class="eyebrow">PHASE 03 · PACKAGE ACTIVATION</p>
        <h1>平台总览</h1>
        <p>萤石开放平台认证已接入，当前实现套餐槽位、幂等激活与审计，真实设备验收仍待补充。</p>
      </div>
      <div class="dashboard__heading-actions">
        <StatusPill
          :status="readinessStatus"
          :label="readinessLabel"
        />
        <el-button :icon="Refresh" :loading="system.loading" @click="system.check">重新检查</el-button>
      </div>
    </section>

    <section class="metric-grid" aria-label="核心指标">
      <article class="metric-card metric-card--teal">
        <div class="metric-card__icon"><el-icon><Connection /></el-icon></div>
        <div>
          <span>已接入设备</span>
          <strong>{{ devices.integration?.device_count ?? 0 }}</strong>
          <small>{{ devices.onlineCount }} 台在线 · {{ devicePackages.succeededCount }} 个套餐激活成功</small>
        </div>
      </article>
      <article class="metric-card metric-card--blue">
        <div class="metric-card__icon"><el-icon><Files /></el-icon></div>
        <div>
          <span>离线数据集</span>
          <strong>{{ offlineVideos.library?.dataset_count ?? 0 }}</strong>
          <small>AI 推理尚未启用</small>
        </div>
      </article>
      <article class="metric-card metric-card--amber">
        <div class="metric-card__icon"><el-icon><Warning /></el-icon></div>
        <div>
          <span>待处理告警</span>
          <strong>--</strong>
          <small>第八阶段开放</small>
        </div>
      </article>
      <article class="metric-card metric-card--slate">
        <div class="metric-card__icon"><el-icon><Lock /></el-icon></div>
        <div>
          <span>萤石认证</span>
          <strong class="metric-card__word">{{ ezvizAuthLabel }}</strong>
          <small>只显示缓存状态，不返回 Token</small>
        </div>
      </article>
    </section>

    <section class="dashboard-grid">
      <article class="panel system-panel">
        <div class="panel__heading">
          <div>
            <span class="panel__kicker">SYSTEM HEALTH</span>
            <h2>基础服务</h2>
          </div>
          <span v-if="system.health" class="version-tag">API v{{ system.health.version }}</span>
        </div>
        <div class="service-list">
          <div v-for="key in ['database', 'redis', 'minio']" :key="key" class="service-row">
            <div>
              <span class="service-row__icon" :class="`service-row__icon--${key}`" />
              <strong>{{ dependencyLabel(key) }}</strong>
            </div>
            <StatusPill
              :status="system.readiness?.checks[key]?.status ?? 'pending'"
              :label="
                system.readiness?.checks[key]?.status === 'ok'
                  ? '运行正常'
                  : system.readiness?.checks[key]?.status === 'disabled'
                    ? '本地未启用'
                  : system.readiness
                    ? '连接异常'
                    : '等待检查'
              "
            />
          </div>
        </div>
        <p class="panel__footnote">
          上次检查：{{ system.checkedAt?.toLocaleTimeString('zh-CN') ?? '尚未检查' }}
        </p>
      </article>

      <article class="panel roadmap-panel">
        <div class="panel__heading">
          <div>
            <span class="panel__kicker">DELIVERY ROADMAP</span>
            <h2>阶段门禁</h2>
          </div>
          <span class="version-tag version-tag--active">进行中</span>
        </div>
        <ol class="roadmap-list">
          <li class="roadmap-list__item">
            <i>1</i>
            <div><strong>项目骨架</strong><span>认证、健康检查、容器化与单元测试</span></div>
          </li>
          <li class="roadmap-list__item">
            <i>2</i>
            <div><strong>萤石设备接入</strong><span>Token、设备同步和在线状态</span></div>
          </li>
          <li class="roadmap-list__item">
            <i>2A</i>
            <div><strong>离线视频模拟</strong><span>目录扫描、来源标注和安全回放</span></div>
          </li>
          <li class="roadmap-list__item roadmap-list__item--active">
            <i>3</i>
            <div><strong>套餐安全激活</strong><span>服务端槽位、幂等与审计</span></div>
          </li>
          <li class="roadmap-list__item">
            <i>4+</i>
            <div><strong>视频与风险闭环</strong><span>播放、AI、事件录像和分级告警</span></div>
          </li>
        </ol>
      </article>

      <article class="panel evidence-panel">
        <div class="panel__heading">
          <div>
            <span class="panel__kicker">EVIDENCE FIRST</span>
            <h2>比赛证据链</h2>
          </div>
        </div>
        <div class="evidence-flow">
          <div><b>前置</b><span>个体基线与失稳趋势</span></div>
          <i />
          <div><b>过程</b><span>连续帧状态与事件证据</span></div>
          <i />
          <div><b>处置</b><span>分级告警与人工反馈</span></div>
        </div>
        <p>尚未完成的能力使用“--”和阶段标签呈现，不用模拟数字冒充实测结果。</p>
      </article>
    </section>
  </div>
</template>
