<template>
  <n-layout has-sider class="main-layout">
    <!-- 登录欢迎动画 -->
    <Transition name="welcome-fade">
      <div v-if="showWelcome" class="welcome-overlay">
        <div
          v-for="(petal, i) in petals"
          :key="i"
          class="sakura-petal"
          :style="petal.style"
        />
        <div class="welcome-card">
          <div class="welcome-emoji">👋</div>
          <div class="welcome-title">{{ greeting }}，{{ displayName }} 🌸</div>
          <div class="welcome-sub">{{ encourage }} · 今天也要加油哦 ✨</div>
        </div>
      </div>
    </Transition>
    <!-- 侧边栏 -->
    <n-layout-sider
      bordered
      :width="248"
      :collapsed-width="0"
      collapse-mode="width"
      :collapsed="sidebarCollapsed"
      class="sidebar"
    >
      <div class="sidebar-brand">
        <div class="logo gradient-sakura">
          <n-icon :size="20" color="#fff"><Database /></n-icon>
        </div>
        <div class="brand-text">
          <div class="name">LX捞数据</div>
          <div class="sub">LX捞数据</div>
        </div>
      </div>

      <div class="sidebar-nav">
        <!-- 数据合并 -->
        <div class="nav-section">
          <div class="nav-section-title">数据合并</div>
          <div
            v-if="userStore.canFileMerge"
            class="nav-item"
            :class="{ active: route.name === 'merge' }"
            @click="navigate('/')"
          >
            <n-icon :size="18"><Upload /></n-icon>
            <span>文件合并</span>
          </div>
          <div
            v-if="userStore.canRuleManagement"
            class="nav-item"
            :class="{ active: route.name === 'rules' }"
            @click="navigate('/rules')"
          >
            <n-icon :size="18"><Layers /></n-icon>
            <span>规则列表</span>
          </div>
        </div>

        <!-- 邮件捞取 -->
        <div v-if="userStore.canMailReader" class="nav-section">
          <div class="nav-section-title">邮件捞取</div>
          <div
            class="nav-item"
            :class="{ active: route.name === 'mail' }"
            @click="navigate('/mail')"
          >
            <n-icon :size="18"><Mail /></n-icon>
            <span>邮件捞取</span>
          </div>
        </div>

        <!-- 管理 -->
        <div v-if="userStore.isAdmin" class="nav-section">
          <div class="nav-section-title">管理</div>
          <div
            class="nav-item"
            :class="{ active: route.name === 'admin' }"
            @click="navigate('/admin')"
          >
            <n-icon :size="18"><Settings /></n-icon>
            <span>管理后台</span>
          </div>
        </div>

        <!-- 帮助 -->
        <div class="nav-section">
          <div class="nav-section-title">帮助</div>
          <div class="nav-item" @click="showHelp = true">
            <n-icon :size="18"><Help /></n-icon>
            <span>使用说明</span>
          </div>
        </div>
      </div>

      <!-- 底部 -->
      <div class="sidebar-footer">
        <div v-if="userStore.user" class="user-box">
          <div class="user-avatar gradient-sakura">{{ avatarText }}</div>
          <div class="user-info">
            <div class="user-name">{{ userStore.user.name || userStore.user.username }}</div>
            <div class="user-role">{{ userStore.isAdmin ? '管理员' : '普通用户' }}</div>
          </div>
          <n-button quaternary circle size="small" @click="handleLogout" title="退出登录">
            <template #icon>
              <n-icon><LogOut /></n-icon>
            </template>
          </n-button>
        </div>
        <div class="status">
          <span class="dot"></span>
          <span>服务运行中</span>
        </div>
        <div class="version-row">
          <span class="version">{{ versionText }}</span>
          <n-button quaternary circle size="tiny" @click="checkUpdate" title="检查更新">
            <template #icon>
              <n-icon :size="13"><Refresh /></n-icon>
            </template>
          </n-button>
          <n-tag
            v-if="hasUpdate"
            type="primary"
            size="tiny"
            round
            style="cursor: pointer; font-size: 10px"
            @click="checkUpdate"
          >
            {{ updateBadgeText }}
          </n-tag>
        </div>
      </div>
    </n-layout-sider>

    <!-- 移动端遮罩 -->
    <div
      v-if="sidebarCollapsed === false && isMobile"
      class="sidebar-overlay"
      @click="sidebarCollapsed = true"
    ></div>

    <!-- 主内容区 -->
    <n-layout class="main-content">
      <n-layout-content content-style="height: 100vh; overflow-y: auto;">
        <button class="mobile-toggle" @click="sidebarCollapsed = !sidebarCollapsed" title="菜单">
          <n-icon :size="22"><Menu /></n-icon>
        </button>
        <div class="page-container">
          <router-view v-slot="{ Component }">
            <transition name="page" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </div>
      </n-layout-content>
    </n-layout>

    <!-- 使用说明弹窗 -->
    <n-modal v-model:show="showHelp" preset="card" title="使用说明" style="max-width: 640px;">
      <div class="help-content">
        <h3>📊 文件合并</h3>
        <ol>
          <li>上传多个 Excel 文件（.xlsx）</li>
          <li>系统自动分析每个文件的 Sheet 表头</li>
          <li>纠正列名映射，选择参与的 Sheet</li>
          <li>选择需要筛选的省份</li>
          <li>点击"开始合并"，等待处理完成</li>
          <li>下载合并后的 Excel 文件</li>
        </ol>
        <h3>📧 邮件捞取</h3>
        <ol>
          <li>管理员在管理后台配置邮箱 IMAP 参数</li>
          <li>手动执行邮件捞取，下载附件 Excel</li>
          <li>按规则自动处理并筛选数据</li>
          <li>在下方"处理结果"区域查看和下载</li>
        </ol>
      </div>
    </n-modal>
  </n-layout>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useUserStore } from '@/stores/user'
