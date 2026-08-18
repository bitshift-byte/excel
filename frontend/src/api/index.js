/**
 * API 封装层
 * 基于 fetch，session/cookie 认证，未登录自动跳转
 */

let onUnauthorized = null

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

async function request(url, options = {}) {
  const opts = {
    credentials: 'same-origin',
    headers: {},
    ...options,
  }
  if (opts.body && !(opts.body instanceof FormData) && !opts.headers['Content-Type']) {
    opts.headers['Content-Type'] = 'application/json'
  }
  if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
    opts.body = JSON.stringify(opts.body)
  }

  try {
    const resp = await fetch(url, opts)
    if (resp.status === 401 || resp.status === 403) {
      if (onUnauthorized) onUnauthorized()
      return { status: 'error', detail: '未登录或登录已过期' }
    }
    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`
      try {
        const e = await resp.json()
        detail = e.detail || detail
      } catch (_) {}
      return { status: 'error', detail }
    }
    // 尝试解析 JSON，失败则返回文本
    const text = await resp.text()
    try {
      return JSON.parse(text)
    } catch (_) {
      return text
    }
  } catch (err) {
    return { status: 'error', detail: err.message || '网络错误' }
  }
}

export const api = {
  get: (url) => request(url, { method: 'GET' }),
  post: (url, body) => request(url, { method: 'POST', body }),
  put: (url, body) => request(url, { method: 'PUT', body }),
  del: (url) => request(url, { method: 'DELETE' }),
  upload: (url, formData) =>
    request(url, { method: 'POST', body: formData, headers: {} }),
}

// ===================== 具体接口 =====================

// 生成浏览器指纹（用于单设备登录绑定）
function generateBrowserFingerprint() {
  const ua = navigator.userAgent
  const screen = `${window.screen.width}x${window.screen.height}`
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'unknown'
  // 简单 hash
  const str = ua + screen + tz
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i)
    hash |= 0
  }
  return 'fp_' + Math.abs(hash).toString(36)
}

// 认证
export const authApi = {
  login: (username, password) =>
    api.post('/api/login', { username, password, browser_fingerprint: generateBrowserFingerprint() }),
  logout: () => api.post('/api/logout'),
  me: () => api.get('/api/me'),
  sync: () => api.get('/api/sync'),
}

// 规则
export const ruleApi = {
  list: () => api.get('/api/rules'),
}

// 地区
export const regionApi = {
  list: () => api.get('/api/regions'),
}

// 功能开关
export const featureApi = {
  list: () => api.get('/api/features'),
}

// 文件分析
export const fileApi = {
  analyze: (formData) => api.upload('/api/analyze', formData),
  process: (formData) => api.upload('/api/process', formData),
  download: () => '/api/download',
}

// 邮件
export const mailApi = {
  config: () => api.get('/api/mail/config'),
  run: (date) => api.post('/api/mail/run', { date }),
  results: () => api.get('/api/mail/results'),
  tasks: () => api.get('/api/mail/tasks'),
  resultFile: (filename) => `/api/mail/results/${encodeURIComponent(filename)}`,
  previewFile: (filename) => `/api/mail/results/${filename}/preview`,
  previewFileData: (filename) => api.get(`/api/mail/results/${encodeURIComponent(filename)}/preview`),
}

// ===================== 管理后台（代理到认证服务） =====================

export const adminApi = {
  // 用户管理
  users: () => api.get('/api/admin/users'),
  addUser: (data) => api.post('/api/admin/users', data),
  editUser: (username, data) => api.put(`/api/admin/users/${encodeURIComponent(username)}`, data),
  resetPassword: (username, password) => api.put(`/api/admin/users/${encodeURIComponent(username)}/password`, { password }),
  deleteUser: (username) => api.del(`/api/admin/users/${encodeURIComponent(username)}`),
  unbindDevice: (username) => api.post(`/api/admin/users/${encodeURIComponent(username)}/unbind-device`),
  deviceStatus: (username) => api.get(`/api/admin/users/${encodeURIComponent(username)}/device-status`),
  userFeatures: (username) => api.get(`/api/admin/users/${encodeURIComponent(username)}/features`),
  updateUserFeatures: (username, features) => api.put(`/api/admin/users/${encodeURIComponent(username)}/features`, features),

  // 应用配置
  appConfig: () => api.get('/api/admin/app-config'),
  mailConfig: (data) => api.put('/api/admin/mail-config', data),

  // 功能开关（全局）
  features: () => api.get('/api/admin/features'),
  updateFeatures: (data) => api.put('/api/admin/features', data),

  // 规则管理
  rules: () => api.get('/api/admin/rules'),
  addRule: (data) => api.post('/api/admin/rules', data),
  updateRule: (id, data) => api.put(`/api/admin/rules/${id}`, data),
  deleteRule: (id) => api.del(`/api/admin/rules/${id}`),

  // 用户规则分配
  getUserRules: (username) => api.get(`/api/admin/users/${encodeURIComponent(username)}/rules`),
  assignUserRules: (username, ruleIds) => api.put(`/api/admin/users/${encodeURIComponent(username)}/rules`, { rule_ids: ruleIds }),

  // 用户省份分配
  getUserProvinces: (username) => api.get(`/api/admin/users/${encodeURIComponent(username)}/provinces`),
  assignUserProvinces: (username, provinces) => api.put(`/api/admin/users/${encodeURIComponent(username)}/provinces`, { provinces }),


}
