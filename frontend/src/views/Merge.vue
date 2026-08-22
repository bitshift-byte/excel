<template>
  <div class="page-view">
    <div class="page-header">
      <div>
        <h1 class="page-title">文件合并</h1>
        <p class="page-desc">上传多个 Excel 文件，自动分析、智能匹配列名、按省份筛选合并</p>
      </div>
    </div>

    <n-steps :current="currentStep" class="steps-bar" size="small">
      <n-step title="上传文件" description="选择 Excel 文件" />
      <n-step title="配置列名" description="纠正表头映射" />
      <n-step title="合并下载" description="生成结果文件" />
    </n-steps>

    <!-- Step 1: 上传 -->
    <div v-if="currentStep === 1" class="step-content animate-fade">
      <n-card class="upload-card" hoverable>
        <n-upload
          multiple
          accept=".xlsx,.xls"
          :default-upload="false"
          :file-list="fileList"
          @change="handleFileChange"
          :show-file-list="false"
        >
          <n-upload-dragger>
            <div class="upload-dragger-content">
              <n-icon :size="48" color="var(--primary-l)"><Upload /></n-icon>
              <p class="upload-title">点击或拖拽文件到此处上传</p>
              <p class="upload-hint">支持 .xlsx / .xls 格式，可同时上传多个文件</p>
            </div>
          </n-upload-dragger>
        </n-upload>

        <div v-if="selectedFiles.length" class="file-chips">
          <div v-for="(f, idx) in selectedFiles" :key="idx" class="file-chip">
            <n-icon :size="16" color="var(--primary)"><File /></n-icon>
            <span class="chip-name">{{ f.name }}</span>
            <span class="chip-size">{{ (f.size / 1024).toFixed(0) }}KB</span>
            <n-button quaternary circle size="tiny" @click="removeFile(idx)">
              <template #icon><n-icon><Close /></n-icon></template>
            </n-button>
          </div>
        </div>

        <n-button
          type="primary"
          size="large"
          block
          :disabled="!selectedFiles.length"
          :loading="analyzing"
          @click="analyzeFiles"
          style="margin-top: 20px"
        >
          <template #icon><n-icon><Search /></n-icon></template>
          开始分析
        </n-button>
      </n-card>
    </div>

    <!-- Step 2: 配置列名 + 省份选择 -->
    <div v-if="currentStep === 2" class="step-content animate-fade">
      <!-- 规则选择器 -->
      <n-card v-if="rulesData.length > 0" class="rule-selector-card" hoverable>
        <div class="rule-selector-row">
          <div class="rule-selector-left">
            <n-icon :size="18" color="var(--secondary)"><Layers /></n-icon>
            <span class="rule-label">匹配规则：</span>
            <n-select
              v-model:value="selectedRuleId"
              :options="ruleOptions"
              placeholder="-- 选择规则 --"
              class="rule-select"
              size="small"
            />
          </div>
          <n-space>
            <n-button size="small" type="primary" @click="applyRuleToSheets">
              <template #icon><n-icon><Target /></n-icon></template>
              自动匹配
            </n-button>
            <n-button size="small" @click="clearRuleMapping">清除映射</n-button>
          </n-space>
        </div>
      </n-card>

      <!-- Sheet 配置 -->
      <n-card hoverable style="margin-bottom: 16px">
        <template #header>
          <div class="card-header-row">
            <span>Sheet 配置</span>
            <n-tag size="small" round type="info">{{ sheetCountText }}</n-tag>
          </div>
        </template>

        <div v-for="(file, fname) in fileGroups" :key="fname" class="file-section">
          <div class="file-section-head" :class="{ on: file.hasSelected }">
            <n-icon :size="18" color="var(--primary)"><File /></n-icon>
            <div class="file-meta">
              <div class="file-name">{{ fname }}</div>
              <div class="file-info">{{ file.sheets.length }} 个 Sheet · {{ file.totalRows }} 行</div>
            </div>
            <n-tag size="small" round :type="file.selectedCount > 0 ? 'primary' : 'default'">
              {{ file.selectedCount }}/{{ file.sheets.length }} 选中
            </n-tag>
          </div>

          <n-tabs type="line" size="small" style="margin-top: 8px" :pane-style="{ overflow: 'hidden' }">
            <n-tab-pane
              v-for="s in file.sheets"
              :key="s.key"
              :name="s.key"
            >
              <template #tab>
                <div class="sheet-tab-label">
                  <n-checkbox
                    :checked="sheetStates[s.key].selected"
                    @update:checked="toggleSheetSel(s.key)"
                    @click.stop
                  />
                  <span>{{ s.sheet_name }}</span>
                  <n-tag size="tiny" round>{{ s.row_count }}</n-tag>
                </div>
              </template>

              <div class="header-edit-table">
                <table class="edit-tbl">
                  <thead>
                    <tr>
                      <th v-for="(h, hi) in sheetStates[s.key].headers" :key="hi">
                        <div class="col-num">{{ hi + 1 }}</div>
                        <input
                          type="text"
                          class="col-input"
                          :class="{ mod: sheetStates[s.key].headers[hi] !== sheetStates[s.key].originalHeaders[hi] }"
                          v-model="sheetStates[s.key].headers[hi]"
                          :list="`cols-${s.key}`"
                        />
                        <div
                          v-if="sheetStates[s.key].headers[hi] !== sheetStates[s.key].originalHeaders[hi]"
                          class="col-orig"
                        >
                          原始: {{ sheetStates[s.key].originalHeaders[hi] }}
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, ri) in (sheetStates[s.key].sample_rows || [])" :key="ri">
                      <td v-for="(cell, ci) in row" :key="ci" :title="cell || ''">
                        {{ cell || '' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
                <datalist :id="`cols-${s.key}`">
                  <option v-for="c in allColumns" :key="c" :value="c" />
                </datalist>
              </div>
            </n-tab-pane>
          </n-tabs>
        </div>
      </n-card>

      <!-- 省份选择 -->
      <n-card hoverable style="margin-bottom: 16px">
        <template #header>
          <div class="card-header-row">
            <span>筛选省份</span>
            <n-tag size="small" round type="success">已选 {{ selectedProvinces.length }} 个</n-tag>
          </div>
        </template>

        <div class="prov-groups">
          <n-button
            v-for="g in Object.keys(PROV_GROUPS)"
            :key="g"
            size="small"
            round
            @click="selectProvGroup(g)"
          >
            {{ g }}
          </n-button>
          <n-button size="small" round @click="selectAllProv">全选</n-button>
          <n-button size="small" round @click="clearProv">清空</n-button>
        </div>

        <n-input
          v-model:value="provSearch"
          placeholder="搜索省份..."
          clearable
          size="small"
          class="prov-search"
        >
          <template #prefix><n-icon><Search /></n-icon></template>
        </n-input>

        <div class="prov-tags">
          <div
            v-for="r in filteredRegions"
            :key="r.name"
            class="prov-tag"
            :class="{ on: selectedProvinces.includes(r.name) }"
            @click="toggleProv(r.name)"
          >
            {{ r.name }}
          </div>
        </div>

        <div v-if="selectedProvinces.length > 0" class="prov-bar">
          已选择 {{ selectedProvinces.length }} 个省份：{{ selectedProvinces.join('、') }}
        </div>
      </n-card>

      <!-- 交货号区间筛选 -->
      <n-card hoverable style="margin-bottom: 16px">
        <template #header>
          <div class="card-header-row">
            <span>交货号区间</span>
            <n-tag size="small" round :type="deliveryMin || deliveryMax ? 'warning' : 'default'">
              {{ deliveryMin || deliveryMax ? '已设置' : '不筛选' }}
            </n-tag>
          </div>
        </template>

        <div class="delivery-range-row">
          <n-input-number
            v-model:value="deliveryMin"
            placeholder="最小交货号"
            :show-button="false"
            size="small"
            class="delivery-input"
            clearable
          />
          <span class="range-sep">—</span>
          <n-input-number
            v-model:value="deliveryMax"
            placeholder="最大交货号"
            :show-button="false"
            size="small"
            class="delivery-input"
            clearable
          />
          <n-button size="small" quaternary @click="deliveryMin = null; deliveryMax = null">清除</n-button>
        </div>
        <p class="delivery-hint">可选：填入交货号区间（如 2424796922 ~ 2424802864），只合并该区间内的数据</p>
      </n-card>

      <div class="step-actions">
        <n-button @click="goStep(1)">← 重新上传</n-button>
        <n-button type="primary" size="large" :loading="merging" @click="processMerge">
          <template #icon><n-icon><Zap /></n-icon></template>
          开始合并
        </n-button>
      </div>
    </div>

    <!-- Step 3: 合并结果 -->
    <div v-if="currentStep === 3" class="step-content animate-fade">
      <n-card hoverable>
        <!-- 统计 -->
        <div class="stats-grid">
          <div class="stat">
            <div class="stat-label">输出Sheet</div>
            <div class="stat-value">{{ stats.sheet_count || 0 }}</div>
            <div class="stat-desc">个工作表</div>
          </div>
          <div class="stat accent">
            <div class="stat-label">合并行数</div>
            <div class="stat-value">{{ stats.total_merged_rows || 0 }}</div>
            <div class="stat-desc">行数据</div>
          </div>
          <div class="stat amber">
            <div class="stat-label">{{ stats.provinces && stats.provinces.length > 0 ? '筛选结果' : '合并结果' }}</div>
            <div class="stat-value">{{ stats.filtered_rows || 0 }}</div>
            <div class="stat-desc">{{ stats.provinces && stats.provinces.length > 0 ? stats.provinces.join('、') : '全部数据' }}</div>
          </div>
          <div class="stat purple">
            <div class="stat-label">交货汇总</div>
            <div class="stat-value">{{ stats.pivot_delivery_count || 0 }}</div>
            <div class="stat-desc">个交货号</div>
          </div>
        </div>

        <!-- 奥妙统计 -->
        <div v-if="stats.omo_detail_count > 0" class="omo-stats-bar">
          <n-icon :size="16" color="var(--secondary)"><Layers /></n-icon>
          <span>奥妙明细 <strong>{{ stats.omo_detail_count }}</strong> 行</span>
          <span class="omo-divider">|</span>
          <span>奥妙小计 <strong>{{ stats.omo_subtotal_count }}</strong> 个交货号</span>
        </div>

        <!-- 预览 -->
        <div v-if="previews && previews.length" class="preview-section">
          <div v-for="(pv, pi) in previewTables" :key="pi" class="result-card">
            <div class="result-head">
              <div class="rh-title">
                <span class="dot"></span>
                {{ pv.sheet_name || '数据预览' }}
              </div>
              <n-tag size="small" round type="success">{{ pv.total }} 行</n-tag>
            </div>
            <div class="result-body">
              <!-- 移动端：卡片式展示 -->
              <div v-if="isMobile" class="preview-cards">
                <div v-for="(row, ri) in pv.data" :key="ri" class="preview-card">
                  <div v-for="(h, hi) in pv.headers" :key="hi" class="preview-card-row">
                    <span class="preview-card-label">{{ h }}</span>
                    <span class="preview-card-value">{{ row[h] || '' }}</span>
                  </div>
                </div>
              </div>
              <!-- 桌面端：数据表格 -->
              <n-data-table
                v-else
                :columns="pv.columns"
                :data="pv.data"
                :row-key="(row, index) => index"
                :bordered="false"
                size="small"
                :max-height="400"
                :scroll-x="pv.headers.length * 120"
              />
            </div>
            <div v-if="pv.total > pv.preview_count" class="result-note">
              显示前 {{ pv.preview_count }} 行，共 {{ pv.total }} 行，完整数据请下载 Excel
            </div>
          </div>
        </div>

        <n-empty v-else description="未筛选到匹配数据" style="padding: 40px" />

        <div class="step-actions" style="margin-top: 24px">
          <n-button @click="goStep(1)">重新开始</n-button>
          <n-button type="primary" size="large" @click="downloadLatest">
            <template #icon><n-icon><Download /></n-icon></template>
            下载 Excel
          </n-button>
        </div>
      </n-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { NButton, NCard, NCheckbox, NDataTable, NEmpty, NIcon, NInput, NInputNumber, NSelect, NSpace, NStep, NSteps, NTabPane, NTabs, NTag, NUpload, NUploadDragger, useDialog, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { fileApi, regionApi } from '@/api'
import { useMergeStore } from '@/stores/merge'
import { useResponsive } from '@/composables/useResponsive'
import {
  Upload, File, Close, Search, Target, Zap, Download, Layers,
} from '@/utils/icons'

const message = useMessage()
const dialog = useDialog()

// Pinia store：合并流程状态持久化，页面切换不丢失进度
const mergeStore = useMergeStore()
const { currentStep, analyzeData, selectedProvinces, selectedRuleId } = storeToRefs(mergeStore)

// 响应式断点：移动端预览表格 → 卡片切换
const { isMobile } = useResponsive()

const fileList = ref([])
const selectedFiles = ref([])
const analyzing = ref(false)
const merging = ref(false)

// 分析结果（本地，随组件重建）
const sheetStates = reactive({})
const allColumns = ref([])
const rulesData = ref([])

// 省份（搜索框为本地，选中项存于 store）
const regions = ref([])
const provSearch = ref('')

// 交货号区间（本地）
const deliveryMin = ref(null)
const deliveryMax = ref(null)

const PROV_GROUPS = {
  '华北': ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区'],
  '东北': ['辽宁省', '吉林省', '黑龙江省'],
  '华东': ['上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省'],
  '华中': ['河南省', '湖北省', '湖南省'],
  '华南': ['广东省', '广西壮族自治区', '海南省'],
  '西南': ['重庆市', '四川省', '贵州省', '云南省', '西藏自治区'],
  '西北': ['陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区'],
}

// 计算属性
const sheetCountText = computed(() => {
  const count = Object.keys(sheetStates).length
  return `${count} 个 Sheet`
})

const fileGroups = computed(() => {
  const groups = {}
  if (!analyzeData.value) return groups
  for (const s of analyzeData.value.sheets) {
    const key = `${s.filename}::${s.sheet_name}`
    if (!groups[s.filename]) {
      groups[s.filename] = {
        sheets: [],
        totalRows: 0,
        selectedCount: 0,
        hasSelected: false,
      }
    }
    groups[s.filename].sheets.push({ ...s, key })
    groups[s.filename].totalRows += s.row_count
    if (sheetStates[key]?.selected) {
      groups[s.filename].selectedCount++
      groups[s.filename].hasSelected = true
    }
  }
  return groups
})

const ruleOptions = computed(() => {
  return rulesData.value.map(r => ({
    label: `${r.name} (${r.standard_headers.length} 个目标列名)`,
    value: r.id,
  }))
})

const filteredRegions = computed(() => {
  if (!provSearch.value) return regions.value
  const q = provSearch.value.toLowerCase()
  return regions.value.filter(r => r.name.toLowerCase().includes(q))
})

const stats = ref({})
const previews = ref([])

// 预览表格的 columns/data 预计算，避免模板内联 .map() 每次渲染重建
const previewTables = computed(() => {
  if (!previews.value || !previews.value.length) return []
  return previews.value.map(pv => ({
    ...pv,
    columns: pv.headers.map(h => ({ title: h, key: h, ellipsis: { tooltip: true }, width: 120 })),
    data: pv.rows.map(row => {
      const obj = {}
      pv.headers.forEach((h, i) => { obj[h] = row[i] || '' })
      return obj
    }),
  }))
})

// 方法
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

function handleFileChange({ fileList: newList }) {
  // 文件大小校验：过滤掉超过 50MB 的文件
  const oversized = newList.filter(f => f.file && f.file.size > MAX_FILE_SIZE)
  if (oversized.length > 0) {
    const names = oversized.map(f => f.name).join('、')
    message.warning(`以下文件超过 50MB 限制，已被过滤：${names}`)
  }

  const validFiles = newList
    .filter(f => f.file && /\.(xlsx|xls)$/i.test(f.name) && f.file.size <= MAX_FILE_SIZE)

  fileList.value = validFiles
  selectedFiles.value = validFiles
    .map(f => f.file)
    .filter((f, i, arr) => arr.findIndex(x => x.name === f.name) === i)
}

function removeFile(idx) {
  const target = selectedFiles.value[idx]
  if (!target) return
  selectedFiles.value.splice(idx, 1)
  fileList.value = fileList.value.filter(f => f.name !== target.name)
}

async function analyzeFiles() {
  if (!selectedFiles.value.length) return
  analyzing.value = true
  const loadingMsg = message.loading('正在分析表头...', { duration: 0 })
  try {
    const fd = new FormData()
    for (const f of selectedFiles.value) {
      fd.append('files', f)
    }
    const data = await fileApi.analyze(fd)
    if (data.status === 'success') {
      mergeStore.setAnalyzeData(data)
      allColumns.value = data.all_columns || []
      rulesData.value = data.rules || []
      initSheetStates(data)
      if (data.regions) {
        regions.value = data.regions
      }
      currentStep.value = 2
      // 如果有规则，自动选中第一个并应用
      if (rulesData.value.length > 0) {
        selectedRuleId.value = rulesData.value[0].id
        applyRuleToSheets()
      } else {
        message.success(`已读取 ${data.sheets.length} 个 Sheet`)
      }
    } else {
      message.error(data.detail || '分析失败')
    }
  } catch (e) {
    message.error('请求出错: ' + e.message)
  } finally {
    loadingMsg.destroy()
    analyzing.value = false
  }
}

function initSheetStates(data) {
  // 清空
  Object.keys(sheetStates).forEach(k => delete sheetStates[k])

  let bestKey = null
  let bestScore = -1
  for (const s of data.sheets) {
    const key = `${s.filename}::${s.sheet_name}`
    const hasStreet = s.headers.some(h => h.includes('街道') && !h.includes('街道2') && !h.includes('街道 3'))
    const score = (hasStreet ? 1000 : 0) + s.row_count
    if (score > bestScore) {
      bestScore = score
      bestKey = key
    }
    sheetStates[key] = {
      selected: false,
      headers: [...s.headers],
      originalHeaders: [...s.headers],
      row_count: s.row_count,
      sample_rows: s.sample_rows || [],
      filename: s.filename,
      sheet_name: s.sheet_name,
    }
  }
  // 只默认选中最佳 Sheet
  if (bestKey && sheetStates[bestKey]) {
    sheetStates[bestKey].selected = true
  }
}

function toggleSheetSel(key) {
  if (sheetStates[key]) {
    sheetStates[key].selected = !sheetStates[key].selected
  }
}

function resetAll() {
  // 重置 store 持久化状态（currentStep / analyzeData / selectedProvinces / selectedRuleId）
  mergeStore.reset()
  // 清空本地状态
  fileList.value = []
  selectedFiles.value = []
  Object.keys(sheetStates).forEach(k => delete sheetStates[k])
  allColumns.value = []
  rulesData.value = []
  stats.value = {}
  previews.value = []
  provSearch.value = ''
  deliveryMin.value = null
  deliveryMax.value = null
}

function goStep(n) {
  if (n === 1 && currentStep.value > 1) {
    dialog.warning({
      title: '确认重新上传',
      content: '当前进度将丢失，确认要重新上传吗？',
      positiveText: '确认',
      negativeText: '取消',
      onPositiveClick: () => {
        resetAll()
      },
    })
    return
  }
  currentStep.value = n
}

function normalizeStr(s) {
  if (!s) return ''
  return s.trim().toLowerCase().replace(/\s/g, '').replace(/_/g, '')
}

function applyRuleToSheets() {
  if (!selectedRuleId.value) {
    message.warning('请先选择一个规则')
    return
  }
  const rule = rulesData.value.find(r => r.id === selectedRuleId.value)
  if (!rule) {
    message.error('规则未找到')
    return
  }
  // 前端仅做预览用简单匹配：normalizeStr 归一化后精确匹配 source_columns。
  // 真正的列匹配在 /api/process 时由后端完成，此处不影响最终合并结果。
  const stdHeaders = rule.standard_headers || []
  let totalMatched = 0
  for (const key of Object.keys(sheetStates)) {
    const st = sheetStates[key]
    const usedTargets = new Set()
    st.originalHeaders.forEach((header, idx) => {
      const hs = header ? String(header) : ''
      if (!hs) return
      const hsNorm = normalizeStr(hs)
      if (!hsNorm) return
      let matched = null
      for (const sh of stdHeaders) {
        const target = sh.name
        if (!target || usedTargets.has(target)) continue
        const cols = (sh.source_columns || []).map(normalizeStr).filter(Boolean)
        if (cols.includes(hsNorm)) {
          matched = target
          break
        }
      }
      if (matched) {
        usedTargets.add(matched)
        st.headers[idx] = matched
        totalMatched++
      }
    })
  }
  message.success(`已按规则「${rule.name}」自动匹配 ${totalMatched} 列`)
}

function clearRuleMapping() {
  for (const key of Object.keys(sheetStates)) {
    const st = sheetStates[key]
    st.headers = [...st.originalHeaders]
  }
  selectedRuleId.value = null
  message.success('已清除所有映射')
}

async function processMerge() {
  const selected = []
  const mappings = {}
  for (const key of Object.keys(sheetStates)) {
    if (sheetStates[key].selected) {
      selected.push(key)
      const st = sheetStates[key]
      const mod = {}
      st.headers.forEach((h, i) => {
        if (h !== st.originalHeaders[i] && st.originalHeaders[i]) {
          mod[st.originalHeaders[i]] = h
        }
      })
      if (Object.keys(mod).length > 0) mappings[key] = mod
    }
  }
  if (selected.length === 0) {
    message.warning('请至少勾选一个 Sheet')
    return
  }

  merging.value = true
  const loadingMsg = message.loading('正在合并数据...', { duration: 0 })
  try {
    const fd = new FormData()
    fd.append('session_id', analyzeData.value.session_id)
    fd.append('mappings', JSON.stringify(mappings))
    fd.append('selected_sheets', JSON.stringify(selected))
    fd.append('provinces', JSON.stringify(selectedProvinces.value))
    if (selectedRuleId.value) fd.append('rule_id', selectedRuleId.value)
    if (deliveryMin.value) fd.append('delivery_min', String(deliveryMin.value))
    if (deliveryMax.value) fd.append('delivery_max', String(deliveryMax.value))

    const data = await fileApi.process(fd)
    if (data.status === 'success') {
      stats.value = data.stats || {}
      previews.value = data.previews || []
      currentStep.value = 3
      const action = stats.value.provinces && stats.value.provinces.length > 0 ? '筛选' : '合并'
      message.success(`${action}完成，共 ${stats.value.filtered_rows} 行`)
    } else {
      message.error(data.detail || '处理失败')
    }
  } catch (e) {
    message.error('请求出错: ' + e.message)
  } finally {
    loadingMsg.destroy()
    merging.value = false
  }
}

async function downloadLatest() {
  const loadingMsg = message.loading('正在准备下载...', { duration: 0 })
  try {
    const sessionId = analyzeData.value?.session_id
    const resp = await fetch(fileApi.download(sessionId), { credentials: 'same-origin' })
    if (!resp.ok) {
      let detail = `下载失败 (HTTP ${resp.status})`
      try {
        const err = await resp.json()
        detail = err.detail || detail
      } catch (_) {}
      message.error(detail)
      return
    }
    // 解析文件名
    const disposition = resp.headers.get('content-disposition')
    let filename = '合并结果.xlsx'
    if (disposition) {
      const match = disposition.match(/filename\*?=(?:UTF-8'')?(["']?)([^;"']+)\1/i)
      if (match) filename = decodeURIComponent(match[2])
    }
    // Blob 下载
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

function toggleProv(name) {
  const arr = selectedProvinces.value
  if (arr.includes(name)) {
    selectedProvinces.value = arr.filter(p => p !== name)
  } else {
    selectedProvinces.value = [...arr, name]
  }
}

function selectProvGroup(group) {
  const provs = PROV_GROUPS[group]
  if (!provs) return
  const arr = selectedProvinces.value
  const allSelected = provs.every(p => arr.includes(p))
  if (allSelected) {
    selectedProvinces.value = arr.filter(p => !provs.includes(p))
  } else {
    const merged = new Set(arr)
    provs.forEach(p => merged.add(p))
    selectedProvinces.value = [...merged]
  }
}

function selectAllProv() {
  selectedProvinces.value = regions.value.map(r => r.name)
}

function clearProv() {
  selectedProvinces.value = []
}

async function loadRegions() {
  const data = await regionApi.list()
  if (data.status === 'success' && data.regions) {
    regions.value = data.regions
  }
}

onMounted(() => {
  loadRegions()
  // 页面重新挂载时，若 store 中仍保留分析结果但本地 sheetStates 已丢失，则重建之
  if (analyzeData.value && Object.keys(sheetStates).length === 0) {
    allColumns.value = analyzeData.value.all_columns || []
    rulesData.value = analyzeData.value.rules || []
    initSheetStates(analyzeData.value)
    if (analyzeData.value.regions) {
      regions.value = analyzeData.value.regions
    }
  }
  // 合并结果（stats/previews）为本地状态，重新挂载后会丢失；
  // 若仍停留在结果步骤但没有预览数据，回退到配置步骤避免空页面
  if (currentStep.value === 3 && (!previews.value || previews.value.length === 0)) {
    currentStep.value = analyzeData.value ? 2 : 1
  }
})
</script>

<style scoped>
.page-view {
  padding: 32px;
  max-width: 1100px;
  margin: 0 auto;
  animation: blossom-in .4s var(--ease-spring) both;
}

.page-header {
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
  color: var(--text-3);
  font-weight: 500;
}

.steps-bar {
  margin-bottom: 28px;
}

.step-content {
  margin-top: 8px;
}

.upload-card {
  border-radius: var(--r-lg);
}

.upload-dragger-content {
  padding: 40px 20px;
  text-align: center;
}

.upload-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-2);
  margin: 12px 0 4px;
}

.upload-hint {
  font-size: 12px;
  color: var(--text-4);
}

.file-chips {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--muted);
  border-radius: var(--r-sm);
  border: 1px solid var(--border-l);
}

.chip-name {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip-size {
  font-size: 12px;
  color: var(--text-4);
}

.rule-selector-card {
  margin-bottom: 16px;
}

.rule-selector-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.rule-selector-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rule-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-2);
}

.card-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-section {
  margin-bottom: 20px;
}

.file-section-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--muted);
  border-radius: var(--r-sm);
  border: 1px solid var(--border-l);
}

.file-section-head.on {
  border-color: var(--primary-l);
  background: var(--primary-bg);
}

.file-meta {
  flex: 1;
}

.file-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}

.file-info {
  font-size: 12px;
  color: var(--text-4);
}

.sheet-tab-label {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

/* Tab nav: constrain width and enable horizontal scroll for overflow */
:deep(.n-tabs) {
  max-width: 100%;
}

:deep(.n-tabs-nav) {
  max-width: 100%;
  overflow: hidden;
}

/* Override Naive UI's overflow:hidden to enable native horizontal scroll */
:deep(.n-tabs-nav-scroll-wrapper) {
  overflow-x: auto !important;
  overflow-y: hidden !important;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

/* Thin scrollbar styling */
:deep(.n-tabs-nav-scroll-wrapper::-webkit-scrollbar) {
  height: 4px;
}
:deep(.n-tabs-nav-scroll-wrapper::-webkit-scrollbar-track) {
  background: transparent;
}
:deep(.n-tabs-nav-scroll-wrapper::-webkit-scrollbar-thumb) {
  background: var(--border);
  border-radius: 2px;
}
:deep(.n-tabs-nav-scroll-wrapper::-webkit-scrollbar-thumb:hover) {
  background: var(--primary);
}

/* v-x-scroll inner container should not constrain width */
:deep(.n-tabs .v-x-scroll) {
  overflow: visible !important;
}

/* Tab content scroll area */
.header-edit-table {
  overflow-x: auto;
  overflow-y: hidden;
  max-width: 100%;
  -webkit-overflow-scrolling: touch;
}

/* Ensure tab pane doesn't expand beyond card width */
:deep(.n-tab-pane) {
  min-width: 0;
  overflow: hidden;
}

.edit-tbl {
  border-collapse: collapse;
  font-size: 12px;
  table-layout: auto;
}

.edit-tbl th {
  padding: 8px 6px;
  text-align: left;
  vertical-align: top;
  min-width: 90px;
  max-width: 160px;
  word-wrap: break-word;
  word-break: break-word;
}

.col-num {
  font-size: 10px;
  color: var(--text-4);
  margin-bottom: 4px;
}

.col-input {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 16px;
  font-family: inherit;
  background: var(--surface);
  color: var(--text);
}

/* 桌面端缩小字体（移动端保持 16px 防止 iOS 自动缩放） */
@media (min-width: 768px) {
  .col-input {
    font-size: 13px;
  }
}

.col-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-bg);
}

.col-input.mod {
  border-color: var(--accent);
  background: var(--accent-bg);
  color: var(--accent-d);
}

.col-orig {
  font-size: 10px;
  color: var(--text-4);
  margin-top: 2px;
}

.edit-tbl td {
  padding: 6px;
  font-size: 12px;
  color: var(--text-2);
  min-width: 90px;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-bottom: 1px solid var(--border-l);
}

.prov-groups {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.prov-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
}

.prov-tag {
  padding: 6px 14px;
  border-radius: var(--r-pill);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-2);
  transition: all 0.15s ease;
}

