<template>
  <div class="page-view">
    <div class="page-header">
      <div>
        <h1 class="page-title">邮件捞取</h1>
        <p class="page-desc">从邮箱捞取附件并自动合并处理</p>
      </div>
      <n-space>
        <n-button type="primary" @click="showRunModal = true" :loading="running">
          <template #icon><n-icon><Zap /></n-icon></template>
          立即执行
        </n-button>
        <n-button @click="refreshAll">
          <template #icon><n-icon><Refresh /></n-icon></template>
          刷新
        </n-button>
      </n-space>
    </div>

    <!-- 邮件配置状态 -->
    <n-card hoverable class="section-card">
      <template #header>
        <div class="card-header-row">
          <n-icon :size="18" color="var(--primary)"><Mail /></n-icon>
          <div>
            <div class="ch-title">邮件配置状态</div>
            <div class="ch-sub">配置由管理员在后台统一管理</div>
          </div>
        </div>
      </template>

      <div class="config-grid">
        <div class="config-item">
          <div class="config-label">邮箱地址</div>
          <div class="config-value">{{ config.email || '未配置' }}</div>
        </div>
        <div class="config-item">
          <div class="config-label">IMAP服务器</div>
          <div class="config-value">{{ config.imap_host || '-' }}</div>
        </div>
        <div class="config-item">
          <div class="config-label">主题关键词</div>
          <div class="config-value">
            <n-space size="small">
              <n-tag v-for="k in (config.subject_keywords || [])" :key="k" size="small" round>{{ k }}</n-tag>
              <span v-if="!config.subject_keywords?.length" class="text-faint">无</span>
            </n-space>
          </div>
        </div>
        <div class="config-item">
          <div class="config-label">筛选省份</div>
          <div class="config-value">
            <n-space size="small">
              <n-tag v-for="p in (config.provinces || [])" :key="p" size="small" round type="info">{{ p }}</n-tag>
              <span v-if="!config.provinces?.length" class="text-faint">全量</span>
            </n-space>
          </div>
        </div>
      </div>
    </n-card>

    <!-- 处理结果 -->
    <n-card hoverable class="section-card">
      <template #header>
        <div class="card-header-row">
          <n-icon :size="18" color="var(--accent-d)"><Download /></n-icon>
          <div>
            <div class="ch-title">处理结果</div>
            <div class="ch-sub">合并生成的 Excel 文件</div>
          </div>
        </div>
      </template>

      <n-data-table
        :columns="resultColumns"
        :data="resultFiles"
        :bordered="false"
        size="small"
        :loading="resultsLoading"
      />
      <n-empty v-if="!resultFiles.length && !resultsLoading" description="暂无处理结果" size="small" style="padding: 20px" />
    </n-card>

    <!-- 捞取任务 -->
    <n-card hoverable class="section-card">
      <template #header>
        <div class="card-header-row">
          <n-icon :size="18" color="var(--secondary)"><Layers /></n-icon>
          <div>
            <div class="ch-title">捞取任务</div>
            <div class="ch-sub">每轮捞到的邮件及附件</div>
          </div>
        </div>
      </template>

      <n-data-table
        :columns="taskColumns"
        :data="tasks"
        :bordered="false"
        size="small"
        :max-height="300"
        :loading="tasksLoading"
        :row-key="row => row.time"
        :expanded-row-keys="expandedTaskKeys"
        @update:expanded-row-keys="(keys) => expandedTaskKeys = keys"
      />
      <n-empty v-if="!tasks.length && !tasksLoading" description="暂无捞取任务" size="small" style="padding: 20px" />

    <!-- 邮件预览弹窗 -->
    <n-modal v-model:show="mailPreviewModal.show" preset="card" title="邮件详情" style="width:600px;max-width:95vw" :bordered="false">
      <div class="mail-preview-info">
        <span class="mail-preview-time">{{ mailPreviewModal.time }}</span>
        <n-tag size="small" round>{{ mailPreviewModal.mails.length }} 封邮件</n-tag>
      </div>
      <div class="mail-preview-list">
        <div v-for="(mail, i) in mailPreviewModal.mails" :key="i" class="mail-preview-item">
          <div class="mail-preview-subject">
            <n-icon :component="mail.processed ? Zap : Mail" :color="mail.processed ? 'var(--primary)' : 'var(--text-4)'" />
            <span>{{ mail.subject || '(无主题)' }}</span>
          </div>
          <div class="mail-preview-attachments" v-if="mail.attachments && mail.attachments.length">
            <n-tag v-for="att in mail.attachments" :key="att" size="tiny" round>{{ att }}</n-tag>
          </div>
          <div class="mail-preview-status" :class="{ ok: mail.processed }">
            {{ mail.processed ? '已处理' : '未匹配' }}
          </div>
        </div>
      </div>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="mailPreviewModal.show = false">关闭</n-button>
        </div>
      </template>
    </n-modal>
    </n-card>

    <!-- 处理日志 -->
    <n-card hoverable>
      <template #header>
        <div class="card-header-row" style="cursor: pointer" @click="logExpanded = !logExpanded">
          <n-icon :size="18" color="var(--text-3)"><Refresh /></n-icon>
          <div>
            <div class="ch-title">处理日志</div>
            <div class="ch-sub">最近处理的详细记录</div>
          </div>
          <n-icon class="chevron" :class="{ collapsed: !logExpanded }" style="margin-left: auto"><ChevronForward /></n-icon>
        </div>
      </template>
      <div v-show="logExpanded" class="log-box">
        <div v-for="(log, i) in logs" :key="i" class="log-line">{{ log }}</div>
        <n-empty v-if="!logs.length" description="暂无日志" size="small" />
      </div>
    </n-card>

    <!-- Excel 预览弹窗 -->
    <n-modal v-model:show="excelPreviewModal.show" preset="card" :bordered="false" style="width:920px;max-width:95vw">
      <template #header>
        <div class="excel-preview-header">
          <n-icon :component="Grid" :size="18" color="var(--primary)" />
          <span class="excel-preview-title">{{ excelPreviewModal.filename }}</span>
        </div>
      </template>
      <n-spin :show="excelPreviewModal.loading">
        <n-tabs v-if="excelPreviewModal.sheets.length" type="line" animated size="small">
          <n-tab-pane v-for="(sheet, si) in excelPreviewModal.sheets" :key="si" :name="si">
            <template #tab>
              <span class="excel-tab-label">{{ sheet.sheet_name }}</span>
              <n-tag size="tiny" round :bordered="false" class="excel-tab-count">{{ sheet.total_rows }}行</n-tag>
            </template>
            <div class="excel-preview-scroll">
              <table class="excel-preview-table">
                <thead v-if="sheet.rows && sheet.rows.length">
                  <tr>
                    <th class="excel-corner">#</th>
                    <th v-for="(cell, ci) in sheet.rows[0]" :key="ci">{{ cell ?? '' }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in sheet.rows.slice(1)" :key="'h'+ri" :class="{ 'alt-row': ri % 2 === 1 }">
                    <td class="excel-row-num">{{ ri + 1 }}</td>
                    <td v-for="(cell, ci) in row" :key="ci" class="excel-cell">{{ cell ?? '' }}</td>
                  </tr>
                  <!-- 省略分隔行 -->
                  <tr v-if="sheet.tail_rows && sheet.tail_rows.length" class="excel-ellipsis-row">
                    <td :colspan="(sheet.rows[0] || []).length + 1">⋯ 中间省略 {{ sheet.tail_start - sheet.rows.length }} 行 ⋯</td>
                  </tr>
                  <!-- 末尾 10 行 -->
                  <tr v-for="(row, ri) in (sheet.tail_rows || [])" :key="'t'+ri" :class="{ 'alt-row': (sheet.tail_start + ri) % 2 === 1 }">
                    <td class="excel-row-num">{{ sheet.tail_start + ri + 1 }}</td>
                    <td v-for="(cell, ci) in row" :key="ci" class="excel-cell">{{ cell ?? '' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="sheet.tail_rows && sheet.tail_rows.length" class="excel-preview-hint">
              <n-icon :component="Eye" />
              <span>显示前 {{ sheet.rows.length - 1 }} 行 + 后 {{ sheet.tail_rows.length }} 行，共 {{ sheet.total_rows }} 行</span>
            </div>
            <div v-else-if="sheet.total_rows > 1" class="excel-preview-hint">
              <n-icon :component="Eye" />
              <span>共 {{ sheet.total_rows }} 行</span>
            </div>
          </n-tab-pane>
        </n-tabs>
        <n-empty v-else-if="!excelPreviewModal.loading" description="无数据" size="small" style="padding:40px" />
      </n-spin>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="excelPreviewModal.show = false">关闭</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 立即执行弹窗 -->
    <n-modal v-model:show="showRunModal" preset="dialog" title="选择处理日期">
      <p>选择要处理的邮件日期，会捞取该日期一整天的邮件并合并。</p>
      <n-date-picker v-model:value="runDate" type="date" clearable style="width: 100%; margin-top: 12px" />
      <template #action>
        <n-space>
          <n-button @click="showRunModal = false">取消</n-button>
          <n-button type="primary" @click="confirmRun" :loading="running">立即执行</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, reactive, h, onMounted } from 'vue'
import { useMessage, NButton, NSpace, NIcon, NTag, NTabs, NTabPane, NSpin, NEmpty } from 'naive-ui'
import { mailApi } from '@/api'
import { Mail, Zap, Download, Refresh, Layers, ChevronForward, Eye, Grid } from '@/utils/icons'

const message = useMessage()

const config = ref({})
const running = ref(false)
const showRunModal = ref(false)
const runDate = ref(null)
const logExpanded = ref(false)

const resultFiles = ref([])
const resultsLoading = ref(false)
const tasks = ref([])
const tasksLoading = ref(false)
const logs = ref([])

const resultColumns = [
  { title: '文件名', key: 'filename', ellipsis: { tooltip: true } },
  { title: '生成时间', key: 'mtime', width: 180 },
  { title: '大小', key: 'size', width: 100, render(row) {
    if (row.size == null) return '-'
    const kb = (row.size / 1024).toFixed(1)
    return kb > 1024 ? (kb / 1024).toFixed(1) + ' MB' : kb + ' KB'
  }},
  {
    title: '操作',
    key: 'actions',
    width: 160,
    render(row) {
      return h('div', { class: 'result-actions' }, () => [
        h(NButton, {
          size: 'small',
          quaternary: true,
          type: 'info',
          onClick: () => previewExcel(row.filename),
        }, { icon: () => h(NIcon, null, () => h(Eye)), default: () => '预览' }),
        h(NButton, {
          size: 'small',
          quaternary: true,
          type: 'primary',
          onClick: () => downloadFile(row.filename),
        }, { icon: () => h(NIcon, null, () => h(Download)), default: () => '下载' }),
      ])
    },
  },
]

const expandedTaskKeys = ref([])
const excelPreviewModal = reactive({
  show: false,
  filename: '',
  sheets: [],
  loading: false,
})

const mailPreviewModal = reactive({
  show: false,
  time: '',
  mails: [],
})

const taskColumns = [
  { title: '时间', key: 'time', width: 170, ellipsis: { tooltip: true } },
  { title: '邮件数', key: 'mailCount', width: 80, render(row) {
    return (row.mails || []).length
  }},
  {
    title: '已处理',
    key: 'processedCount',
    width: 80,
    render(row) {
      const processed = (row.mails || []).filter(m => m.processed).length
      const total = (row.mails || []).length
      return processed + ' / ' + total
    },
  },
  {
    title: '摘要',
    key: 'summary',
    ellipsis: { tooltip: true },
    render(row) {
      if (!row.mails || !row.mails.length) return '-'
      const subjects = row.mails.map(m => m.subject || '(无主题)')
      const display = subjects.slice(0, 3).join('、')
      return subjects.length > 3 ? display + '...' : display
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    render(row) {
      return h(NButton, {
        size: 'small',
        quaternary: true,
        type: 'info',
        onClick: () => openMailPreview(row),
      }, () => '详情')
    },
  },
]

function openMailPreview(row) {
  mailPreviewModal.time = row.time
  mailPreviewModal.mails = row.mails || []
  mailPreviewModal.show = true
}

async function loadConfig() {
  try {
    const data = await mailApi.config()
    if (data.status === 'success') {
      config.value = data.config || {}
    }
  } catch (e) {
    // silent
  }
}

async function loadResults() {
  resultsLoading.value = true
  try {
    const data = await mailApi.results()
    if (data.status === 'success' && data.files) {
      resultFiles.value = data.files
    }
  } finally {
    resultsLoading.value = false
  }
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const data = await mailApi.tasks()
    if (data.status === 'success' && data.tasks) {
      tasks.value = data.tasks
    }
  } finally {
    tasksLoading.value = false
  }
}

function downloadFile(filename) {
  const a = document.createElement('a')
  a.href = mailApi.resultFile(filename)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

async function previewExcel(filename) {
  excelPreviewModal.filename = filename
  excelPreviewModal.sheets = []
  excelPreviewModal.show = true
  excelPreviewModal.loading = true
  try {
    const data = await mailApi.previewFileData(filename)
    if (data && typeof data === 'object' && data.sheets) {
      excelPreviewModal.sheets = data.sheets
    } else {
      // previewFile returns the raw JSON, not wrapped
      excelPreviewModal.sheets = (data && data.sheets) || []
    }
  } catch (e) {
    message.error('预览加载失败')
  }
  excelPreviewModal.loading = false
}

async function confirmRun() {
  showRunModal.value = false
  running.value = true
  message.loading('正在执行，可能需要几十秒...', { duration: 5000 })
  try {
    const dateStr = runDate.value
      ? new Date(runDate.value).toISOString().slice(0, 10)
      : ''
    const data = await mailApi.run(dateStr)
    if (data.status === 'success') {
      message.success(`执行完成，处理 ${data.handled} 封邮件`)
      if (data.logs) logs.value = data.logs
      loadResults()
      loadTasks()
    } else {
      message.error(data.detail || '执行失败')
    }
  } finally {
    running.value = false
  }
}

function refreshAll() {
  loadConfig()
  loadResults()
  loadTasks()
}

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.page-view {
  padding: 28px 32px;
  max-width: 1100px;
  margin: 0 auto;
  animation: blossom-in .4s var(--ease-spring) both;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

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
  font-weight: 500;
  color: var(--text-3);
}

.section-card {
  margin-bottom: 16px;
}

/* Cards: glass surface, soft shadow, spring hover lift */
:deep(.n-card) {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  border: 1px solid var(--border-l);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-sm);
  transition: transform var(--dur) var(--ease-spring),
              box-shadow var(--dur) var(--ease-spring);
}

:deep(.n-card:hover) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

:deep(.n-card > .n-card__content) {
  padding: 20px 24px;
}

.card-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ch-title {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--primary-d);
}

.ch-sub {
  font-size: 12px;
  color: var(--text-4);
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.config-label {
  font-size: 12px;
  color: var(--text-4);
  margin-bottom: 4px;
  transition: color var(--dur) var(--ease-spring);
}

.config-value {
  font-size: 14px;
  color: var(--text-2);
  font-weight: 600;
}

.text-faint {
  color: var(--text-4);
}

.manual-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.manual-date {
  flex: 1;
  min-width: 200px;
}

/* Date picker focus state */
.manual-date :deep(.n-input .n-input__border),
.manual-date :deep(.n-input .n-input__state-border) {
  transition: border-color var(--dur) var(--ease-spring),
              box-shadow var(--dur) var(--ease-spring);
}

.manual-date :deep(.n-input--focus .n-input__state-border) {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-bg);
}

/* Primary buttons: sakura gradient + pink glow + hover lift */
:deep(.n-button.n-button--primary-type) {
  background: var(--grad-sakura);
  border: none;
  color: #fff;
  box-shadow: var(--shadow-pink);
  transition: transform var(--dur) var(--ease-spring),
              box-shadow var(--dur) var(--ease-spring);
}

:deep(.n-button.n-button--primary-type:hover) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-lg);
}

