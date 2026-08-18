<template>
  <div class="page-view">
    <div class="page-header">
      <div>
        <h1 class="page-title">管理后台</h1>
        <p class="page-desc">用户管理、邮件配置、功能开关、规则管理</p>
      </div>
      <n-button circle tertiary @click="refreshCurrentTab" :loading="loading">
        <template #icon><n-icon :component="Refresh" /></template>
      </n-button>
    </div>

    <n-tabs v-model:value="activeTab" type="line" animated @update:value="onTabChange">
      <!-- ==================== 用户管理 ==================== -->
      <n-tab-pane name="users" tab="用户管理">
        <div class="tab-toolbar">
          <div class="stat-row">
            <div class="stat-chip"><span class="stat-num">{{ users.length }}</span><span class="stat-label">总用户</span></div>
            <div class="stat-chip accent"><span class="stat-num">{{ enabledCount }}</span><span class="stat-label">已启用</span></div>
            <div class="stat-chip danger"><span class="stat-num">{{ users.length - enabledCount }}</span><span class="stat-label">已禁用</span></div>
          </div>
          <n-button type="primary" @click="openUserModal(null)">
            <template #icon><n-icon :component="Plus" /></template>
            添加用户
          </n-button>
        </div>

        <n-card :bordered="false" class="table-card">
          <n-data-table
            :columns="userColumns"
            :data="users"
            :bordered="false"
            :loading="loading"
            :row-key="r => r.username"
            :scroll-x="900"
          />
        </n-card>
      </n-tab-pane>

      <!-- ==================== 邮件配置 ==================== -->
      <n-tab-pane name="mail" tab="邮件配置">
        <n-card :bordered="false" class="config-card">
          <n-form label-placement="top" :show-feedback="true" class="config-form">
            <div class="form-grid">
              <n-form-item label="启用邮件自动读取">
                <n-switch v-model:value="mailConfig.enabled" />
              </n-form-item>
              <n-form-item label="邮箱地址">
                <n-input v-model:value="mailConfig.email" placeholder="example@126.com" />
              </n-form-item>
              <n-form-item label="IMAP 授权码">
                <n-input v-model:value="mailConfig.auth_code" type="password" show-password-on="click" placeholder="IMAP 授权码" />
              </n-form-item>
              <n-form-item label="IMAP 服务器">
                <n-input v-model:value="mailConfig.imap_host" placeholder="imap.126.com" />
              </n-form-item>
              <n-form-item label="输出文件前缀">
                <n-input v-model:value="mailConfig.output_prefix" placeholder="捞数据_" />
              </n-form-item>
              <n-form-item label="主题关键词" :span="2">
                <n-dynamic-tags v-model:value="mailConfig.subject_keywords" />
              </n-form-item>
              <n-form-item label="筛选省份" :span="2">
                <n-dynamic-tags v-model:value="mailConfig.provinces" />
              </n-form-item>
            </div>
          </n-form>
          <div class="form-actions">
            <n-button type="primary" @click="saveMailConfig" :loading="savingMail">保存配置</n-button>
          </div>
        </n-card>
      </n-tab-pane>

      <!-- ==================== 功能开关 ==================== -->
      <n-tab-pane name="features" tab="功能开关">
        <n-card title="全局功能开关" :bordered="false" class="config-card">
          <div class="feature-list">
            <div v-for="item in featureList" :key="item.key" class="feature-item">
              <div class="feature-info">
                <div class="feature-name">{{ item.label }}</div>
                <div class="feature-desc">{{ item.desc }}</div>
              </div>
              <n-switch
                :value="globalFeatures[item.key]"
                @update:value="v => saveFeature(item.key, v)"
              />
            </div>
          </div>
        </n-card>

        <n-card title="用户功能权限" :bordered="false" class="config-card" style="margin-top:16px">
          <n-data-table
            :columns="featureUserColumns"
            :data="users"
            :bordered="false"
            :loading="loading"
            :row-key="r => r.username"
            :scroll-x="700"
          />
        </n-card>
      </n-tab-pane>

      <!-- ==================== 规则管理 ==================== -->
      <n-tab-pane name="rules" tab="规则管理">
        <div class="tab-toolbar">
          <span class="toolbar-hint">共 {{ rules.length }} 条规则</span>
          <n-button type="primary" @click="openRuleModal(null)">
            <template #icon><n-icon :component="Plus" /></template>
            添加规则
          </n-button>
        </div>

        <div class="rules-list">
          <n-empty v-if="!rules.length && !loading" description="暂无规则，点击「添加规则」创建" />
          <div v-for="rule in rules" :key="rule.id" class="rule-card">
            <div class="rule-head">
              <div class="rule-name">
                <n-icon :component="Layers" class="rule-icon" />
                <span>{{ rule.name }}</span>
                <n-tag v-if="rule.builtin" size="small" type="warning" round>内置</n-tag>
              </div>
              <div class="rule-actions">
                <n-button size="small" tertiary @click="openRuleModal(rule)">编辑</n-button>
                <n-button size="small" tertiary type="error" :disabled="rule.builtin" @click="confirmDeleteRule(rule)">删除</n-button>
              </div>
            </div>
            <div class="rule-meta">
              <span>{{ (rule.standard_headers || []).length }} 个标准列</span>
              <span v-if="rule.updated_at">更新于 {{ formatDate(rule.updated_at) }}</span>
              <span v-if="rule.id">ID: {{ rule.id }}</span>
            </div>
            <div class="rule-headers-preview">
              <n-tag
                v-for="h in (rule.standard_headers || [])"
                :key="h.name"
                size="small"
                round
                :bordered="false"
                class="header-tag"
              >
                {{ h.name }}
              </n-tag>
            </div>
          </div>
        </div>
      </n-tab-pane>
    </n-tabs>

    <!-- ==================== 用户编辑弹窗 ==================== -->
    <n-modal v-model:show="userModal.show" preset="card" :title="userModal.isEdit ? '编辑用户' : '添加用户'" style="width:480px" :bordered="false">
      <n-form ref="userFormRef" label-placement="top" :model="userModal.form">
        <n-form-item label="用户名" v-if="!userModal.isEdit">
          <n-input v-model:value="userModal.form.username" placeholder="登录用户名" />
        </n-form-item>
        <n-form-item label="用户名" v-else>
          <n-input :value="userModal.form.username" disabled />
        </n-form-item>
        <n-form-item label="密码" v-if="!userModal.isEdit">
          <n-input v-model:value="userModal.form.password" type="password" show-password-on="click" placeholder="初始密码" />
        </n-form-item>
        <n-form-item label="姓名">
          <n-input v-model:value="userModal.form.name" placeholder="显示姓名" />
        </n-form-item>
        <n-form-item label="角色">
          <n-select v-model:value="userModal.form.role" :options="roleOptions" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="userModal.form.enabled" />
        </n-form-item>
        <n-divider>功能权限</n-divider>
        <n-form-item v-for="item in featureList" :key="item.key" :label="item.label">
          <n-switch v-model:value="userModal.form.features[item.key]" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="userModal.show = false">取消</n-button>
          <n-button type="primary" @click="saveUser" :loading="userModal.saving">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- ==================== 重置密码弹窗 ==================== -->
    <n-modal v-model:show="pwModal.show" preset="card" title="重置密码" style="width:400px" :bordered="false">
      <n-form label-placement="top">
        <n-form-item label="用户名">
          <n-input :value="pwModal.username" disabled />
        </n-form-item>
        <n-form-item label="新密码">
          <n-input v-model:value="pwModal.password" type="password" show-password-on="click" placeholder="输入新密码" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="pwModal.show = false">取消</n-button>
          <n-button type="primary" @click="resetPassword" :loading="pwModal.saving">确认</n-button>
        </div>
      </template>
    </n-modal>

    <!-- ==================== 规则编辑弹窗 ==================== -->
    <n-modal v-model:show="ruleModal.show" preset="card" :title="ruleModal.isEdit ? '编辑规则' : '添加规则'" style="width:680px;max-width:95vw" :bordered="false">
      <n-form label-placement="top">
        <n-form-item label="规则名称">
          <n-input v-model:value="ruleModal.form.name" placeholder="如：各省汇总规则" />
        </n-form-item>
        <n-divider>标准列定义</n-divider>
      </n-form>

      <div class="header-editor">
        <div v-for="(header, hi) in ruleModal.form.standard_headers" :key="hi" class="header-block">
          <div class="header-block-head">
            <span class="hb-title">标准列 #{{ hi + 1 }}</span>
            <n-button size="tiny" tertiary type="error" @click="removeHeader(hi)">
              <template #icon><n-icon :component="Close" /></template>
            </n-button>
          </div>
          <div class="header-grid">
            <n-input v-model:value="header.name" placeholder="目标列名（如：姓名）" />
            <n-input v-model:value="header.source_columns_str" placeholder="源列名，逗号分隔（如：A列,B列）" />
          </div>

          <div class="mappings-section">
            <div class="mappings-header" @click="header._show_mappings = !header._show_mappings">
              <n-icon :component="ChevronForward" class="chevron" :class="{ open: header._show_mappings }" />
              <span>值映射 ({{ header.mappings.length }})</span>
            </div>
            <div v-if="header._show_mappings" class="mappings-list">
              <div v-for="(mapping, mi) in header.mappings" :key="mi" class="mapping-row">
                <div class="mapping-row-head">
                  <span class="mr-label">映射 #{{ mi + 1 }}</span>
                  <n-button size="tiny" tertiary type="error" @click="removeMapping(hi, mi)">
                    <template #icon><n-icon :component="Close" /></template>
                  </n-button>
                </div>
                <n-select
                  :value="mapping.type"
                  @update:value="v => changeMappingType(hi, mi, v)"
                  :options="mappingTypeOptions"
                  size="small"
                />
                <div v-if="mapping.type === 'column'" class="mapping-fields">
                  <n-input v-model:value="mapping.when_column" size="small" placeholder="判断列名" />
                  <n-input v-model:value="mapping.equals" size="small" placeholder="等于值" />
                  <n-input v-model:value="mapping.use_column" size="small" placeholder="取此列的值" />
                </div>
                <div v-else class="mapping-fields">
                  <n-input v-model:value="mapping.source_file_contains" size="small" placeholder="来源文件包含" />
                  <n-input v-model:value="mapping.source_value" size="small" placeholder="源值" />
                  <n-input v-model:value="mapping.target_value" size="small" placeholder="目标值" />
                </div>
              </div>
              <n-button size="small" dashed @click="addMapping(hi)">
                <template #icon><n-icon :component="Plus" /></template>
                添加映射
              </n-button>
            </div>
          </div>
        </div>
      </div>
      <n-button dashed block style="margin-top:12px" @click="addHeader">
        <template #icon><n-icon :component="Plus" /></template>
        添加标准列
      </n-button>

      <template #footer>
        <div class="modal-footer">
          <n-button @click="ruleModal.show = false">取消</n-button>
          <n-button type="primary" @click="saveRule" :loading="ruleModal.saving">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- ==================== 规则分配弹窗 ==================== -->
    <n-modal v-model:show="ruleAssignModal.show" preset="card" title="分配规则" style="width:520px;max-width:95vw" :bordered="false">
      <div class="rule-assign-info">
        <n-icon :component="User" />
        <span>{{ ruleAssignModal.username }}（{{ ruleAssignModal.name }}）</span>
      </div>
      <n-spin :show="ruleAssignModal.loading">
        <div class="rule-assign-list">
          <div v-if="customRules.length === 0" class="rule-assign-empty">
            暂无可分配的自定义规则，请先在「规则管理」中创建
          </div>
          <div
            v-for="rule in customRules"
            :key="rule.id"
            class="rule-assign-item"
            :class="{ checked: ruleAssignModal.selectedIds.includes(rule.id) }"
            @click="toggleRuleAssign(rule.id)"
          >
            <n-icon :component="Layers" class="rule-assign-icon" />
            <div class="rule-assign-content">
              <div class="rule-assign-name">{{ rule.name }}</div>
              <div class="rule-assign-meta">{{ (rule.standard_headers || []).length }} 个标准列</div>
            </div>
            <n-icon v-if="ruleAssignModal.selectedIds.includes(rule.id)" :component="CheckmarkCircle" class="rule-assign-check" />
          </div>
        </div>
      </n-spin>
      <div class="rule-assign-builtin-hint">
        <n-icon :component="Layers" />
        <span>内置规则（联合利华标准34列）默认对所有用户可见，无需分配</span>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="ruleAssignModal.show = false">取消</n-button>
          <n-button type="primary" @click="saveRuleAssign" :loading="ruleAssignModal.saving">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 删除确认已改用 dialog.warning() -->
  </div>