import {
  Database, Upload, Layers, Mail, Download,
  Settings, Help, LogOut, Refresh
} from "@/utils/icons"
import { MenuOutline as Menu } from '@vicons/ionicons5'
import { useTabScroll } from '@/composables/useTabScroll' 
const router = useRouter()
const route = useRoute()
const message = useMessage()
const userStore = useUserStore()

useTabScroll()

const sidebarCollapsed = ref(false)
const isMobile = ref(false)

// Auto-collapse sidebar on small screens
const MOBILE_BREAKPOINT = 900

function handleResize() {
  isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
  if (isMobile.value) {
    sidebarCollapsed.value = true
  } else {
    sidebarCollapsed.value = false
  }
}

function navigate(path) {
  router.push(path)
  if (isMobile.value) sidebarCollapsed.value = true
}
const showHelp = ref(false)
const versionText = ref('v1.0.0')
const hasUpdate = ref(false)
const updateBadgeText = ref('新版本')
const updateInfo = ref(null)

const avatarText = computed(() => {
  const name = userStore.user?.name || userStore.user?.username || '?'
  return name[0].toUpperCase()
})

// ---- 登录欢迎动画 ----
const showWelcome = ref(false)
const displayName = computed(() => userStore.user?.name || userStore.user?.username || '小伙伴')
const petals = ref([])

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h >= 5 && h < 12) return '早上好'
  if (h >= 12 && h < 18) return '下午好'
  if (h >= 18 && h < 23) return '晚上好'
  return '夜深了'
})

const encourage = computed(() => {
  const h = new Date().getHours()
  if (h >= 5 && h < 12) return '新的一天开始了'
  if (h >= 12 && h < 18) return '元气满满'
  if (h >= 18 && h < 23) return '辛苦啦'
  return '注意休息'
})

function generatePetals(count = 18) {
  const arr = []
  const colors = ['#F06595', '#FFC2D1', '#FF8FB1', '#FFB3C6', '#F8B4D9']
  for (let i = 0; i < count; i++) {
    const size = 8 + Math.random() * 10
    arr.push({
      style: {
        left: `${Math.random() * 100}%`,
        top: `-20px`,
        width: `${size}px`,
        height: `${size}px`,
        background: colors[Math.floor(Math.random() * colors.length)],
        animationDuration: `${2.5 + Math.random() * 2}s`,
        animationDelay: `${Math.random() * 0.8}s`,
        opacity: String(0.7 + Math.random() * 0.3),
        transform: `rotate(${Math.random() * 360}deg)`,
      }
    })
  }
  return arr
}