:deep(.n-button.n-button--primary-type:active) {
  transform: translateY(0);
}

/* Data tables: bold headers, pink hover */
:deep(.n-data-table .n-data-table-thead .n-data-table-th) {
  font-weight: 700;
  color: var(--text-2);
}

:deep(.n-data-table .n-data-table-tr:hover .n-data-table-td) {
  background: var(--primary-bg) !important;
  transition: background var(--dur) var(--ease-spring);
}

/* Responsive */
@media (max-width: 640px) {
  .page-view {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    gap: 12px;
  }

  .config-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .manual-row {
    flex-direction: column;
    align-items: stretch;
  }

  .manual-date {
    min-width: 0;
  }
}

/* ---- Log box ---- */
.log-box {
  font-family: var(--font-mono, 'SFMono-Regular', Menlo, Consolas, monospace);
  font-size: 12px;
  line-height: 1.8;
  max-height: 260px;
  overflow-y: auto;
  background: var(--muted);
  border: 1px solid var(--border-l);
  border-radius: var(--r-sm);
  padding: 12px;
}

.log-line {
  color: var(--text-2);
}

/* ---- Chevron ---- */
.chevron {
  transition: transform var(--dur) var(--ease-spring), color var(--dur) var(--ease-spring);
  color: var(--text-4);
}

