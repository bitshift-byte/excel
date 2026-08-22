<template>
  <div class="page-view">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">规则列表</h1>
        <p class="page-desc">查看分配给你的列名匹配规则和值映射</p>
      </div>
      <div class="header-stats" v-if="rules.length > 0">
        <div class="stat-chip">
          <span class="stat-num">{{ rules.length }}</span>
          <span class="stat-label">规则集</span>
        </div>
        <div class="stat-chip">
          <span class="stat-num">{{ totalHeaders }}</span>
          <span class="stat-label">目标列</span>
        </div>
        <div class="stat-chip">
          <span class="stat-num">{{ totalMappings }}</span>
          <span class="stat-label">值映射</span>
        </div>
      </div>
    </div>

    <!-- 搜索栏 -->
    <div v-if="rules.length > 0" class="search-bar">
      <n-input
        v-model:value="searchText"
        placeholder="搜索规则名、目标列名或匹配列名…"
        clearable
        size="medium"
      >
        <template #prefix>
          <n-icon :size="16" color="var(--text-3)"><Search /></n-icon>
        </template>
      </n-input>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && rules.length === 0" class="empty-card">
      <div class="rule-empty">
        <div class="empty-icon">
          <n-icon :size="36" color="var(--primary)"><Layers /></n-icon>
        </div>
        <div class="rep-title">暂无分配的规则</div>
        <div class="rep-desc">请联系管理员为你分配规则，或查看下方示例了解规则的作用</div>
        <div class="example-box">
          <div class="example-label">示例</div>
          <div class="example-content">
            规则名称：联合利华标准模板<br>
            目标列名「客户名称」← 可匹配源列名：客户名称、Customer Name、客户<br>
            目标列名「街道」← 可匹配源列名：街道、街道地址、Address
          </div>
        </div>
      </div>
    </div>

    <!-- 规则卡片列表 -->
    <div v-if="!loading && filteredRules.length > 0" class="rules-list">
      <div
        v-for="(r, ri) in filteredRules"
        :key="r.id"
        class="rule-card-wrapper"
        :style="{ animationDelay: ri * 60 + 'ms' }"
      >
        <div :class="['rule-card', { expanded: expandedId === r.id }]">
          <!-- 卡片头部 -->
          <div class="rule-card-head" @click="toggleRuleCard(r.id)">
            <div class="rch-left">
              <div class="rch-icon">
                <n-icon :size="18" color="var(--primary)"><Layers /></n-icon>
              </div>
              <div class="rch-info">
                <div class="rch-name">{{ r.name }}</div>
                <div class="rch-meta">
                  <span class="meta-badge">{{ r.standard_headers.length }} 列</span>
                  <span v-if="countMappings(r) > 0" class="meta-badge meta-badge--map">{{ countMappings(r) }} 映射</span>
                  <span v-if="r.updated_at" class="meta-time">{{ r.updated_at }}</span>
                </div>
              </div>
            </div>
            <div class="rch-right">
              <div v-if="expandedId === r.id" class="collapse-btn" @click.stop="toggleRuleCard(r.id)">
                <n-icon :size="16"><ChevronUp /></n-icon>
              </div>
              <div v-else class="expand-btn" @click.stop="toggleRuleCard(r.id)">
                <span>展开</span>
                <n-icon :size="14"><ChevronDown /></n-icon>
              </div>
            </div>
          </div>

          <!-- 卡片内容 -->
          <Transition name="expand">
            <div v-show="expandedId === r.id" class="rule-card-body">
              <div class="headers-grid">
                <div
                  v-for="(sh, si) in r.standard_headers"
                  :key="si"
                  class="std-header-block"
                  :class="{ 'has-mapping': sh.value_mappings && sh.value_mappings.length > 0 }"
                >
                  <div class="shb-head">
                    <div class="shb-num">{{ si + 1 }}</div>
                    <div class="shb-name">{{ sh.name }}</div>
                    <div
                      v-if="sh.value_mappings && sh.value_mappings.length > 0"
                      class="shb-map-count"
                    >
                      {{ sh.value_mappings.length }} 条映射
                    </div>
                  </div>
                  <div class="shb-cols">
                    <span
                      v-for="sc in (sh.source_columns || [])"
                      :key="sc"
                      class="col-tag"
                    >
                      {{ sc }}
                    </span>
                    <span v-if="!sh.source_columns || sh.source_columns.length === 0" class="no-cols">
                      未设置匹配列名
                    </span>
                  </div>

                  <!-- 值映射 -->
                  <div v-if="sh.value_mappings && sh.value_mappings.length > 0" class="shb-vm-block">
                    <div v-for="(vm, vi) in sh.value_mappings" :key="vi" class="shb-vm-row">
                      <template v-if="vm.source_file_contains">
                        <span class="vm-vm-tag">文件</span>
                        <span class="vm-text">包含「{{ vm.source_file_contains }}」</span>
                        <span class="vm-text">值「{{ vm.source_value }}」</span>
                        <span class="vm-arrow">→</span>
                        <span class="vm-target">{{ vm.target_value }}</span>
                      </template>
                      <template v-else-if="vm.when_column">
                        <span class="vm-vm-tag vm-vm-tag--col">条件</span>
                        <span class="vm-text">当「{{ vm.when_column }}」=「{{ vm.equals }}」</span>
                        <span class="vm-arrow">→</span>
                        <span class="vm-target">用「{{ vm.use_column }}」列的值</span>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <!-- 无搜索结果 -->
    <div v-if="!loading && rules.length > 0 && filteredRules.length === 0" class="no-result">
      <n-icon :size="32" color="var(--text-4)"><Search /></n-icon>
      <div style="margin-top:8px;font-size:14px;color:var(--text-3)">没有匹配「{{ searchText }}」的规则</div>
    </div>

    <div v-if="loading" class="loading-wrap">
      <n-spin size="medium" />
    </div>
  </div>
