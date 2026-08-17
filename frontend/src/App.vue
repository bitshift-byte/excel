<template>
  <n-config-provider :theme-overrides="sakuraThemeOverrides" :locale="zhCN" :date-locale="dateZhCN">
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
import { zhCN, dateZhCN } from 'naive-ui'
import { sakuraThemeOverrides } from '@/theme/sakura'
</script>