</template>

<script setup>
import { ref, reactive, computed, h, onMounted } from 'vue'
import { useMessage, useDialog, NTag, NButton, NSwitch, NSpace, NIcon } from 'naive-ui'
import { adminApi } from '@/api'
import {
  Plus, Close, Refresh, Layers, ChevronForward, User, Lock, MapPin,
} from '@/utils/icons'
import { CheckmarkCircle } from '@vicons/ionicons5'

const message = useMessage()
const dialog = useDialog()

const activeTab = ref('users')
const loading = ref(false)

// ============== 数据 ==============
const users = ref([])
const rules = ref([])
const globalFeatures = ref({})
const mailConfig = reactive({
  enabled: false,
  email: '',
  auth_code: '',
  imap_host: 'imap.126.com',
  subject_keywords: [],
  provinces: [],
  output_prefix: '',
})

// ============== 功能定义 ==============
const featureList = [
  { key: 'file_merge', label: '文件合并功能', desc: '允许用户合并 Excel 文件' },
  { key: 'mail_reader', label: '邮件自动读取', desc: '允许用户使用邮件捞取功能' },
  { key: 'rule_management', label: '规则查看', desc: '允许用户查看规则配置' },
]

const roleOptions = [
  { label: '管理员', value: 'admin' },
  { label: '普通用户', value: 'user' },
]