.prov-tag:hover {
  border-color: var(--primary-l);
  background: var(--primary-bg);
}

.prov-tag.on {
  background: var(--grad-sakura);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 2px 8px rgba(240, 101, 149, 0.25);
}

.prov-tag.on:hover {
  box-shadow: 0 4px 12px rgba(240, 101, 149, 0.35);
  transform: translateY(-1px);
}

.prov-bar {
  margin-top: 12px;
  padding: 8px 14px;
  background: var(--primary-bg);
  border-radius: var(--r-pill);
  font-size: 13px;
  font-weight: 700;
  color: var(--primary-d);
  display: inline-flex;
  align-items: center;
}

.step-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
}

/* Stats grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  .page-view {
    padding: 20px 16px;
  }
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

/* 奥妙统计条 */
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

/* 交货号区间 */
.delivery-range-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.rule-select {
  width: 280px;
}

.delivery-input {
  width: 200px;
}

.prov-search {
  max-width: 300px;
  margin: 12px 0;
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

/* Preview */
.preview-section {
  margin-top: 24px;
}

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

.result-body {
  padding: 0;
}

/* 移动端预览卡片 */
.preview-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
}

.preview-card {
  border: 1px solid var(--border-l);
  border-radius: var(--r-sm);
  padding: 10px 12px;
  background: var(--surface);
}

