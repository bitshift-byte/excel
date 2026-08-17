import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { setUnauthorizedHandler } from './api'
import './styles/global.css'

// 全局注册 Naive UI 组件
import {
  create,
  NConfigProvider,
  NLoadingBarProvider,
  NMessageProvider,
  NNotificationProvider,
  NDialogProvider,
  NDialog,
  NInput,
  NInputGroup,
  NInputNumber,
  NButton,
  NButtonGroup,
  NForm,
  NFormItem,
  NSwitch,
  NSelect,
  NTag,
  NCard,
  NTabs,
  NTabPane,
  NDataTable,
  NIcon,
  NEmpty,
  NModal,
  NDivider,
  NRadio,
  NRadioGroup,
  NUpload,
  NDescriptions,
  NDescriptionsItem,
  NSpace,
  NDynamicTags,
  NLayout,
  NLayoutSider,
  NLayoutContent,
  NMenu,
  NBadge,
  NTooltip,
  NAlert,
  NProgress,
  NSpin,
  NCheckbox,
  NCheckboxGroup,
  NCollapse,
  NCollapseItem,
  NPopover,
  NDropdown,
  NStatistic,
  NGrid,
  NGridItem,
  NResult,
  NStep,
  NSteps,
  NUploadDragger,
  NDatePicker,
} from 'naive-ui'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

// 注册所有 Naive UI 组件（kebab-case 命名匹配模板中的 <n-xxx> 标签）
const naiveComponents = [
  NConfigProvider, NLoadingBarProvider, NMessageProvider, NNotificationProvider,
  NDialogProvider, NDialog, NInput, NInputGroup, NInputNumber, NButton, NButtonGroup,
  NForm, NFormItem, NSwitch, NSelect, NTag, NCard, NTabs, NTabPane, NDataTable,
  NIcon, NEmpty, NModal, NDivider, NRadio, NRadioGroup, NUpload, NDescriptions,
  NDescriptionsItem, NSpace, NDynamicTags, NLayout, NLayoutSider, NLayoutContent,
  NMenu, NBadge, NTooltip, NAlert, NProgress, NSpin, NCheckbox, NCheckboxGroup,
  NCollapse, NCollapseItem, NPopover, NDropdown, NStatistic, NGrid, NGridItem,
  NResult,
  NStep, NSteps, NUploadDragger, NDatePicker,
]
naiveComponents.forEach(comp => {
  // Naive UI 组件名如 "Input", "ConfigProvider" 等，需转为 "n-input", "n-config-provider"
  const kebab = 'n-' + comp.name.replace(/([A-Z])/g, (m, p, i) => (i ? '-' : '') + m.toLowerCase())
  app.component(kebab, comp)
})

// 设置未认证处理
setUnauthorizedHandler(() => {
  router.push({ name: 'login' })
})

app.use(router)
app.mount('#app')