const mappingTypeOptions = [
  { label: '固定值映射', value: 'value' },
  { label: '条件取列', value: 'column' },
]

// ============== 计算属性 ==============
const enabledCount = computed(() => users.value.filter(u => u.enabled !== false).length)

// ============== 用户列表 ==============
const userColumns = computed(() => [
  {
    title: '用户',
    key: 'username',
    render(row) {
      const avatar = (row.name || row.username || '?').charAt(0).toUpperCase()
      return h('div', { class: 'cell-user' }, [
        h('div', { class: 'cell-avatar' }, avatar),
        h('div', { class: 'cell-info' }, [
          h('div', { class: 'cell-username' }, row.username),
        ]),
      ])
    },
  },
  { title: '姓名', key: 'name' },
  {
    title: '角色',
    key: 'role',
    width: 100,
    render(row) {
      return h(NTag, {
        size: 'small',
        type: row.role === 'admin' ? 'default' : 'success',
        round: true,
      }, { default: () => row.role === 'admin' ? '管理员' : '普通用户' })
    },
  },
  {
    title: '功能权限',
    key: 'features',
    width: 180,
    render(row) {
      const f = row.features || {}
      return h('div', { class: 'feat-badges' }, [
        h(NTag, { size: 'tiny', type: f.file_merge ? 'primary' : 'default', round: true, bordered: false }, () => '合并'),
        h(NTag, { size: 'tiny', type: f.mail_reader ? 'primary' : 'default', round: true, bordered: false }, () => '邮件'),
        h(NTag, { size: 'tiny', type: f.rule_management ? 'primary' : 'default', round: true, bordered: false }, () => '规则'),
      ])
    },
  },
  {
    title: '启用',
    key: 'enabled',
    width: 80,
    render(row) {
      return h(NSwitch, {
        value: row.enabled !== false,
        disabled: row.username === currentUser.value?.username,
        onUpdate: (v) => toggleEnabled(row, v),
      })
    },
  },
  {
    title: '设备',
    key: 'device',
    width: 100,
    render(row) {
      return h(DeviceStatus, { username: row.username })
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 320,
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'small', quaternary: true, onClick: () => openUserModal(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', quaternary: true, onClick: () => openPwModal(row.username) }, { default: () => '密码' }),
        h(NButton, { size: 'small', quaternary: true, type: 'info', onClick: () => openRuleAssignModal(row) }, { default: () => '规则' }),
        h(NButton, { size: 'small', quaternary: true, type: 'success', onClick: () => openProvinceAssignModal(row) }, { default: () => '省份' }),
        h(NButton, { size: 'small', quaternary: true, type: 'warning', onClick: () => unbindDevice(row.username) }, { default: () => '解绑' }),
        h(NButton, {
          size: 'small', quaternary: true, type: 'error',
          disabled: row.username === currentUser.value?.username || row.role === 'admin' && adminCount.value <= 1,
          onClick: () => confirmDeleteUser(row),
        }, { default: () => '删除' }),
      ])
    },
  },
])