.chevron:not(.collapsed) {
  color: var(--primary-l);
}

.chevron.collapsed {
  transform: rotate(-90deg);
}

/* ---- Mail preview modal ---- */
.mail-preview-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.mail-preview-time {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-2);
}

.mail-preview-list {
  max-height: 400px;
  overflow-y: auto;
}

.mail-preview-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-l);
  flex-wrap: wrap;
}

.mail-preview-item:last-child {
  border-bottom: none;
}

.mail-preview-subject {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--text-2);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mail-preview-attachments {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.mail-preview-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--r-sm);
  background: var(--muted);
  color: var(--text-4);
  white-space: nowrap;
}

.mail-preview-status.ok {
  background: var(--primary-bg);
  color: var(--primary-d);
}

/* ---- Result actions ---- */
.result-actions {
  display: flex;
  gap: 4px;
}

/* ---- Excel preview modal ---- */
.excel-preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.excel-preview-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--primary-d);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 700px;
}

.excel-tab-label {
  font-weight: 600;
}

.excel-tab-count {
  margin-left: 6px;
  background: var(--primary-bg);
  color: var(--primary-d);
}

.excel-preview-scroll {
  max-height: 460px;
  overflow: auto;
  border: 1px solid var(--border-l);
  border-radius: var(--r-sm);
}

.excel-preview-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
  font-family: var(--font-mono, 'SFMono-Regular', Menlo, Consolas, monospace);
}

.excel-preview-table th,
.excel-preview-table td {
  border-right: 1px solid var(--border-l);
  border-bottom: 1px solid var(--border-l);
  padding: 5px 10px;
  white-space: nowrap;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.excel-preview-table th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--muted);
  color: var(--text-1);
  font-weight: 700;
  text-align: left;
}

.excel-corner {
  width: 40px;
  min-width: 40px;
  text-align: center;
}

.excel-row-num {
  width: 40px;
  min-width: 40px;
  text-align: center;
  color: var(--text-4);
  background: var(--muted);
  font-size: 11px;
}

.excel-cell {
  color: var(--text-2);
}

.alt-row .excel-cell {
  background: color-mix(in srgb, var(--muted) 40%, transparent);
}

.excel-preview-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-4);
}

.excel-ellipsis-row td {
  text-align: center;
  color: var(--text-4);
  font-size: 12px;
  padding: 8px;
  background: var(--muted);
  font-style: italic;
  letter-spacing: 1px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

</style>
