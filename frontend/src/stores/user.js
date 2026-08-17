/**
 * 用户状态管理 (Pinia)
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const features = computed(() => user.value?.features || {})

  const canFileMerge = computed(() => features.value.file_merge)
  const canRuleManagement = computed(() => features.value.rule_management)
  const canMailReader = computed(() => features.value.mail_reader)

  async function fetchUser() {
    loading.value = true
    try {
      const data = await authApi.me()
      if (data.status === 'success' && data.user) {
        user.value = data.user
        return data.user
      }
      user.value = null
      return null
    } catch (e) {
      user.value = null
      return null
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch (_) {}
    user.value = null
  }

  return {
    user,
    loading,
    isLoggedIn,
    isAdmin,
    features,
    canFileMerge,
    canRuleManagement,
    canMailReader,
    fetchUser,
    logout,
  }
})
