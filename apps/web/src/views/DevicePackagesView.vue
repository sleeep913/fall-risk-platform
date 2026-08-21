<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Connection, Key, Lock, Tickets } from '@element-plus/icons-vue'
import {
  ElAlert,
  ElButton,
  ElCheckbox,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'

import { useDevicePackagesStore } from '@/stores/device-packages'
import { useDevicesStore } from '@/stores/devices'
import type { PackageActivationStatus, PackageSlot } from '@/types/device-package'

const packagesStore = useDevicePackagesStore()
const devicesStore = useDevicesStore()
const dialogVisible = ref(false)
const form = reactive({ package_slot: 0, device_id: 0, channel_no: 0, confirmed: false })

const availableDevices = computed(() =>
  devicesStore.devices.filter((device) => device.is_present && device.online_status === 'online'),
)
const selectedDevice = computed(
  () => availableDevices.value.find((device) => device.id === form.device_id) ?? null,
)
const availableChannels = computed(() =>
  (selectedDevice.value?.channels ?? []).filter(
    (channel) => channel.is_present && channel.online_status === 'online',
  ),
)
const entitlementBlockers = computed(() =>
  (packagesStore.entitlements?.blockers ?? []).map((blocker) => ({
    ezviz_credentials_not_configured: '尚未配置萤石 AppKey / AppSecret',
    token_not_authenticated: '萤石 Token 尚未取得或需要刷新',
    no_package_codes_configured: '服务端尚未配置赛事套餐码',
    no_online_devices: '尚未同步到在线萤石设备',
  })[blocker]),
)
const tokenStatusText = computed(
  () =>
    ({
      not_configured: '未配置',
      not_cached: '待获取',
      valid: '已认证',
      refresh_required: '待刷新',
    })[packagesStore.entitlements?.token_status ?? 'not_configured'],
)

onMounted(() => {
  void loadPage()
})

async function loadPage(): Promise<void> {
  try {
    await Promise.all([packagesStore.load(), devicesStore.load()])
  } catch {
    ElMessage.error('套餐与设备状态加载失败')
  }
}

function openActivation(slotRow: unknown): void {
  const slot = slotRow as PackageSlot
  form.package_slot = slot.slot
  form.device_id = 0
  form.channel_no = 0
  form.confirmed = false
  dialogVisible.value = true
}

function handleDeviceChange(): void {
  form.channel_no = 0
}

async function submitActivation(): Promise<void> {
  if (!form.device_id || !form.channel_no) {
    ElMessage.warning('请选择已在线的设备和通道')
    return
  }
  if (!form.confirmed) {
    ElMessage.warning('请先确认设备、通道和套餐槽位无误')
    return
  }
  await ElMessageBox.confirm(
    `即将使用套餐槽位 ${form.package_slot} 激活 ${selectedDevice.value?.name ?? '所选设备'} 的通道 ${form.channel_no}。该操作可能消耗一次性套餐码。`,
    '最终确认',
    { confirmButtonText: '确认提交萤石', cancelButtonText: '取消', type: 'warning' },
  )
  try {
    const result = await packagesStore.activate({
      package_slot: form.package_slot,
      device_id: form.device_id,
      channel_no: form.channel_no,
      confirmed: true,
    })
    dialogVisible.value = false
    if (result.activation_status === 'succeeded') {
      ElMessage.success('萤石设备套餐激活成功')
    } else {
      ElMessage.warning(result.official_message || '萤石未确认激活成功，请人工核查')
    }
  } catch (error: unknown) {
    ElMessage.error(readActivationError(error))
  }
}

function statusText(status: PackageActivationStatus): string {
  return { pending: '结果待确认', succeeded: '激活成功', rejected: '官方拒绝', failed: '请求失败' }[
    status
  ]
}

function statusType(status: PackageActivationStatus): 'success' | 'warning' | 'danger' | 'info' {
  return { pending: 'warning', succeeded: 'success', rejected: 'danger', failed: 'info' }[
    status
  ] as 'success' | 'warning' | 'danger' | 'info'
}

function formatDateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '--'
}

function readActivationError(error: unknown): string {
  const detail = (
    error as { response?: { data?: { detail?: { code?: string; message?: string } | string } } }
  ).response?.data?.detail
  if (typeof detail === 'object' && detail?.message) return detail.message
  if (typeof detail === 'string') return detail
  return '套餐激活请求失败，请查看后端日志并人工核查'
}
</script>

