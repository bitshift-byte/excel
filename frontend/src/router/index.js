import { createRouter, createWebHashHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'merge',
        component: () => import('@/views/Merge.vue'),
        meta: { requiresAuth: true, feature: 'file_merge' },
      },
      {
        path: 'rules',
        name: 'rules',
        component: () => import('@/views/Rules.vue'),
        meta: { requiresAuth: true, feature: 'rule_management' },
      },
      {
        path: 'mail',
        name: 'mail',
        component: () => import('@/views/Mail.vue'),
        meta: { requiresAuth: true, feature: 'mail_reader' },
      },
      {
        path: 'mail-merge',
        name: 'mail-merge',
        component: () => import('@/views/MailMerge.vue'),
        meta: { requiresAuth: true, feature: 'file_merge' },
      },
      {
        path: 'admin',
        name: 'admin',
        component: () => import('@/views/Admin.vue'),
        meta: { requiresAuth: true, admin: true },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const store = useUserStore()

  if (to.meta.public) {
    if (store.isLoggedIn) return { name: 'merge' }
    return true
  }

  // 需要登录的页面，先确保用户信息已加载
  if (!store.isLoggedIn) {
    const user = await store.fetchUser()
    if (!user) {
      return { name: 'login' }
    }
  }

  // 检查功能权限
  if (to.meta.feature) {
    const feats = store.features
    if (to.meta.feature === 'file_merge' && !feats.file_merge) return { name: 'mail' }
    if (to.meta.feature === 'mail_reader' && !feats.mail_reader) return { name: 'merge' }
    if (to.meta.feature === 'rule_management' && !feats.rule_management) return { name: 'merge' }
  }

  // 检查管理员权限
  if (to.meta.admin && !store.isAdmin) {
    return { name: 'merge' }
  }

  return true
})

export default router
