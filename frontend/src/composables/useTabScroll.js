import { onMounted, onUnmounted } from 'vue'

/**
 * 全局 Tab 滚轮滚动支持
 * Naive UI 的 n-tabs 在内容溢出时，v-x-scroll 组件会拦截 wheel 事件
 * 此 composable 在 capture 阶段拦截 wheel 事件，直接调整 scrollLeft
 */
export function useTabScroll() {
  let observer = null

  function bindWheel(wrapper) {
    if (wrapper._wheelBound) return
    wrapper._wheelBound = true
    wrapper.addEventListener('wheel', (e) => {
      if (wrapper.scrollWidth <= wrapper.clientWidth) return
      e.preventDefault()
      e.stopPropagation()
      wrapper.scrollLeft += e.deltaY || e.deltaX
    }, { capture: true, passive: false })
  }

  function scanAndBind() {
    const wrappers = document.querySelectorAll('.n-tabs-nav-scroll-wrapper')
    wrappers.forEach(bindWheel)
  }

  onMounted(() => {
    // 初始绑定
    scanAndBind()
    // MutationObserver 监听 DOM 变化，新出现的 tabs 也自动绑定
    observer = new MutationObserver(() => scanAndBind())
    observer.observe(document.body, { childList: true, subtree: true })
  })

  onUnmounted(() => {
    if (observer) observer.disconnect()
  })
}