</template>

<script setup>
import { NIcon, NInput, NSpin } from 'naive-ui'
import { ref, computed, onMounted } from 'vue'
import { ruleApi } from '@/api'
import { Layers, ChevronForward, ChevronDown, ChevronUp, Search } from '@/utils/icons'

const rules = ref([])
const loading = ref(true)
const expandedId = ref(null)
const searchText = ref('')

const totalHeaders = computed(() =>
  rules.value.reduce((sum, r) => sum + (r.standard_headers?.length || 0), 0)
)
const totalMappings = computed(() =>
  rules.value.reduce((sum, r) => sum + countMappings(r), 0)
)

function countMappings(r) {
  return (r.standard_headers || []).reduce((s, sh) => s + (sh.value_mappings?.length || 0), 0)
}

const filteredRules = computed(() => {
  if (!searchText.value.trim()) return rules.value
  const q = searchText.value.toLowerCase()
  return rules.value
    .map(r => {
      const nameMatch = r.name?.toLowerCase().includes(q)
      const filteredHeaders = (r.standard_headers || []).filter(sh => {
        if (sh.name?.toLowerCase().includes(q)) return true
        if (sh.source_columns?.some(sc => sc.toLowerCase().includes(q))) return true
        return false
      })
      if (nameMatch) return r
      if (filteredHeaders.length > 0) {
        return { ...r, standard_headers: filteredHeaders }
      }
      return null
    })
    .filter(Boolean)
})

async function loadRules() {
  loading.value = true
  try {
    const data = await ruleApi.list()
    if (data.status === 'success') {
      rules.value = data.rules || []
      if (rules.value.length > 0) {
        expandedId.value = rules.value[0].id
      }
    }
  } catch (e) {
    // ignore
  } finally {
    loading.value = false
  }
}

function toggleRuleCard(id) {
  expandedId.value = expandedId.value === id ? null : id
}

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.page-view {
  padding: 28px 32px;
  max-width: 1100px;
  margin: 0 auto;
  animation: blossom-in .4s var(--ease-spring) both;
}

/* ============ Header ============ */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.page-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.5px;
  margin: 0 0 4px 0;
}

.page-desc {
  font-size: 13px;
  color: var(--text-3);
  margin: 0;
}

.header-stats {
  display: flex;
  gap: 8px;
}

.stat-chip {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid var(--glass-border);
  border-radius: var(--r-sm);
  padding: 8px 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 64px;
  box-shadow: var(--shadow-sm);
}

.stat-num {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--primary-d);
  line-height: 1.2;
}

.stat-label {
  font-size: 10px;
  color: var(--text-3);
  margin-top: 2px;
}

/* ============ Search ============ */
.search-bar {
  margin-bottom: 16px;
  max-width: 420px;
}

/* ============ Empty State ============ */
.empty-card {
  margin-top: 20px;
}

.rule-empty {
  text-align: center;
  padding: 48px 24px;
  background: var(--surface);
  border: 1px dashed var(--border);
  border-radius: var(--r-lg);
  animation: blossom-in .4s var(--ease-spring) both;
}

.empty-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: var(--primary-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}

.rep-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 6px;
}

.rep-desc {
  font-size: 14px;
  color: var(--text-3);
  margin-bottom: 20px;
}

.example-box {
  background: var(--muted);
  border: 1px solid var(--border-l);
  border-radius: var(--r-md);
  padding: 16px 20px;
  text-align: left;
  max-width: 480px;
  margin: 0 auto;
  transition: border-color var(--dur) var(--ease-spring), box-shadow var(--dur) var(--ease-spring);
}

.example-box:hover {
  border-color: var(--primary-l);
  box-shadow: var(--shadow-sm);
}

.example-label {
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  color: var(--text-3);
  margin-bottom: 8px;
}

.example-content {
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.8;
}

/* ============ Rule Cards ============ */
.rules-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rule-card-wrapper {
  animation: blossom-in .35s var(--ease-spring) both;
}

.rule-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
  transition: border-color var(--dur) var(--ease-spring), box-shadow var(--dur) var(--ease-spring);
}

