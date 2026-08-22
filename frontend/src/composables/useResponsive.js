/**
 * useResponsive — JS 级响应式判断
 * 使用 requestAnimationFrame 节流 resize 事件
 * 用于表格→卡片切换、分页尺寸调整等 CSS 无法解决的场景
 */
import { ref, onMounted, onUnmounted } from 'vue'

export function useResponsive(breakpoint = 768) {
  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(false)

  let rafId = null

  function update() {
    const w = window.innerWidth
    isMobile.value = w < breakpoint
    isTablet.value = w >= breakpoint && w < 1024
    isDesktop.value = w >= 1024
  }

  function onResize() {
    if (rafId) cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(update)
  }

  onMounted(() => {
    update()
    window.addEventListener('resize', onResize, { passive: true })
  })

  onUnmounted(() => {
    window.removeEventListener('resize', onResize)
    if (rafId) cancelAnimationFrame(rafId)
  })

  return { isMobile, isTablet, isDesktop }
}