let welcomeTimer = null
function triggerWelcome() {
  petals.value = generatePetals()
  showWelcome.value = true
  if (welcomeTimer) clearTimeout(welcomeTimer)
  welcomeTimer = setTimeout(() => {
    showWelcome.value = false
  }, 3000)
}

async function handleLogout() {
  await userStore.logout()
  router.push('/login')
}

async function checkUpdate() {
  // pywebview 桌面端更新检查
  if (!window.pywebview || !window.pywebview.api) {
    message.info('当前运行在浏览器模式下，更新检查仅在桌面应用中可用')
    return
  }
  try {
    const result = await window.pywebview.api.check_update()
    if (result && result.has_update) {
      updateInfo.value = result
      hasUpdate.value = true
      updateBadgeText.value = '新版本'
      const msg = `发现新版本 ${result.latest}！\n\n${result.body || ''}\n\n是否立即下载升级？`
      if (confirm(msg)) {
        message.loading('正在下载新版本，请稍候...', { duration: 5000 })
        const dlResult = await window.pywebview.api.do_update()
        if (dlResult && dlResult.error) {
          message.error('下载失败: ' + dlResult.error)
        } else {
          message.success('新版本已下载，请重启应用完成升级')
          updateBadgeText.value = '待重启'
        }
      }
    } else if (result && result.error) {
      message.error('检查更新失败: ' + result.error)
    } else {
      message.success('当前已是最新版本')
    }
  } catch (e) {
    message.error('检查更新失败: ' + e.message)
  }
}

async function loadVersion() {
  if (!window.pywebview || !window.pywebview.api) return
  try {
    const v = await window.pywebview.api.get_version()
    if (v) versionText.value = v
  } catch (e) {}

  // 检查待应用的更新
  try {
    const pending = await window.pywebview.api.has_pending_update?.()
    if (pending) {
      hasUpdate.value = true
      updateBadgeText.value = '待重启'
    }
  } catch (e) {}
}

onMounted(() => {
  loadVersion()
  handleResize()
  window.addEventListener('resize', handleResize)
  if (sessionStorage.getItem('justLoggedIn') === '1') {
    sessionStorage.removeItem('justLoggedIn')
    // 等待用户信息和页面渲染就绪
    setTimeout(triggerWelcome, 200)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (welcomeTimer) clearTimeout(welcomeTimer)
})


</script>

<style scoped>
.main-layout {
  height: 100vh;
}

/* ---- Sidebar (glassmorphism) ---- */
.sidebar {
  background: var(--glass-bg) !important;
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border-right: 1px solid var(--glass-border) !important;
  box-shadow: 4px 0 24px -8px rgba(240, 101, 149, 0.12);
  display: flex;
  flex-direction: column;
}

/* Naive UI wraps content in a scroll container — make it flex too */
:deep(.n-layout-sider-scroll-container) {
  display: flex;
  flex-direction: column;
  height: 100% !important;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 22px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-l);
}

.logo {
  width: 40px;
  height: 40px;
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-pink);
  flex-shrink: 0;
}

.brand-text .name {
  font-family: 'Quicksand', sans-serif;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--primary-d);
}

.brand-text .sub {
  font-size: 11px;
  color: var(--text-4);
  font-weight: 500;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 16px 14px;
}

.nav-section {
  margin-bottom: 20px;
}

.nav-section-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--text-4);
  padding: 0 10px 8px;
  font-family: 'Quicksand', sans-serif;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--r-sm);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-3);
  transition: all 0.28s cubic-bezier(0.22, 1, 0.36, 1);
  margin-bottom: 2px;
  position: relative;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background: var(--primary);
  border-radius: 0 3px 3px 0;
  transition: height 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.nav-item:hover {
  background: var(--primary-bg);
  color: var(--primary-d);
}

.nav-item.active {
  background: var(--primary-bg);
  color: var(--primary-d);
  font-weight: 700;
}

.nav-item.active::before {
  height: 22px;
}

.nav-item.active .n-icon {
  color: var(--primary);
}

.sidebar-footer {
  flex-shrink: 0;
  padding: 16px 22px;
  border-top: 1px solid var(--border-l);
}

.user-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 6px;
  border-radius: var(--r-sm);
}

.user-avatar {
  width: 34px;
  height: 34px;
  border-radius: var(--r-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  font-family: 'Quicksand', sans-serif;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(240, 101, 149, 0.25);
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  font-size: 11px;
  color: var(--text-4);
}

.status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-3);
  font-weight: 600;
  padding: 8px 6px 4px;
}

