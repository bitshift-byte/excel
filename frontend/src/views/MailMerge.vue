<template>
  <div class="page-view">
    <div class="page-header">
      <div>
        <h1 class="page-title">邮件合并</h1>
        <p class="page-desc">选邮件捞取产物 + 上传总表，两个文件一起合并出最终表格</p>
      </div>
    </div>

    <n-steps :current="currentStep" class="steps-bar" size="small">
      <n-step title="选择来源" description="选邮件产物 + 上传总表" />
      <n-step title="结果下载" description="查看并下载结果" />
    </n-steps>

    <!-- Step 1: 选邮件产物 + 上传总表 → 一键合并 -->
    <div v-if="currentStep === 1" class="step-content animate-fade">
      <!-- 左右两栏：左边选邮件产物，右边上传总表 -->
      <div class="source-grid">
        <!-- 左：邮件捞取产物列表 -->
        <n-card hoverable class="source-card">
          <template #header>
            <div class="card-header-row">
              <span>邮件捞取产物</span>
              <n-tag size="small" round :type="selectedMailFile ? 'success' : 'default'">
                {{ selectedMailFile ? '已选 1 个' : '未选择' }}
              </n-tag>
            </div>
          </template>

          <div v-if="loadingMailResults" class="loading-box">
            <n-spin size="small" />
            <span style="margin-left: 8px; color: var(--text-3)">加载中...</span>
          </div>

          <div v-else-if="mailResults.length === 0" class="empty-hint">
            <n-empty description="暂无邮件捞取产物，请先在「邮件捞取」页面执行捞取" size="small" />
          </div>

          <div v-else class="mail-list">
            <div
              v-for="f in mailResults"
              :key="f.filename"
              class="mail-item"
              :class="{ active: selectedMailFile === f.filename }"
              @click="selectedMailFile = selectedMailFile === f.filename ? '' : f.filename"
            >
              <div class="mail-item-main">
                <n-radio
                  :checked="selectedMailFile === f.filename"
                  @change="selectedMailFile = f.filename"
                  @click.stop
                >
                  <span class="mail-name">{{ f.filename }}</span>
                </n-radio>
                <div class="mail-meta">
                  <span>{{ f.mtime }}</span>
                  <span>{{ (f.size / 1024).toFixed(0) }}KB</span>
                </div>
                <div class="mail-sheets">
                  <n-tag
                    v-for="s in f.sheets"
                    :key="s.name"
                    size="tiny"
                    round
                    :bordered="false"
                    :type="s.rows > 100 ? 'info' : 'default'"
                  >
                    {{ s.name }}({{ s.rows }})
                  </n-tag>
                </div>
              </div>
            </div>
          </div>
        </n-card>

        <!-- 右：上传总表 -->
        <n-card hoverable class="source-card">
          <template #header>
            <div class="card-header-row">
              <span>上传总表（可选）</span>
              <n-tag size="small" round :type="selectedFiles.length > 0 ? 'primary' : 'default'">
                {{ selectedFiles.length }} 个文件
              </n-tag>
            </div>
          </template>

          <n-upload
            multiple
            accept=".xlsx,.xls"
            :default-upload="false"
            :file-list="fileList"
            @change="handleFileChange"
            :show-file-list="false"
          >
            <n-upload-dragger class="mini-uploader">
              <div class="upload-dragger-content">
                <n-icon :size="36" color="var(--primary-l)"><Upload /></n-icon>
                <p class="upload-title">点击或拖拽总表到此处</p>
                <p class="upload-hint">含「明细」「已发运」「未发运」的 .xlsx / .xls</p>
              </div>
            </n-upload-dragger>
          </n-upload>

          <div v-if="selectedFiles.length" class="file-chips">
            <div v-for="(f, idx) in selectedFiles" :key="f.name" class="file-chip">
              <n-icon :size="16" color="var(--primary)"><File /></n-icon>
              <span class="chip-name">{{ f.name }}</span>
              <span class="chip-size">{{ (f.size / 1024).toFixed(0) }}KB</span>
              <n-button quaternary circle size="tiny" @click="removeFile(f.name)">
                <template #icon><n-icon><Close /></n-icon></template>
              </n-button>
            </div>
          </div>
        </n-card>
      </div>

      <!-- 交货号区间（可选） -->
      <n-card hoverable style="margin-top: 16px">
        <template #header>
          <div class="card-header-row">
            <span>交货号区间（可选）</span>
            <n-tag size="small" round :type="deliveryMin || deliveryMax ? 'warning' : 'default'">
              {{ deliveryMin || deliveryMax ? '已设置' : '不筛选' }}
            </n-tag>
          </div>
        </template>
        <div class="delivery-range-row">
          <n-input-number v-model:value="deliveryMin" placeholder="最小交货号" :show-button="false" size="small" style="width: 200px" clearable />
          <span class="range-sep">—</span>
          <n-input-number v-model:value="deliveryMax" placeholder="最大交货号" :show-button="false" size="small" style="width: 200px" clearable />
          <n-button size="small" quaternary @click="deliveryMin = null; deliveryMax = null">清除</n-button>
        </div>
        <p class="delivery-hint">不填则合并全部数据。填入区间（如 2424796922 ~ 2424802864）只合并该批次</p>
      </n-card>

      <!-- 一键合并按钮 -->
      <n-button
        type="primary"
        size="large"
        block
        :disabled="!selectedMailFile && selectedFiles.length === 0"
        :loading="merging"
        @click="runMerge"
        style="margin-top: 20px"
      >
        <template #icon><n-icon><Zap /></n-icon></template>
        一键合并
      </n-button>
    </div>

    <!-- Step 2: 结果 + 下载 -->
    <div v-if="currentStep === 2" class="step-content animate-fade">
      <n-card hoverable>
        <!-- 数据来源 -->
        <div v-if="stats.source_files && stats.source_files.length" class="source-summary">
          <div v-for="(sf, i) in stats.source_files" :key="i" class="source-badge">
            <n-icon :size="14" :color="sf.source === '邮件捞取产物' ? 'var(--accent-d)' : 'var(--primary)'">
              <File />
            </n-icon>
            <span class="sf-name">{{ sf.name }}</span>
            <n-tag size="tiny" round :bordered="false" :type="sf.source === '邮件捞取产物' ? 'success' : 'info'">
              {{ sf.source }}
            </n-tag>
          </div>
        </div>

        <!-- 统计 -->
        <div class="stats-grid">
          <div class="stat accent">
            <div class="stat-label">新增交货号</div>
            <div class="stat-value">{{ stats.appended_count || 0 }}</div>
            <div class="stat-desc">个新交货号追加到明细</div>
          </div>
          <div class="stat">
            <div class="stat-label">明细总行数</div>
            <div class="stat-value">{{ stats.total_in_detail || 0 }}</div>
            <div class="stat-desc">行（含历史数据）</div>
          </div>
        </div>

        <!-- 输出文件信息 -->
        <div v-if="stats.output_filename" style="margin-top: 16px; text-align: center; padding: 12px; background: var(--muted); border-radius: var(--r-sm);">
          <n-icon :size="16" color="var(--primary)"><File /></n-icon>
          <span style="margin-left: 8px; font-weight: 600;">{{ stats.output_filename }}</span>
        </div>

        <div style="margin-top: 12px; text-align: center; color: var(--text-4); font-size: 13px;">
          输出保留总表原始格式：已发运 / 未发运 / 明细 / 客户信息 / 组套 / Sheet5
        </div>

        <!-- 操作按钮 -->
        <div class="step-actions" style="margin-top: 24px">
          <n-button @click="goStep(1)">重新选择</n-button>
          <n-button type="primary" size="large" @click="downloadLatest">
            <template #icon><n-icon><Download /></n-icon></template>
            下载总表
          </n-button>
        </div>
      </n-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { NButton, NCard, NDataTable, NEmpty, NIcon, NInputNumber, NRadio, NSpin, NStep, NSteps, NTag, NUpload, NUploadDragger, useMessage } from 'naive-ui'