.rule-card:hover {
  border-color: var(--primary-l);
  box-shadow: var(--shadow-md);
}

.rule-card.expanded {
  border-color: var(--primary-l);
  box-shadow: var(--shadow-md);
}

/* ============ Card Header ============ */
.rule-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  gap: 12px;
  padding: 16px 20px;
  transition: background var(--dur) var(--ease-spring);
}

.rule-card-head:hover {
  background: var(--muted);
}

.rch-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}

.rch-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--r-sm);
  background: var(--primary-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform var(--dur) var(--ease-spring);
}

.rule-card-head:hover .rch-icon {
  transform: scale(1.08);
}

.rch-info {
  min-width: 0;
}

.rch-name {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rch-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.meta-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
  background: var(--primary-bg);
  color: var(--primary-d);
}

.meta-badge--map {
  background: var(--muted-2);
  color: var(--text-2);
}

.meta-time {
  font-size: 11px;
  color: var(--text-4);
}

.rch-right {
  flex-shrink: 0;
}

.expand-btn,
.collapse-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: var(--r-sm);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--dur) var(--ease-spring);
}

.expand-btn {
  background: var(--primary-bg);
  color: var(--primary-d);
}

.expand-btn:hover {
  background: var(--primary-l);
  color: #fff;
}

.collapse-btn {
  color: var(--text-3);
}

.collapse-btn:hover {
  color: var(--primary);
}

/* ============ Card Body ============ */
.rule-card-body {
  padding: 0 20px 16px 20px;
  border-top: 1px solid var(--border-l);
}

.headers-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 12px;
}

.std-header-block {
  padding: 12px 14px;
  background: var(--muted);
  border-radius: var(--r-sm);
  border: 1px solid transparent;
  transition: border-color var(--dur) var(--ease-spring), background var(--dur) var(--ease-spring);
}

.std-header-block:hover {
  background: var(--primary-bg);
  border-color: var(--primary-l);
}

.std-header-block.has-mapping {
  border-color: var(--primary-l);
}

.shb-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.shb-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.shb-name {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shb-map-count {
  font-size: 10px;
  font-weight: 600;
  color: var(--primary-d);
  background: #fff;
  padding: 2px 6px;
  border-radius: 10px;
  flex-shrink: 0;
}

.shb-cols {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.col-tag {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 20px;
  background: #fff;
  color: var(--text-2);
  border: 1px solid var(--border-l);
  transition: all var(--dur) var(--ease-spring);
}

.col-tag:hover {
  border-color: var(--primary-l);
  color: var(--primary-d);
}

.no-cols {
  font-size: 12px;
  color: var(--text-4);
  font-style: italic;
}

/* ============ Value Mappings ============ */
.shb-vm-block {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border-l);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.shb-vm-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-2);
  flex-wrap: wrap;
}

.vm-vm-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  flex-shrink: 0;
}

.vm-vm-tag--col {
  background: #868E96;
}

.vm-text {
  white-space: nowrap;
}

.vm-arrow {
  color: var(--text-4);
  flex-shrink: 0;
}

.vm-target {
  color: var(--primary-d);
  font-weight: 700;
  white-space: nowrap;
}

/* ============ No Results ============ */
.no-result {
  text-align: center;
  padding: 60px 20px;
}

.loading-wrap {
  display: flex;
  justify-content: center;
  padding: 60px;
}

/* ============ Transition ============ */
.expand-enter-active,
.expand-leave-active {
  transition: opacity .3s var(--ease-spring);
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
}

/* ============ Responsive ============ */
@media (max-width: 768px) {
  .page-view {
    padding: 20px 14px;
  }

  .page-header {
    flex-direction: column;
    gap: 12px;
  }

  .page-title {
    font-size: 20px;
  }

  .page-desc {
    font-size: 12px;
  }

  .header-stats {
    width: 100%;
    justify-content: flex-start;
  }

  .stat-chip {
    padding: 6px 10px;
    min-width: 52px;
  }

  .stat-num {
    font-size: 16px;
  }

  .search-bar {
    max-width: 100%;
  }

  .rule-card-head {
    padding: 14px 16px;
  }

  .rch-icon {
    width: 34px;
    height: 34px;
  }

  .rch-name {
    font-size: 14px;
  }

  .expand-btn span,
  .collapse-btn {
    display: none;
  }

  .expand-btn,
  .collapse-btn {
    padding: 6px;
  }

  .rule-card-body {
    padding: 0 12px 12px 12px;
  }

  .headers-grid {
    grid-template-columns: 1fr;
    margin-top: 8px;
  }

  .std-header-block {
    padding: 10px 12px;
  }

  .rule-empty {
    padding: 32px 16px;
  }

  .example-box {
    padding: 12px;
    font-size: 12px;
  }
}

@media (max-width: 480px) {
  .page-view {
    padding: 14px 10px;
  }

  .page-title {
    font-size: 18px;
  }

  .header-stats {
    gap: 6px;
  }

  .stat-chip {
    padding: 5px 8px;
    min-width: 48px;
  }
}
</style>
