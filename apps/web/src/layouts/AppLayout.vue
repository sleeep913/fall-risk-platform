<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, DataAnalysis, Film, Fold, Setting, Tickets, UserFilled } from '@element-plus/icons-vue'
import { ElButton, ElIcon } from 'element-plus'

import BrandMark from '@/components/BrandMark.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const roleLabel = computed(() => {
  const labels = { admin: '系统管理员', caregiver: '护理人员', family: '家属' }
  return auth.user ? labels[auth.user.role] : ''
})

async function handleLogout(): Promise<void> {
  await auth.logout()
  await router.replace({ name: 'login' })
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar__brand">
        <BrandMark />
        <div>
          <strong>安步守护</strong>
          <span>跌倒风险预警平台</span>
        </div>
      </div>

      <nav class="sidebar__nav" aria-label="主导航">
        <RouterLink class="sidebar__link" to="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>总览</span>
        </RouterLink>
        <button class="sidebar__link" disabled title="后续阶段开放">
          <el-icon><UserFilled /></el-icon>
          <span>老人档案</span>
          <small>待开放</small>
        </button>
        <button class="sidebar__link" disabled title="后续阶段开放">
          <el-icon><Bell /></el-icon>
          <span>事件中心</span>
          <small>待开放</small>
        </button>
        <RouterLink v-if="auth.user?.role === 'admin'" class="sidebar__link" to="/devices">
          <el-icon><Setting /></el-icon>
          <span>设备管理</span>
          <small>阶段 2</small>
        </RouterLink>
        <RouterLink v-if="auth.user?.role === 'admin'" class="sidebar__link" to="/offline-videos">
          <el-icon><Film /></el-icon>
          <span>离线视频</span>
          <small>阶段 2A</small>
        </RouterLink>
        <RouterLink v-if="auth.user?.role === 'admin'" class="sidebar__link" to="/device-packages">
          <el-icon><Tickets /></el-icon>
          <span>套餐管理</span>
          <small>阶段 3</small>
        </RouterLink>
      </nav>

      <div class="sidebar__phase">
        <span>研发进度</span>
        <strong>阶段 3 / 9</strong>
        <div class="sidebar__progress"><i /></div>
        <p>套餐槽位、幂等激活与审计</p>
      </div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <button class="icon-button topbar__menu" aria-label="折叠菜单">
          <el-icon><Fold /></el-icon>
        </button>
        <div class="topbar__context">
          <span>XH-202617</span>
          <strong>居家跌倒风险研究</strong>
        </div>
        <div class="topbar__user">
          <div class="topbar__avatar">{{ auth.user?.display_name.slice(0, 1) }}</div>
          <div>
            <strong>{{ auth.user?.display_name }}</strong>
            <span>{{ roleLabel }}</span>
          </div>
          <el-button text @click="handleLogout">退出</el-button>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>