const featureUserColumns = computed(() => [
  { title: '用户名', key: 'username' },
  { title: '姓名', key: 'name' },
  ...featureList.map(item => ({
    title: item.label,
    key: item.key,
    width: 120,
    render(row) {
      return h(NSwitch, {
        value: (row.features || {})[item.key] !== false,
        onUpdate: (v) => toggleUserFeature(row, item.key, v),
      })
    },
  })),
])

const adminCount = computed(() => users.value.filter(u => u.role === 'admin' && u.enabled !== false).length)

const currentUser = ref(null)

// ============== Device Status Component ==============
const deviceStatusCache = ref({})

const DeviceStatus = {
  props: ['username'],
  setup(props) {
    const status = ref(null)
    const loading = ref(true)
    async function load() {
      loading.value = true
      const data = await adminApi.deviceStatus(props.username)
      loading.value = false
      status.value = data
    }
    load()
    return () => {
      if (loading.value) return h('span', { class: 'dev-loading' }, '...')
      if (status.value?.bound) {
        return h(NTag, { size: 'small', type: 'warning', round: true }, { default: () => '已绑定' })
      }
      return h(NTag, { size: 'small', type: 'default', round: true, bordered: false }, { default: () => '未绑定' })
    }
  },
}

// ============== 加载数据 ==============
async function loadUsers() {
  loading.value = true
  const data = await adminApi.users()
  loading.value = false
  if (data.status === 'success') {
    users.value = data.users || []
  } else {
    message.error(data.detail || '加载用户列表失败')
  }
}

async function loadFeatures() {
  const data = await adminApi.features()
  if (data.status === 'success') {
    globalFeatures.value = data.features || {}
  }
}

async function loadMailConfig() {
  const data = await adminApi.appConfig()
  if (data.status === 'success') {
    const cfg = data.config || {}
    const mc = cfg.mail_config || {}
    Object.assign(mailConfig, {
      enabled: !!mc.enabled,
      email: mc.email || '',
      auth_code: mc.auth_code || '',
      imap_host: mc.imap_host || 'imap.126.com',
      subject_keywords: mc.subject_keywords || [],
      provinces: mc.provinces || [],
      output_prefix: mc.output_prefix || '',
    })
  }
}

async function loadRules() {
  loading.value = true
  const data = await adminApi.rules()
  loading.value = false
  if (data.status === 'success') {
    rules.value = data.rules || []
  }
}

async function loadCurrentUser() {
  const data = await adminApi.appConfig()
  // Also use the session user from store if available
  try {
    const me = await import('@/stores/user').then(m => m.useUserStore())
    currentUser.value = me.user
  } catch (_) {}
}

// ============== Tab 切换 ==============
function onTabChange(tab) {
  if (tab === 'users') loadUsers()
  else if (tab === 'mail') loadMailConfig()
  else if (tab === 'features') { loadFeatures(); loadUsers() }
  else if (tab === 'rules') loadRules()
}

function refreshCurrentTab() {
  onTabChange(activeTab.value)
}