import { mailMergeApi } from '@/api'
import { Upload, File, Close, Zap, Download, Layers } from '@/utils/icons'
import { useResponsive } from '@/composables/useResponsive'

const message = useMessage()
const { isMobile } = useResponsive()
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const currentStep = ref(1)

// Step 1
const fileList = ref([])
const selectedFiles = ref([])
const merging = ref(false)
const mailResults = ref([])
const loadingMailResults = ref(false)
const selectedMailFile = ref('')
const deliveryMin = ref(null)
const deliveryMax = ref(null)

// Step 2
const stats = ref({})

async function loadMailResults() {
  loadingMailResults.value = true
  try {
    const data = await mailMergeApi.mailResults()
    if (data.status === 'success') {
      mailResults.value = data.files || []
    } else {
      message.error(data.detail || '加载邮件产物失败')
    }
  } catch (e) {
    message.error('加载邮件产物失败: ' + e.message)
  } finally {
    loadingMailResults.value = false
  }
}

function handleFileChange({ fileList: newList }) {
  fileList.value = newList
  selectedFiles.value = newList
    .filter(f => f.file && /\.(xlsx|xls)$/i.test(f.name))
    .filter(f => {
      if (f.file.size > MAX_FILE_SIZE) {
        message.error(`文件 "${f.name}" 超过 50MB 限制（当前 ${(f.file.size / 1024 / 1024).toFixed(1)}MB），已忽略`)
        return false
      }
      return true
    })
    .map(f => f.file)
    .filter((f, i, arr) => arr.findIndex(x => x.name === f.name) === i)
}