.status .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent-l);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.version-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-4);
  padding: 0 6px;
}

/* ---- Main content ---- */
.main-content {
  background: var(--bg);
}

.page-container {
  min-height: 100vh;
  padding: 0;
}

/* ---- Mobile toggle (hidden on desktop) ---- */
.mobile-toggle {
  display: none;
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 300;
  width: 40px;
  height: 40px;
  border: 1px solid var(--glass-border);
  border-radius: var(--r-sm);
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  color: var(--primary-d);
  cursor: pointer;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-md);
  transition: all 0.2s ease;
}

.mobile-toggle:hover {
  box-shadow: var(--shadow-pink);
}

/* ---- Responsive ---- */
.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 99;
  backdrop-filter: blur(2px);
  animation: fade-in 0.2s ease;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@media (max-width: 900px) {
  .mobile-toggle {
    display: flex;
  }

  :deep(.n-layout-sider) {
    position: fixed !important;
    z-index: 100;
    height: 100vh;
    box-shadow: 4px 0 32px -8px rgba(0, 0, 0, 0.3);
    transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
  }

  :deep(.n-layout-sider.n-layout-sider--collapsed) {
    transform: translateX(-100%);
  }

  .page-container {
    padding-top: 0;
  }
}

@media (min-width: 901px) {
  .mobile-toggle {
    display: none;
  }
}

.help-content h3 {
  font-size: 15px;
  font-weight: 700;
  color: var(--primary-d);
  margin: 16px 0 8px;
}

.help-content h3:first-child {
  margin-top: 0;
}

.help-content ol {
  padding-left: 20px;
  font-size: 14px;
  line-height: 2;
  color: var(--text-2);
}

/* ---- Mobile responsive extras ---- */
@media (max-width: 480px) {
  .sidebar-brand {
    padding: 16px;
  }
  .brand-text .name {
    font-size: 14px;
  }
  .brand-text .sub {
    font-size: 10px;
  }
  .nav-item {
    padding: 8px 10px;
    font-size: 12px;
  }
  .nav-section-title {
    font-size: 9px;
    padding: 0 8px 6px;
  }
  .sidebar-footer {
    padding: 12px 16px;
  }
  .user-name {
    font-size: 12px;
  }
  .user-role {
    font-size: 10px;
  }
}

/* ---- 登录欢迎动画 ---- */
.welcome-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  pointer-events: none;
  overflow: hidden;
}

.sakura-petal {
  position: absolute;
  border-radius: 50% 0 50% 0;
  animation-name: petal-fall;
  animation-timing-function: cubic-bezier(.22, 1, .36, 1);
  animation-iteration-count: 1;
  animation-fill-mode: forwards;
  filter: drop-shadow(0 2px 4px rgba(240, 101, 149, 0.2));
}

@keyframes petal-fall {
  0% {
    transform: translateY(-20px) translateX(0) rotate(0deg);
    opacity: 1;
  }
  50% {
    transform: translateY(50vh) translateX(20px) rotate(180deg);
    opacity: 1;
  }
  100% {
    transform: translateY(105vh) translateX(-10px) rotate(360deg);
    opacity: 0;
  }
}

.welcome-card {
  position: absolute;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid var(--glass-border);
  border-radius: var(--r-lg);
  padding: 24px 40px;
  box-shadow: var(--shadow-pink), 0 16px 48px -12px rgba(240, 101, 149, 0.25);
  text-align: center;
  animation: welcome-in 0.5s var(--ease-spring) both;
}

.welcome-emoji {
  font-size: 32px;
  margin-bottom: 8px;
  animation: wave 1.5s ease-in-out infinite;
}

.welcome-title {
  font-family: 'Quicksand', sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--primary-d);
  letter-spacing: -0.3px;
  margin-bottom: 6px;
}

.welcome-sub {
  font-size: 13px;
  color: var(--text-3);
  font-weight: 500;
}

@keyframes welcome-in {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-12px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
}

@keyframes wave {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(15deg); }
  75% { transform: rotate(-10deg); }
}

.welcome-fade-leave-active {
  transition: opacity 0.6s var(--ease-spring);
}

.welcome-fade-leave-to {
  opacity: 0;
}
</style>