/**
 * API 封装层
 * 基于 axios + 拦截器，session/cookie 认证，未登录自动跳转。
 *
 * 设计要点：
 * - HTTP 错误与网络错误统一抛出 ApiError，调用方用 try/catch 自然处理（不再静默失败）
 * - 401 触发 onUnauthorized（跳转登录 + 清理状态）；403 仅提示无权限，不跳转登录
 * - 幂等 GET 请求自动重试（网络错误 / 5xx），指数退避
 * - 支持 AbortController 取消请求、上传进度回调
 */

import axios from 'axios'

// ===================== 配置 =====================

/** 幂等 GET 请求的重试配置（可调） */
const RETRY_CONFIG = {
  retries: 2, // 重试次数（不含首次）
  delay: 1000, // 初始退避基数（毫秒）
  maxDelay: 10000, // 单次退避上限（毫秒）
}

/** HTTP 状态码 -> 中文友好提示 */
const HTTP_STATUS_MESSAGES = {
  400: '请求参数有误，请检查后重试',
  401: '登录已过期，请重新登录',
  403: '没有权限执行此操作',
  404: '请求的资源不存在',
  413: '上传文件过大，请压缩后重试',
  415: '不支持的文件类型',
  422: '请求数据验证失败，请检查输入',
  429: '请求过于频繁，请稍后重试',
  500: '服务器内部错误，请稍后重试',
  502: '网关错误，服务暂不可用',
  503: '服务暂时不可用，请稍后重试',
  504: '网关超时，请稍后重试',
}

// ===================== 错误类型 =====================

/**
 * 统一 API 错误。HTTP 错误与网络错误都会抛出此类型，调用方可用 try/catch 捕获。
 */
export class ApiError extends Error {
  /**
   * @param {number} status HTTP 状态码（网络错误 / 取消时为 0）
   * @param {string} message 面向用户的友好提示
   * @param {string} [detail] 后端返回的原始 detail（缺省时回退到 message）
   */
  constructor(status, message, detail) {
    super(message)
    this.name = 'ApiError'
    /** HTTP 状态码，网络错误 / 取消为 0 */
    this.status = status
    /** 面向用户的友好提示 */
    this.message = message
    /** 后端原始 detail */
    this.detail = detail !== undefined ? detail : message
    /** 是否可重试（仅网络错误与 5xx） */
    this.retryable = false
  }
}

// ===================== axios 实例 + 拦截器 =====================

let onUnauthorized = null

/**
 * 注册 401 未授权处理器（由 main.js 注入：跳转登录 + 清理状态）。
 * @param {() => void} fn
 */
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 30000,
  withCredentials: true,
})

// 请求拦截器：透传 signal（AbortController）用于取消请求
http.interceptors.request.use((config) => config)

// 响应拦截器：统一错误处理 + 响应体解包
http.interceptors.response.use(
  (response) => {
    const payload = response.data
    // 若响应体本身用 .data 字段包裹实际数据，则解开一层；否则返回整个响应体
    if (payload && typeof payload === 'object' && 'data' in payload) {
      return payload.data
    }
    return payload
  },
  (error) => {
    throw normalizeError(error)
  }
)

/**
 * 将 axios 错误归一化为 ApiError。
 * @param {import('axios').AxiosError} error
 * @returns {ApiError}
 */
function normalizeError(error) {
  // 请求被取消（AbortController）：不可重试
  if (axios.isCancel(error) || error?.code === 'ERR_CANCELED') {
    const e = new ApiError(0, '请求已取消')
    e.retryable = false
    return e
  }

  // 无响应：网络错误或超时，可重试
  if (!error.response) {
    const isTimeout =
      error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')
    const msg = isTimeout ? '请求超时，请检查网络后重试' : '网络连接失败，请检查网络'
    const e = new ApiError(0, msg)
    e.retryable = true
    return e
  }

  const { status, data } = error.response
  const detail = data?.detail

  // 401：登录态失效，触发跳转登录（由 handler 做去重 + 清理状态）
  if (status === 401) {
    if (onUnauthorized) onUnauthorized()
    const e = new ApiError(status, HTTP_STATUS_MESSAGES[401], detail)
    e.retryable = false
    return e
  }

  // 403：已登录但无权限，仅提示，不跳转登录
  if (status === 403) {
    const e = new ApiError(status, '没有权限执行此操作', detail)
    e.retryable = false
    return e
  }

  // 其它 4xx / 5xx：按状态码映射友好文案；仅 5xx 可重试
  const friendly = HTTP_STATUS_MESSAGES[status] || `请求失败（HTTP ${status}）`
  const e = new ApiError(status, friendly, detail)
  e.retryable = status >= 500 && status < 600
  return e
}