function removeFile(name) {
  selectedFiles.value = selectedFiles.value.filter(f => f.name !== name)
  fileList.value = fileList.value.filter(f => f.name !== name)
}

async function runMerge() {
  if (!selectedMailFile.value && selectedFiles.value.length === 0) {
    message.warning('请至少选择一个邮件产物或上传总表文件')
    return
  }
  merging.value = true
  const loadingMsg = message.loading('正在合并数据...', { duration: 0 })
  try {
    const fd = new FormData()
    if (selectedMailFile.value) {
      fd.append('mail_filename', selectedMailFile.value)
    }
    for (const f of selectedFiles.value) {
      fd.append('files', f)
    }
    if (deliveryMin.value) fd.append('delivery_min', String(deliveryMin.value))
    if (deliveryMax.value) fd.append('delivery_max', String(deliveryMax.value))

    const data = await mailMergeApi.run(fd)
    if (data.status === 'success') {
      stats.value = data.stats || {}
      currentStep.value = 2
      message.success(`合并完成，新增 ${stats.value.appended_count || 0} 个交货号`)
    } else {
      message.error(data.detail || '合并失败')
    }
  } catch (e) {
    message.error('请求出错: ' + e.message)
  } finally {
    merging.value = false
    loadingMsg.destroy()
  }
}

function goStep(n) { currentStep.value = n }

async function downloadLatest() {
  const loadingMsg = message.loading('正在准备下载...', { duration: 0 })
  try {
    const resp = await fetch(mailMergeApi.download(), { credentials: 'same-origin' })
    if (!resp.ok) {
      let detail = `下载失败 (HTTP ${resp.status})`
      try { const err = await resp.json(); detail = err.detail || detail } catch (_) {}
      message.error(detail)
      return
    }
    const disposition = resp.headers.get('content-disposition')
    let filename = '邮件合并结果.xlsx'
    if (disposition) {
      const match = disposition.match(/filename\*?=(?:UTF-8'')?(["']?)([^;"']+)\1/i)
      if (match) filename = decodeURIComponent(match[2])
    }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    message.success('文件已下载')
  } catch (e) {
    message.error('下载失败：' + e.message)
  } finally {
    loadingMsg.destroy()
  }
}

onMounted(() => {
  loadMailResults()
})
</script>

<style scoped>
/* ============ Mobile Card Layout (preview table -> cards) ============ */
.mobile-preview-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
}
.mobile-data-card {
  border-radius: 12px;
}
.card-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-light, #F0DEE7);
}
.card-row:last-child {
  border-bottom: none;
}
.card-label {
  color: var(--text-3, #8B7588);
  font-size: 13px;
  flex-shrink: 0;
}
.card-value {
  color: var(--text, #3D2B3C);
  font-size: 14px;
  text-align: right;
  word-break: break-all;
}

.page-view {
  padding: 32px;
  max-width: 1100px;
  margin: 0 auto;
  animation: blossom-in .4s var(--ease-spring) both;
}

.page-header { margin-bottom: 24px; }

.page-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--primary-d);
  letter-spacing: -0.3px;
  margin-bottom: 4px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-3);
  font-weight: 500;
}

.steps-bar {
  margin-bottom: 28px;
}

.step-content { margin-top: 8px; }

/* 左右两栏 */
.source-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 768px) {
  .source-grid { grid-template-columns: 1fr; }
}

.source-card { min-height: 300px; }

