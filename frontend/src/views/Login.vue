<template>
  <div class="login-page">
    <!-- 极光柔彩背景 -->
    <div class="bg-aurora">
      <div class="aurora-glow"></div>
      <div class="aurora-grain"></div>
      <div class="aurora-vignette"></div>
      <div class="petal-layer">
        <img
          v-for="p in petals"
          :key="p.id"
          class="petal"
          :src="p.src"
          alt=""
          loading="lazy"
          :style="p.style"
        />
      </div>
    </div>

    <div class="login-wrap">
      <div class="login-card glass animate-blossom">
        <!-- Logo -->
        <div class="logo-area">
          <div class="logo gradient-sakura">
            <n-icon :size="22" color="#fff">
              <Database />
            </n-icon>
          </div>
          <div>
            <div class="title">LX捞数据</div>
            <div class="sub">用户名密码登录</div>
          </div>
        </div>

        <!-- 错误提示 -->
        <transition name="err">
          <div v-if="errorMsg" class="err-msg">
            <n-icon :size="16"><Alert /></n-icon>
            <span>{{ errorMsg }}</span>
          </div>
        </transition>

        <!-- 登录表单 -->
        <n-form ref="formRef" :model="formData" :rules="rules" @submit.prevent="handleLogin">
          <n-form-item label="用户名" path="username">
            <n-input
              v-model:value="formData.username"
              placeholder="请输入用户名"
              size="large"
              :input-props="{ autocomplete: 'username' }"
              @keydown.enter="focusPassword"
            >
              <template #prefix>
                <n-icon :size="17" color="var(--text-4)"><User /></n-icon>
              </template>
            </n-input>
          </n-form-item>

          <n-form-item label="密码" path="password">
            <n-input
              ref="pwInputRef"
              v-model:value="formData.password"
              type="password"
              show-password-on="click"
              placeholder="请输入密码"
              size="large"
              :input-props="{ autocomplete: 'current-password' }"
              @keydown.enter="handleLogin"
            >
              <template #prefix>
                <n-icon :size="17" color="var(--text-4)"><Lock /></n-icon>
              </template>
            </n-input>
          </n-form-item>

          <n-button
            type="primary"
            size="large"
            block
            round
            :loading="loading"
            @click="handleLogin"
            style="margin-top: 8px"
          >
            登录
          </n-button>
        </n-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { NButton, NForm, NFormItem, NIcon, NInput } from 'naive-ui'
import { ref, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { authApi } from '@/api'
import { Database, User, Lock, Alert } from "@/utils/icons"
import petalA from '@/assets/sakura/petal-a.webp'
import petalB from '@/assets/sakura/petal-b.webp'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const pwInputRef = ref(null)
const loading = ref(false)
const errorMsg = ref('')

/* 真实樱花飘落花瓣 */
const petalImages = [petalA, petalB]
const petals = Array.from({ length: 12 }, (_, i) => {
  const img = petalImages[i % 2]
  const size = 12 + Math.random() * 16
  const left = Math.random() * 100
  const duration = 14 + Math.random() * 16
  const delay = Math.random() * -28
  const sway = 20 + Math.random() * 40
  const rotate = Math.random() * 360
  return {
    id: i,
    src: img,
    style: {
      left: `${left}%`,
      width: `${size}px`,
      height: `${size}px`,
      animationDuration: `${duration}s`,
      animationDelay: `${delay}s`,
      '--sway': `${sway}px`,
      '--rotate-start': `${rotate}deg`,
    }
  }
})

const formData = reactive({
  username: '',
  password: '',
})

const rules = {
  username: { required: true, message: '请输入用户名', trigger: 'blur' },
  password: { required: true, message: '请输入密码', trigger: 'blur' },
}

function focusPassword() {
  pwInputRef.value?.focus()
}

async function handleLogin() {
  errorMsg.value = ''

  try {
    await formRef.value?.validate()
  } catch (_) {
    return
  }

  loading.value = true
  try {
    const data = await authApi.login(formData.username.trim(), formData.password.trim())
    if (data.status === 'success') {
      await userStore.fetchUser()
      sessionStorage.setItem('justLoggedIn', '1')
      router.push('/')
      return
    }

    let msg = data.detail || '登录失败'
    errorMsg.value = msg
  } catch (err) {
    errorMsg.value = '网络错误，请检查网络后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  width: 100%;
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
}

.login-page::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 1;
  background: radial-gradient(ellipse 120% 100% at 50% 50%, transparent 40%, rgba(61,43,60,0.04) 100%);
  pointer-events: none;
}

[data-theme="dark"] .login-page::before {
  background: radial-gradient(ellipse 120% 100% at 50% 50%, transparent 30%, rgba(0,0,0,0.35) 100%);
}

.bg-aurora {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background: var(--bg);
}

/* Aurora glow — slow rotating conic gradient, ultra-subtle */
.aurora-glow {
  position: absolute;
  inset: -30%;
  background: conic-gradient(
    from 0deg at 50% 50%,
    transparent 0deg,
    rgba(240, 101, 149, 0.06) 50deg,
    transparent 110deg,
    rgba(155, 125, 212, 0.05) 170deg,
    transparent 230deg,
    rgba(255, 143, 177, 0.04) 290deg,
    transparent 360deg
  );
  filter: blur(60px);
  animation: aurora-rotate 50s linear infinite;
  will-change: transform;
}

[data-theme="dark"] .aurora-glow {
  background: conic-gradient(
    from 0deg at 50% 50%,
    transparent 0deg,
    rgba(240, 101, 149, 0.10) 50deg,
    transparent 110deg,
    rgba(155, 125, 212, 0.08) 170deg,
    transparent 230deg,
    rgba(255, 143, 177, 0.06) 290deg,
    transparent 360deg
  );
  filter: blur(80px);
}

@keyframes aurora-rotate {
  from { transform: rotate(0deg) scale(1.1); }
  to { transform: rotate(360deg) scale(1.1); }
}

/* Fine grain texture — prevents banding, adds premium tactile quality */
.aurora-grain {
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  opacity: 0.025;
  mix-blend-mode: multiply;
  pointer-events: none;
}

[data-theme="dark"] .aurora-grain {
  opacity: 0.04;
  mix-blend-mode: screen;
}

/* Vignette — subtle edge darkening for depth */
.aurora-vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 90% 80% at 50% 45%, transparent 50%, rgba(61,43,60,0.06) 100%);
  pointer-events: none;
}

