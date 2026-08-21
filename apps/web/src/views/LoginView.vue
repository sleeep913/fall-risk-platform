<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElButton,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'

import BrandMark from '@/components/BrandMark.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()

const form = reactive({ username: '', password: '' })
const rules: FormRules<typeof form> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit(formRef: FormInstance | undefined): Promise<void> {
  if (!formRef || !(await formRef.validate().catch(() => false))) return
  try {
    await auth.login(form)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch {
    ElMessage.error('用户名或密码错误，请重试')
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story" aria-label="平台介绍">
      <div class="login-story__glow" />
      <div class="login-story__content">
        <div class="login-story__brand">
          <BrandMark />
          <span>安步守护</span>
        </div>
        <p class="eyebrow">XH-202617 · 多模态 AI 居家安全研究</p>
        <h1>让每一次失稳<br /><em>更早被看见</em></h1>
        <p class="login-story__lead">
          从长期风险趋势到短期失稳先兆，再到事件分级处置，构建可解释、可验证的跌倒防护闭环。
        </p>
        <div class="login-story__flow">
          <span><i>01</i>前置评估</span>
          <b />
          <span><i>02</i>过程识别</span>
          <b />
          <span><i>03</i>分级预警</span>
        </div>
      </div>
      <p class="login-story__privacy">隐私优先 · 最小采集 · 全程可追溯</p>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="login-card__mobile-brand">
          <BrandMark />
          <span>安步守护</span>
        </div>
        <p class="eyebrow">WELCOME BACK</p>
        <h2>登录管理平台</h2>
        <p class="login-card__hint">使用系统管理员分配的账号继续</p>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username">
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
              show-password
              @keyup.enter="submit(formRef)"
            >
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-button
            class="login-card__submit"
            type="primary"
            :loading="auth.loading"
            @click="submit(formRef)"
          >
            安全登录
          </el-button>
        </el-form>

        <div class="login-card__notice">
          <span aria-hidden="true">i</span>
          当前为第一阶段工程版本，尚未接入真实视频与 AI 推理。
        </div>
      </div>
      <footer>© 2026 安步守护项目组 · 仅限授权研究与演示</footer>
    </section>
  </main>
</template>
