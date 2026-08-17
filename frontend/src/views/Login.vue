<template>
  <div class="login-page">
    <!-- 浮动花瓣装饰球 -->
    <div class="bg-deco">
      <div class="orb s1"></div>
      <div class="orb s2"></div>
      <div class="orb s3"></div>
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
import { ref, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { authApi } from '@/api'
import { Database, User, Lock, Alert } from "@/utils/icons"

const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const pwInputRef = ref(null)
const loading = ref(false)
const errorMsg = ref('')

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
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
}

.bg-deco {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.35;
  animation: float-orb 8s ease-in-out infinite;
}

.s1 {
  width: 420px;
  height: 420px;
  background: var(--primary-l);
  top: -80px;
  left: -60px;
}
.s2 {
  width: 360px;
  height: 360px;
  background: var(--secondary-l);
  bottom: -60px;
  right: -40px;
  animation-delay: 2s;
}
.s3 {
  width: 280px;
  height: 280px;
  background: #A8C5E8;
  top: 40%;
  right: 20%;
  animation-delay: 4s;
  opacity: 0.2;
}

.login-wrap {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 20px;
}

.login-card {
  border-radius: var(--r-xl);
  box-shadow: var(--shadow-xl);
  padding: 40px 36px;
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
  .s1 {
    width: 280px;
    height: 280px;
  }
  .s2 {
    width: 240px;
    height: 240px;
  }
  .s3 {
    width: 180px;
    height: 180px;
  }
}
</style>