.preview-card-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid var(--border-l);
  font-size: 12px;
}

.preview-card-row:last-child {
  border-bottom: none;
}

.preview-card-label {
  flex: 0 0 38%;
  font-weight: 600;
  color: var(--text-3);
  word-break: break-all;
}

.preview-card-value {
  flex: 1;
  color: var(--text-2);
  word-break: break-all;
}

.result-note {
  padding: 8px 14px;
  font-size: 12px;
  color: var(--text-4);
  background: var(--muted);
  text-align: center;
}

/* ---- Naive UI component theme overrides (pink sakura) ---- */
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

:deep(.n-steps .n-step-indicator--focus) {
  color: var(--primary);
}

:deep(.n-tabs.n-tabs--segment-type .n-tab-pane__tab--active) {
  font-weight: 700;
}

/* ---- Mobile responsive ---- */
@media (max-width: 768px) {
  .page-view {
    padding: 16px 12px;
  }
  .page-header {
    flex-direction: column;
    gap: 8px;
  }
  .rule-selector-row {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
  .rule-selector-left {
    flex-wrap: wrap;
  }
  .rule-select {
    width: 100%;
    flex: 1;
    min-width: 120px;
  }
  .delivery-input {
    width: 100%;
    flex: 1;
    min-width: 100px;
  }
  .prov-search {
    max-width: 100%;
  }
  .page-title {
    font-size: 20px;
  }
  .page-desc {
    font-size: 12px;
  }
  .upload-card :deep(.n-upload) {
    --n-padding: 20px;
  }
  :deep(.n-card > .n-card__content) {
    padding: 14px;
  }
  .file-section-head {
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 10px;
  }
  .file-name {
    font-size: 13px;
  }
  .file-info {
    font-size: 11px;
  }
  :deep(.n-tabs-tab) {
    padding: 6px 8px;
  }
  .sheet-tab-label {
    gap: 4px;
  }
  .sheet-tab-label span {
    font-size: 12px;
  }
  .edit-tbl th {
    min-width: 80px;
    padding: 6px 4px;
  }
  .edit-tbl td {
    font-size: 11px;
    padding: 4px;
  }
  .col-input {
    padding: 4px 6px;
  }
  .stat {
    padding: 14px;
  }
  .step-actions {
    flex-direction: column;
    gap: 8px;
  }
  .step-actions .n-button {
    width: 100%;
  }
  .prov-tag {
    padding: 5px 10px;
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
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>