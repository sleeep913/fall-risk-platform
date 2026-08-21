import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'devices',
          name: 'devices',
          component: () => import('@/views/DevicesView.vue'),
          meta: { adminOnly: true },
        },
        {
          path: 'offline-videos',
          name: 'offline-videos',
          component: () => import('@/views/OfflineVideosView.vue'),
          meta: { adminOnly: true },
        },
        {
          path: 'device-packages',
          name: 'device-packages',
          component: () => import('@/views/DevicePackagesView.vue'),
          meta: { adminOnly: true },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.restoreSession()
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
  if (to.meta.adminOnly && auth.user?.role !== 'admin') {
    return { name: 'dashboard' }
  }
  return true
})

export default router