.card-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 邮件产物列表 */
.loading-box {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.empty-hint { padding: 20px; }

.mail-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.mail-item {
  padding: 10px 12px;
  border: 1.5px solid var(--border-l);
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: all 0.2s ease;
}

.mail-item:hover {
  border-color: var(--primary-l);
  background: var(--primary-bg);
}

.mail-item.active {
  border-color: var(--primary);
  background: var(--primary-bg);
  box-shadow: 0 0 0 3px var(--primary-bg);
}

.mail-item-main { display: flex; flex-direction: column; gap: 6px; }

.mail-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  word-break: break-all;
}

.mail-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-4);
  padding-left: 24px;
}

.mail-sheets {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-left: 24px;
}

/* 上传区 */
.mini-uploader { min-height: 200px; }

.upload-dragger-content {
  padding: 30px 16px;
  text-align: center;
}

.upload-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-2);
  margin: 10px 0 4px;
}

.upload-hint {
  font-size: 12px;
  color: var(--text-4);
}

.file-chips {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--muted);
  border-radius: var(--r-sm);
  border: 1px solid var(--border-l);
}

.chip-name {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip-size {
  font-size: 11px;
  color: var(--text-4);
}

/* 交货号区间 */
.delivery-range-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.range-sep {
  font-size: 14px;
  color: var(--text-4);
  font-weight: 600;
}

.delivery-hint {
  font-size: 12px;
  color: var(--text-4);
  margin-top: 8px;
}

.step-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
}

/* 数据来源徽章 */
.source-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.source-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--muted);
  border-radius: var(--r-sm);
  border: 1px solid var(--border-l);
  font-size: 12px;
}

.sf-name {
  font-weight: 600;
  color: var(--text-2);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Stats */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

@media (max-width: 900px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 480px) {
  .stats-grid { grid-template-columns: 1fr; }
  .page-view { padding: 20px 16px; }
}

.stat {
  padding: 20px;
  background: var(--muted);
  border-radius: var(--r-md);
  text-align: center;
  border: 1px solid var(--border-l);
  transition: all 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.stat:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.stat.accent { background: var(--accent-bg); }
.stat.amber { background: var(--amber-bg); }
.stat.purple { background: var(--secondary-bg); }

.stat-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-3);
  margin-bottom: 4px;
}

.stat-value {
  font-family: 'Quicksand', sans-serif;
  font-size: 28px;
  font-weight: 700;
  color: var(--text);
}

.stat.accent .stat-value { color: var(--accent-d); }
.stat.amber .stat-value { color: var(--amber); }
.stat.purple .stat-value { color: var(--secondary-d); }

.stat-desc {
  font-size: 11px;
  color: var(--text-4);
  margin-top: 2px;
}

.omo-stats-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  margin-bottom: 16px;
  background: var(--secondary-bg);
  border-radius: var(--r-sm);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}

.omo-stats-bar strong {
  color: var(--secondary-d);
  font-size: 15px;
}

.omo-divider {
  color: var(--text-4);
  margin: 0 4px;
}

/* Preview */
.preview-section { margin-top: 24px; }

.result-card {
  margin-bottom: 16px;
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
  animation: blossom-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes blossom-in {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--muted);
}

.rh-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-2);
}

.rh-title .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

.result-body { padding: 0; }

.result-note {
  padding: 8px 14px;
  font-size: 12px;
  color: var(--text-4);
  background: var(--muted);
  text-align: center;
}

:deep(.n-card) {
  border-radius: var(--r-lg);
  border: 1px solid var(--border-l);
  box-shadow: var(--shadow-sm);
}

:deep(.n-card.n-card--hoverable:hover) {
  box-shadow: var(--shadow-lg);
  border-color: var(--primary-l);
}

:deep(.n-upload-dragger) {
  border-radius: var(--r-md);
  border: 2px dashed var(--border);
  transition: all 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

:deep(.n-upload-dragger:hover) {
  border-color: var(--primary-l);
  background: var(--primary-bg);
}

@media (max-width: 768px) {
  .page-view { padding: 20px 14px; }
  .page-title { font-size: 20px; }
  .page-desc { font-size: 12px; }
  .step-actions { flex-direction: column; gap: 8px; }
  .step-actions .n-button { width: 100%; }
}

@media (max-width: 480px) {
  .page-view { padding: 14px 10px; }
  .page-title { font-size: 18px; }
  .stats-grid { grid-template-columns: 1fr; }
}
</style>