// ============== 用户操作 ==============
const userModal = reactive({
  show: false,
  isEdit: false,
  saving: false,
  form: {
    username: '',
    password: '',
    name: '',
    role: 'user',
    enabled: true,
    features: { file_merge: true, mail_reader: true, rule_management: true },
  },
})

function openUserModal(user) {
  if (user) {
    userModal.isEdit = true
    userModal.form = {
      username: user.username,
      password: '',
      name: user.name || '',
      role: user.role || 'user',
      enabled: user.enabled !== false,
      features: { file_merge: true, mail_reader: true, rule_management: true, ...(user.features || {}) },
    }
  } else {
    userModal.isEdit = false
    userModal.form = {
      username: '',
      password: '',
      name: '',
      role: 'user',
      enabled: true,
      features: { file_merge: true, mail_reader: true, rule_management: true },
    }
  }
  userModal.show = true
}

async function saveUser() {
  if (!userModal.form.username.trim()) {
    message.warning('用户名不能为空')
    return
  }
  if (!userModal.isEdit && !userModal.form.password.trim()) {
    message.warning('密码不能为空')
    return
  }
  userModal.saving = true
  const payload = {
    name: userModal.form.name,
    role: userModal.form.role,
    enabled: userModal.form.enabled,
    features: userModal.form.features,
  }
  let data
  if (userModal.isEdit) {
    data = await adminApi.editUser(userModal.form.username, payload)
  } else {
    payload.username = userModal.form.username
    payload.password = userModal.form.password
    data = await adminApi.addUser(payload)
  }
  userModal.saving = false
  if (data.status === 'success') {
    message.success(userModal.isEdit ? '用户已更新' : '用户已添加')
    userModal.show = false
    loadUsers()
  } else {
    message.error(data.detail || '保存失败')
  }
}

async function toggleEnabled(user, val) {
  const data = await adminApi.editUser(user.username, { enabled: val })
  if (data.status === 'success') {
    message.success(val ? '已启用' : '已禁用')
    loadUsers()
  } else {
    message.error(data.detail || '操作失败')
  }
}

async function toggleUserFeature(user, key, val) {
  const features = { ...(user.features || {}), [key]: val }
  const data = await adminApi.updateUserFeatures(user.username, features)
  if (data.status === 'success') {
    message.success('权限已更新')
    loadUsers()
  } else {
    message.error(data.detail || '操作失败')
  }
}

const pwModal = reactive({
  show: false,
  username: '',
  password: '',
  saving: false,
})

function openPwModal(username) {
  pwModal.username = username
  pwModal.password = ''
  pwModal.show = true
}

async function resetPassword() {
  if (!pwModal.password.trim()) {
    message.warning('密码不能为空')
    return
  }
  pwModal.saving = true
  const data = await adminApi.resetPassword(pwModal.username, pwModal.password)
  pwModal.saving = false
  if (data.status === 'success') {
    message.success('密码已重置')
    pwModal.show = false
  } else {
    message.error(data.detail || '操作失败')
  }
}

async function unbindDevice(username) {
  const data = await adminApi.unbindDevice(username)
  if (data.status === 'success') {
    message.success('设备已解绑')
  } else {
    message.error(data.detail || '操作失败')
  }
}

// delModal 已移除，改用 dialog.warning()