[data-theme="dark"] .aurora-vignette {
  background: radial-gradient(ellipse 90% 80% at 50% 45%, transparent 40%, rgba(0,0,0,0.4) 100%);
}

.petal-layer {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
}

.petal {
  position: absolute;
  top: -60px;
  opacity: 0;
  will-change: transform, opacity;
  animation: fall-sway linear infinite;
  filter: drop-shadow(0 1px 2px rgba(0,0,0,0.08));
}

[data-theme="dark"] .petal {
  filter: brightness(0.75) drop-shadow(0 2px 4px rgba(0,0,0,0.35));
}

@keyframes fall-sway {
  0% {
    transform: translateY(0) translateX(0) rotate(var(--rotate-start));
    opacity: 0;
  }
  8% {
    opacity: 0.55;
  }
  92% {
    opacity: 0.55;
  }
  100% {
    transform: translateY(calc(100vh + 80px)) translateX(var(--sway)) rotate(calc(var(--rotate-start) + 360deg));
    opacity: 0;
  }
}

.login-wrap {
  position: relative;
  z-index: 3;
  width: 100%;
  max-width: 420px;
  padding: 20px;
}

.login-card {
  border-radius: var(--r-xl);
  box-shadow: var(--shadow-xl), 0 0 0 1px rgba(255,255,255,0.5) inset;
  padding: 40px 36px;
  transition: box-shadow .4s var(--ease-spring), transform .4s var(--ease-spring);
  position: relative;
}

.login-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: var(--r-xl);
  padding: 1px;
  background: linear-gradient(135deg, rgba(240,101,149,0.2), transparent 40%, transparent 60%, rgba(155,125,212,0.15));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.login-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 24px 56px -12px rgba(240,101,149,.25), 0 8px 20px -6px rgba(61,43,60,.08);
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 32px;
}

.logo {
  width: 46px;
  height: 46px;
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-pink);
  animation: logo-glow 3s ease-in-out infinite;
}

@keyframes logo-glow {
  0%, 100% { box-shadow: 0 8px 24px -6px rgba(240,101,149,.32); }
  50% { box-shadow: 0 8px 32px -4px rgba(240,101,149,.45); }
}

.title {
  font-family: 'Quicksand', -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif;
  font-size: 19px;
  font-weight: 700;
  color: var(--primary-d);
  letter-spacing: -0.3px;
}

.sub {
  font-size: 12px;
  color: var(--text-4);
  font-weight: 500;
}

.err-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--danger-bg);
  color: var(--danger);
  border: 1px solid rgba(230, 73, 128, 0.15);
  border-radius: var(--r-sm);
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 20px;
  font-weight: 600;
}

.err-enter-active, .err-leave-active {
  transition: all 0.3s ease;
}
.err-enter-from, .err-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ---- Mobile responsive ---- */
@media (max-width: 480px) {
  .login-wrap {
    padding: 16px;
  }
  .login-card {
    padding: 28px 20px;
  }
  .logo-area {
    gap: 10px;
    margin-bottom: 24px;
  }
  .logo {
    width: 40px;
    height: 40px;
  }
  .title {
    font-size: 17px;
  }
  .sub {
    font-size: 11px;
  }
}
</style>