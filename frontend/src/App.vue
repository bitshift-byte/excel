<template>
  <n-config-provider
    :theme="isDark ? darkTheme : null"
    :theme-overrides="isDark ? sakuraDarkThemeOverrides : sakuraThemeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <n-loading-bar-provider>
      <n-message-provider>
        <n-notification-provider>
          <n-dialog-provider>
            <router-view />
          </n-dialog-provider>
        </n-notification-provider>
      </n-message-provider>
    </n-loading-bar-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, watchEffect, provide } from 'vue'
import { zhCN, dateZhCN, darkTheme } from 'naive-ui'
import { sakuraThemeOverrides, sakuraDarkThemeOverrides } from '@/theme/sakura'

const STORAGE_KEY = 'sakura-theme'
const isDark = ref(localStorage.getItem(STORAGE_KEY) === 'dark')

watchEffect(() => {
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem(STORAGE_KEY, isDark.value ? 'dark' : 'light')
})

// 供子组件(如侧栏主题开关)共享主题状态
provide('theme', {
  isDark,
  toggle: () => { isDark.value = !isDark.value },
})
</script>