function confirmDeleteUser(user) {
  dialog.warning({
    title: '删除用户',
    content: `确定要删除用户「${user.name || user.username}」吗？此操作不可撤销。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      const data = await adminApi.deleteUser(user.username)
      if (data.status === 'success') {
        message.success('用户已删除')
        loadUsers()
      } else {
        message.error(data.detail || '删除失败')
      }
    },
  })
}

// ============== 邮件配置 ==============
const savingMail = ref(false)
async function saveMailConfig() {
  savingMail.value = true
  const payload = {
    enabled: mailConfig.enabled,
    email: mailConfig.email.trim(),
    auth_code: mailConfig.auth_code.trim(),
    imap_host: mailConfig.imap_host.trim() || 'imap.126.com',
    subject_keywords: mailConfig.subject_keywords,
    provinces: mailConfig.provinces,
    output_prefix: mailConfig.output_prefix,
  }
  const data = await adminApi.mailConfig(payload)
  savingMail.value = false
  if (data.status === 'success') {
    message.success('邮件配置已保存')
  } else {
    message.error(data.detail || '保存失败')
  }
}

// ============== 功能开关 ==============
async function saveFeature(key, val) {
  const data = await adminApi.updateFeatures({ [key]: val })
  if (data.status === 'success') {
    message.success((val ? '已启用' : '已关闭'))
    globalFeatures.value = data.features || globalFeatures.value
  } else {
    message.error(data.detail || '保存失败')
    loadFeatures()
  }
}

// ============== 规则管理 ==============
const ruleModal = reactive({
  show: false,
  isEdit: false,
  saving: false,
  form: {
    id: null,
    name: '',
    standard_headers: [],
  },
})

function openRuleModal(rule) {
  if (rule) {
    ruleModal.isEdit = true
    ruleModal.form.id = rule.id
    ruleModal.form.name = rule.name || ''
    ruleModal.form.standard_headers = (rule.standard_headers || []).map(h => ({
      name: h.name || '',
      source_columns_str: (h.source_columns || []).join(','),
      mappings: (h.value_mappings || []).map(m => {
        if (m.when_column !== undefined) {
          return { type: 'column', when_column: m.when_column || '', equals: m.equals || '', use_column: m.use_column || '' }
        }
        return { type: 'value', source_file_contains: m.source_file_contains || '', source_value: m.source_value || '', target_value: m.target_value || '' }
      }),
      _show_mappings: false,
    }))
  } else {
    ruleModal.isEdit = false
    ruleModal.form.id = null
    ruleModal.form.name = ''
    ruleModal.form.standard_headers = [{ name: '', source_columns_str: '', mappings: [], _show_mappings: false }]
  }
  ruleModal.show = true
}

function addHeader() {
  ruleModal.form.standard_headers.push({ name: '', source_columns_str: '', mappings: [], _show_mappings: false })
}

function removeHeader(i) {
  ruleModal.form.standard_headers.splice(i, 1)
}

function addMapping(hi) {
  ruleModal.form.standard_headers[hi].mappings.push({
    type: 'value',
    source_file_contains: '',
    source_value: '',
    target_value: '',
  })
  ruleModal.form.standard_headers[hi]._show_mappings = true
}

function removeMapping(hi, mi) {
  ruleModal.form.standard_headers[hi].mappings.splice(mi, 1)
}

function changeMappingType(hi, mi, val) {
  if (val === 'column') {
    ruleModal.form.standard_headers[hi].mappings[mi] = { type: 'column', when_column: '', equals: '', use_column: '' }
  } else {
    ruleModal.form.standard_headers[hi].mappings[mi] = { type: 'value', source_file_contains: '', source_value: '', target_value: '' }
  }
}

async function saveRule() {
  if (!ruleModal.form.name.trim()) {
    message.warning('规则名称不能为空')
    return
  }
  const standard_headers = ruleModal.form.standard_headers
    .filter(h => h.name.trim())
    .map(h => {
      const obj = {
        name: h.name.trim(),
        source_columns: h.source_columns_str.split(',').map(s => s.trim()).filter(Boolean),
      }
      if (h.mappings.length) {
        obj.value_mappings = h.mappings.map(m => {
          if (m.type === 'column') {
            return { when_column: m.when_column, equals: m.equals, use_column: m.use_column }
          }
          return { source_file_contains: m.source_file_contains, source_value: m.source_value, target_value: m.target_value }
        })
      }
      return obj
    })

  if (!standard_headers.length) {
    message.warning('请至少添加一个标准列')
    return
  }

  ruleModal.saving = true
  const payload = { name: ruleModal.form.name.trim(), standard_headers }
  let data
  if (ruleModal.isEdit) {
    data = await adminApi.updateRule(ruleModal.form.id, payload)
  } else {
    data = await adminApi.addRule(payload)
  }
  ruleModal.saving = false
  if (data.status === 'success') {
    message.success(ruleModal.isEdit ? '规则已更新' : '规则已添加')
    ruleModal.show = false
    loadRules()
  } else {
    message.error(data.detail || '保存失败')
  }
}

// ============== 规则分配 ==============
const ruleAssignModal = reactive({
  show: false,
  loading: false,
  saving: false,
  username: '',
  name: '',
  selectedIds: [],
})

// 过滤出非内置规则（可分配的）
const customRules = computed(() => rules.value.filter(r => !r.builtin && r.id !== '_builtin_default'))

async function openRuleAssignModal(user) {
  ruleAssignModal.username = user.username
  ruleAssignModal.name = user.name || user.username
  ruleAssignModal.selectedIds = []
  ruleAssignModal.show = true
  ruleAssignModal.loading = true

  // 确保规则列表已加载
  if (rules.value.length === 0) {
    await loadRules()
  }

  // 加载该用户已分配的规则
  try {
    const data = await adminApi.getUserRules(user.username)
    if (data.status === 'success') {
      ruleAssignModal.selectedIds = data.rule_ids || []
    }
  } catch (e) {
    message.error('加载用户规则失败')
  }
  ruleAssignModal.loading = false
}

function toggleRuleAssign(ruleId) {
  const idx = ruleAssignModal.selectedIds.indexOf(ruleId)
  if (idx >= 0) {
    ruleAssignModal.selectedIds.splice(idx, 1)
  } else {
    ruleAssignModal.selectedIds.push(ruleId)
  }
}

async function saveRuleAssign() {
  ruleAssignModal.saving = true
  try {
    const data = await adminApi.assignUserRules(ruleAssignModal.username, ruleAssignModal.selectedIds)
    if (data.status === 'success') {
      message.success('规则分配已保存')
      ruleAssignModal.show = false
    } else {
      message.error(data.detail || '保存失败')
    }
  } catch (e) {
    message.error('保存失败')
  }
  ruleAssignModal.saving = false
}

// ============== 省份分配 ==============
const ALL_PROVINCES = [
  '上海', '杭州', '南京', '苏州', '无锡', '宁波', '温州', '绍兴', '嘉兴', '湖州',
  '金华', '台州', '衢州', '丽水', '舟山', '合肥', '芜湖', '蚌埠', '安庆', '马鞍山',
  '南昌', '九江', '赣州', '上饶', '宜春', '吉安', '抚州', '景德镇', '萍乡', '新余',
  '鹰潭', '福州', '厦门', '泉州', '漳州', '莆田', '龙岩', '三明', '南平', '宁德',
  '广州', '深圳', '东莞', '佛山', '中山', '珠海', '惠州', '汕头', '湛江', '江门',
  '北京', '天津', '重庆', '成都', '武汉', '长沙', '郑州', '西安', '济南', '青岛',
]

const provinceAssignModal = reactive({
  show: false,
  loading: false,
  saving: false,
  username: '',
  name: '',
  allProvinces: ALL_PROVINCES,
  selected: [],
})

async function openProvinceAssignModal(user) {
  provinceAssignModal.username = user.username
  provinceAssignModal.name = user.name || user.username
  provinceAssignModal.selected = []
  provinceAssignModal.show = true
  provinceAssignModal.loading = true

  try {
    const data = await adminApi.getUserProvinces(user.username)
    if (data.status === 'success') {
      provinceAssignModal.selected = data.provinces || []
    }
  } catch (e) {
    message.error('加载用户省份失败')
  }
  provinceAssignModal.loading = false
}

function toggleProvinceAssign(prov) {
  const idx = provinceAssignModal.selected.indexOf(prov)
  if (idx >= 0) {
    provinceAssignModal.selected.splice(idx, 1)
  } else {
    provinceAssignModal.selected.push(prov)
  }
}

async function saveProvinceAssign() {
  provinceAssignModal.saving = true
  try {
    const data = await adminApi.assignUserProvinces(provinceAssignModal.username, provinceAssignModal.selected)
    if (data.status === 'success') {
      message.success('省份分配已保存')
      provinceAssignModal.show = false
    } else {
      message.error(data.detail || '保存失败')
    }
  } catch (e) {
    message.error('保存失败')
  }
  provinceAssignModal.saving = false
}

function confirmDeleteRule(rule) {
  dialog.warning({
    title: '删除规则',
    content: `确定要删除规则「${rule.name}」吗？`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      const data = await adminApi.deleteRule(rule.id)
      if (data.status === 'success') {
        message.success('规则已删除')
        loadRules()
      } else {
        message.error(data.detail || '删除失败')
      }
    },
  })
}

// ============== 初始化 ==============
onMounted(async () => {
  // 获取当前用户
  try {
    const { useUserStore } = await import('@/stores/user')
    const store = useUserStore()
    currentUser.value = store.user
  } catch (_) {}
  loadUsers()
})
</script>

<style scoped>
/* ============ Page Layout ============ */
.page-view {
  padding: 28px 32px;
  max-width: 1200px;
  margin: 0 auto;
  animation: blossom-in .4s ease both;
}

/* ============ Page Header ============ */
.page-header {
  margin-bottom: 24px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.page-title {
  font-family: 'Quicksand', sans-serif;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 4px;
  color: var(--primary-d);
}
.page-desc {
  font-size: 13px;
  color: var(--text-3);
  font-weight: 500;
}

/* ============ Tabs ============ */
:deep(.n-tabs-tab) {
  font-family: 'Quicksand', sans-serif;
  font-weight: 700;
}

/* ============ Toolbar ============ */
.tab-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.toolbar-hint {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-3);
}

/* ============ Stat Chips ============ */
.stat-row {
  display: flex;
  gap: 12px;
}
.stat-chip {
  display: flex;
  flex-direction: column;
  padding: 8px 18px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  min-width: 84px;
  box-shadow: var(--shadow-sm);
  transition: all .28s cubic-bezier(.22,1,.36,1);
}
.stat-chip:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}
.stat-chip.accent { border-color: var(--accent); background: var(--accent-bg); }
.stat-chip.danger { border-color: var(--danger); background: var(--danger-bg); }
.stat-num {
  font-family: 'Quicksand', sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}
.stat-chip.accent .stat-num { color: var(--accent-d); }
.stat-chip.danger .stat-num { color: var(--danger); }
.stat-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .5px;
  color: var(--text-4);
  font-family: 'Quicksand', sans-serif;
}

/* ============ Table Card ============ */
.table-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

/* ============ User Table Cells ============ */
.cell-user {
  display: flex;
  align-items: center;
  gap: 10px;
}
.cell-avatar {
  width: 34px;
  height: 34px;
  border-radius: var(--r-sm);
  background: var(--grad-warm);
  color: var(--primary-d);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  font-family: 'Quicksand', sans-serif;
  flex-shrink: 0;
  border: 1px solid var(--border);
}
.cell-username {
  font-weight: 700;
  color: var(--text);
}
.feat-badges {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.dev-loading {
  font-size: 11px;
  color: var(--text-4);
}

/* ============ Config Cards ============ */
.config-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 16px;
}
.config-form .form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 24px;
}
.config-form .form-grid .n-form-item:last-child,
.config-form .form-grid .n-form-item:nth-last-child(2) {
  grid-column: span 2;
}
.form-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

/* ============ Features ============ */
.feature-list {
  display: flex;
  flex-direction: column;
}
.feature-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  border-bottom: 1px solid var(--border-l);
  gap: 16px;
}
.feature-item:last-child {
  border-bottom: none;
}
.feature-info {
  min-width: 0;
}
.feature-name {
  font-family: 'Quicksand', sans-serif;
  font-weight: 700;
  font-size: 15px;
  color: var(--text);
}
.feature-desc {
  font-size: 12px;
  color: var(--text-4);
  margin-top: 3px;
}

/* ============ Rules ============ */
.rules-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.rule-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 18px 22px;
  box-shadow: var(--shadow-sm);
  transition: all .28s cubic-bezier(.22,1,.36,1);
  animation: blossom-in .35s ease both;
}
.rule-card:hover {
  border-color: var(--primary-l);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.rule-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  gap: 12px;
}
.rule-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Quicksand', sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  min-width: 0;
  word-break: break-all;
}
.rule-icon {
  color: var(--primary);
  font-size: 20px;
  flex-shrink: 0;
}
.rule-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.rule-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-3);
  margin-bottom: 8px;
}
.rule-headers-preview {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.header-tag {
  background: var(--primary-bg) !important;
  color: var(--primary-d) !important;
}

/* ============ Modal ============ */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* ============ Header Editor ============ */
.header-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header-block {
  background: var(--muted);
  border: 1px solid var(--border-l);
  border-radius: var(--r-md);
  padding: 14px 16px;
}
.header-block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.hb-title {
  font-family: 'Quicksand', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--primary-d);
}
.header-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 10px;
}
.mappings-section {
  margin-top: 8px;
}
.mappings-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Quicksand', sans-serif;
  color: var(--secondary-d);
  user-select: none;
  transition: opacity .2s ease;
}
.mappings-header:hover {
  text-decoration: underline;
}
.chevron {
  transition: transform .2s ease;
}
.chevron.open {
  transform: rotate(90deg);
}
.mappings-list {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.mapping-row {
  background: var(--surface);
  border: 1px solid var(--border-l);
  border-radius: var(--r-sm);
  padding: 10px 12px;
}
.mapping-row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.mr-label {
  font-size: 12px;
  font-weight: 700;
  font-family: 'Quicksand', sans-serif;
  color: var(--text-3);
}
.mapping-fields {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
}

@media (max-width: 768px) {
  .page-view { padding: 20px 16px; }
  .config-form .form-grid { grid-template-columns: 1fr; }
  .config-form .form-grid .n-form-item:last-child,
  .config-form .form-grid .n-form-item:nth-last-child(2) {
    grid-column: span 1;
  }
  .header-grid,
  .mapping-fields { grid-template-columns: 1fr; }
  .stat-row { flex-wrap: wrap; }
}

/* ---- Mobile responsive ---- */
@media (max-width: 768px) {
  .page-view {
    padding: 20px 14px;
  }
  .page-header {
    flex-direction: column;
    gap: 8px;
  }
  .page-title {
    font-size: 20px;
  }
  .page-desc {
    font-size: 12px;
  }
  :deep(.n-card > .n-card__content) {
    padding: 14px;
  }
  .header-grid {
    grid-template-columns: 1fr;
  }
  .mapping-fields {
    grid-template-columns: 1fr;
  }
  .config-form .form-grid {
    grid-template-columns: 1fr;
  }
  .stat-row {
    flex-wrap: wrap;
    gap: 8px;
  }
  :deep(.n-tabs-tab) {
    padding: 6px 10px;
    font-size: 13px;
  }
  :deep(.n-data-table) {
    font-size: 12px;
  }
  :deep(.n-button) {
    font-size: 13px;
  }
}

@media (max-width: 480px) {
  .page-view {
    padding: 14px 10px;
  }
  .page-title {
    font-size: 18px;
  }
}

/* ============ Rule Assignment Modal ============ */
.rule-assign-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--muted);
  border-radius: var(--r-sm);
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.rule-assign-list {
  max-height: 360px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rule-assign-empty {
  text-align: center;
  padding: 32px 16px;
  color: var(--text-3);
  font-size: 13px;
}

.rule-assign-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: all var(--dur) var(--ease-spring);
}

.rule-assign-item:hover {
  border-color: var(--primary-l);
  background: var(--primary-bg);
}

.rule-assign-item.checked {
  border-color: var(--primary);
  background: var(--primary-bg);
}

.rule-assign-icon {
  color: var(--primary);
  flex-shrink: 0;
}

.rule-assign-content {
  flex: 1;
  min-width: 0;
}

.rule-assign-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.rule-assign-meta {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 2px;
}

.rule-assign-check {
  color: var(--primary);
  flex-shrink: 0;
}

.rule-assign-builtin-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--muted);
  border-radius: var(--r-sm);
  font-size: 12px;
  color: var(--text-3);
}
</style>