// ===================== 重试（仅幂等 GET） =====================

/**
 * @typedef {Object} RequestOptions
 * @property {AbortSignal} [signal] 用于取消请求
 */

/**
 * 是否可重试：网络错误（含超时）或 5xx；取消与 4xx 不重试。
 * @param {ApiError} err
 * @returns {boolean}
 */
function isRetryable(err) {
  return !!(err && err.retryable)
}

/**
 * 可被 signal 取消的延时。
 * @param {number} ms
 * @param {AbortSignal} [signal]
 * @returns {Promise<void>}
 */
function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new ApiError(0, '请求已取消'))
      return
    }
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer)
        reject(new ApiError(0, '请求已取消'))
      },
      { once: true }
    )
  })
}

/**
 * 幂等 GET 请求，带自动重试（指数退避）。
 * 仅对网络错误与 5xx 重试，最多 RETRY_CONFIG.retries 次。
 * @param {string} url
 * @param {RequestOptions & import('axios').AxiosRequestConfig} [opts]
 * @returns {Promise<any>}
 */
async function getWithRetry(url, opts = {}) {
  const { signal, ...config } = opts
  const maxAttempts = RETRY_CONFIG.retries + 1
  let lastError
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await http.get(url, { ...config, signal })
    } catch (err) {
      lastError = err
      if (!isRetryable(err) || attempt === maxAttempts - 1) {
        throw err
      }
      const backoff = Math.min(
        RETRY_CONFIG.delay * Math.pow(2, attempt),
        RETRY_CONFIG.maxDelay
      )
      await sleep(backoff, signal)
    }
  }
  throw lastError
}

// ===================== 通用请求方法 =====================

export const api = {
  /**
   * GET 请求（幂等，自动重试网络错误 / 5xx）。
   * @param {string} url
   * @param {RequestOptions} [opts]
   * @returns {Promise<any>}
   */
  get: (url, opts = {}) => getWithRetry(url, opts),

  /**
   * POST 请求。
   * @param {string} url
   * @param {*} [body]
   * @param {RequestOptions} [opts]
   * @returns {Promise<any>}
   */
  post: (url, body, opts = {}) => http.post(url, body, opts),

  /**
   * PUT 请求。
   * @param {string} url
   * @param {*} [body]
   * @param {RequestOptions} [opts]
   * @returns {Promise<any>}
   */
  put: (url, body, opts = {}) => http.put(url, body, opts),

  /**
   * DELETE 请求。
   * @param {string} url
   * @param {RequestOptions} [opts]
   * @returns {Promise<any>}
   */
  del: (url, opts = {}) => http.delete(url, opts),

  /**
   * 文件上传（POST FormData），支持上传进度与取消。
   * @param {string} url
   * @param {FormData} formData
   * @param {Object} [opts]
   * @param {(e: import('axios').AxiosProgressEvent) => void} [opts.onUploadProgress]
   * @param {AbortSignal} [opts.signal]
   * @returns {Promise<any>}
   */
  upload: (url, formData, opts = {}) => http.post(url, formData, opts),
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
  /** @param {string} [sessionId] */
  download: (sessionId) => sessionId ? '/api/download?session_id=' + sessionId : '/api/download',
}

// 邮件
export const mailApi = {
  config: () => api.get('/api/mail/config'),
  run: (date) => api.post('/api/mail/run', { date }),
  results: () => api.get('/api/mail/results'),
  tasks: () => api.get('/api/mail/tasks'),
  resultFile: (filename) => `/api/mail/results/${encodeURIComponent(filename)}`,
  previewFileData: (filename) => api.get(`/api/mail/results/${encodeURIComponent(filename)}/preview`),
}

// 邮件合并
export const mailMergeApi = {
  run: (formData) => api.upload('/api/mail-merge/run', formData),
  download: () => '/api/mail-merge/download',
  mailResults: () => api.get('/api/mail-merge/mail-results'),
}

// ===================== 管理后台 =====================

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
