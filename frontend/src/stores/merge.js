/**
 * 合并流程状态管理
 * 将 Merge.vue 的组件内状态提取到 Pinia store，
 * 使页面切换后不丢失进度
 */
import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export const useMergeStore = defineStore('merge', () => {
  const currentStep = ref(1)
  const analyzeData = ref(null)
  const selectedFiles = ref([])
  const sheetStates = reactive({})
  const selectedProvinces = ref([])
  const selectedRuleId = ref(null)
  const deliveryStart = ref('')
  const deliveryEnd = ref('')
  const mergeResult = ref(null)

  function reset() {
    currentStep.value = 1
    analyzeData.value = null
    selectedFiles.value = []
    Object.keys(sheetStates).forEach(k => delete sheetStates[k])
    selectedProvinces.value = []
    selectedRuleId.value = null
    deliveryStart.value = ''
    deliveryEnd.value = ''
    mergeResult.value = null
  }

  function setAnalyzeData(data) {
    analyzeData.value = data
  }

  function setFiles(files) {
    selectedFiles.value = files
  }

  function setSheetState(key, state) {
    sheetStates[key] = state
  }

  return {
    currentStep,
    analyzeData,
    selectedFiles,
    sheetStates,
    selectedProvinces,
    selectedRuleId,
    deliveryStart,
    deliveryEnd,
    mergeResult,
    reset,
    setAnalyzeData,
    setFiles,
    setSheetState,
  }
})