<template>
  <div class="packages-page page-container">
    <section class="packages-heading">
      <div>
        <p class="eyebrow">PHASE 03 · DEVICE PACKAGE ACTIVATION</p>
        <h1>萤石套餐管理</h1>
        <p>管理五个赛事套餐槽位。激活码只在服务端读取，页面不会接收或显示完整内容。</p>
      </div>
      <el-button :loading="packagesStore.loading" :icon="Connection" @click="loadPage">
        刷新状态
      </el-button>
    </section>

    <el-alert
      title="赛事专属权益已纳入平台管理"
      type="success"
      :closable="false"
      show-icon
      class="packages-alert"
    >
      <template #default>
        官方通知包含 5 个免费设备套餐，权益有效期为 6 个月（准确起止时间以萤石开放平台后台为准）。
        当前 Token 状态：{{ tokenStatusText }}；代金券：{{ packagesStore.entitlements?.coupon_redeemed ? '已人工确认领取' : '待人工领取并确认' }}。
      </template>
    </el-alert>

    <el-alert
      v-if="entitlementBlockers.length"
      title="套餐激活尚未就绪"
      :description="`${entitlementBlockers.join('；')}。在全部条件满足前，平台不会向萤石提交真实激活请求。`"
      type="warning"
      :closable="false"
      show-icon
      class="packages-alert"
    />

    <section class="package-metrics">
      <article class="package-metric"><el-icon><Tickets /></el-icon><div><span>赛事槽位</span><strong>{{ packagesStore.entitlements?.package_slots_total ?? 5 }}</strong></div></article>
      <article class="package-metric"><el-icon><Key /></el-icon><div><span>已配置</span><strong>{{ packagesStore.configuredCount }}/{{ packagesStore.entitlements?.package_slots_total ?? 5 }}</strong></div></article>
      <article class="package-metric"><el-icon><Lock /></el-icon><div><span>激活成功</span><strong>{{ packagesStore.succeededCount }}</strong></div></article>
      <article class="package-metric"><el-icon><Tickets /></el-icon><div><span>通知有效期</span><strong>{{ packagesStore.entitlements?.validity_months ?? 6 }} 个月</strong></div></article>
      <article class="package-metric"><el-icon><Connection /></el-icon><div><span>可选在线设备</span><strong>{{ availableDevices.length }}</strong></div></article>
    </section>

    <section class="panel packages-panel">
      <div class="panel__heading packages-panel__heading">
        <div><span class="panel__kicker">SERVER-SIDE SLOTS</span><h2>套餐槽位与审计记录</h2></div>
        <el-tag type="info" effect="plain">仅管理员</el-tag>
      </div>
      <el-table :data="packagesStore.slots" v-loading="packagesStore.loading" class="packages-table">
        <el-table-column prop="slot" label="槽位" width="80">
          <template #default="scope">槽位 {{ scope.row.slot }}</template>
        </el-table-column>
        <el-table-column label="服务端配置" width="120">
          <template #default="scope"><el-tag :type="scope.row.configured ? 'success' : 'info'" size="small">{{ scope.row.configured ? '已配置' : '未配置' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="激活状态" min-width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.activation" :type="statusType(scope.row.activation.activation_status)" size="small">{{ statusText(scope.row.activation.activation_status) }}</el-tag>
            <span v-else>尚未使用</span>
          </template>
        </el-table-column>
        <el-table-column label="设备与通道" min-width="190">
          <template #default="scope">
            <span v-if="scope.row.activation">{{ scope.row.activation.device_name }} · {{ scope.row.activation.device_serial_masked }} · 通道 {{ scope.row.activation.channel_no }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="官方结果" min-width="180">
          <template #default="scope">{{ scope.row.activation?.official_message ?? '--' }}</template>
        </el-table-column>
        <el-table-column label="激活时间" min-width="165">
          <template #default="scope">{{ formatDateTime(scope.row.activation?.activated_at ?? null) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="scope">
            <el-button
              text
              type="primary"
              :loading="packagesStore.activatingSlot === scope.row.slot"
              :disabled="!scope.row.configured || !!scope.row.activation || !packagesStore.entitlements?.activation_ready"
              @click="openActivation(scope.row)"
            >激活</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <p class="packages-privacy-note">页面只显示权益摘要、槽位、脱敏设备序列号和官方结果；完整套餐码、AppSecret 与 accessToken 均不会返回浏览器。代金券领取状态仅记录人工确认，不会自动领取代金券或开通任何付费服务。</p>

    <el-dialog v-model="dialogVisible" title="激活萤石设备套餐" width="520px">
      <el-alert title="套餐码可能只能使用一次，提交前必须核对真实在线设备、通道号和套餐槽位。" type="warning" :closable="false" show-icon />
      <el-form label-position="top" class="package-form">
        <el-form-item label="套餐槽位"><strong>槽位 {{ form.package_slot }}</strong></el-form-item>
        <el-form-item label="在线设备">
          <el-select v-model="form.device_id" placeholder="选择设备" @change="handleDeviceChange">
            <el-option v-for="device in availableDevices" :key="device.id" :value="device.id" :label="`${device.name}（${device.serial_masked}）`" />
          </el-select>
        </el-form-item>
        <el-form-item label="在线通道">
          <el-select v-model="form.channel_no" placeholder="选择通道" :disabled="!form.device_id">
            <el-option v-for="channel in availableChannels" :key="channel.id" :value="channel.channel_no" :label="`${channel.name}（通道 ${channel.channel_no}）`" />
          </el-select>
          <el-empty v-if="form.device_id && !availableChannels.length" description="所选设备没有在线通道" :image-size="50" />
        </el-form-item>
        <el-checkbox v-model="form.confirmed">我已核对真实设备、通道号和套餐槽位，并理解提交可能消耗一次性套餐码。</el-checkbox>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="danger" :disabled="!form.confirmed || !form.device_id || !form.channel_no" @click="submitActivation">进入最终确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>
