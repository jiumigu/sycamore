import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as timerApi from '@/shared/api/timerApi'
import type { TimerPrevResult, TimerSession, TimerStopResult } from '@/shared/types/timer'

/**
 * 实时计时 · 全局单例状态
 *
 * 🔴 计时锚点来自**后端**的 `elapsed_seconds`，本地只负责累加增量：
 *    `已流逝 = 后端值 + (本地此刻 − 收到响应的时刻)`。
 *    直接用 `Date.now() − start_time` 会把「本地与服务端的时钟差」算进时长里，
 *    打开就显示错值、甚至负数，且没有任何报错。
 *
 * 🔴 库是唯一真源：不把「正在计时」只存内存/localStorage —— 刷新、换标签页、
 *    换设备都以 `GET /timer/running/` 为准（窗口重新聚焦时也会对一次）。
 */

const session = ref<TimerSession | null>(null)
const baseElapsed = ref(0)
const anchorAt = ref(0)
/** 每秒自增，仅用来驱动 computed 重算（时间本身不存这里） */
const tick = ref(0)
const loading = ref(false)

let intervalId: ReturnType<typeof setInterval> | null = null
let listenersBound = false
let initialised = false

function pad2(n: number) {
  return String(n).padStart(2, '0')
}

function startTicking() {
  if (intervalId !== null) return
  intervalId = setInterval(() => { tick.value += 1 }, 1000)
}

function stopTicking() {
  if (intervalId === null) return
  clearInterval(intervalId)
  intervalId = null
}

function apply(data: { session: TimerSession | null; elapsed_seconds?: number }) {
  session.value = data.session
  // start/running 直接在顶层给 elapsed_seconds；stop/discard 的回包把它放在 session 里
  baseElapsed.value = data.elapsed_seconds ?? data.session?.elapsed_seconds ?? 0
  anchorAt.value = Date.now()
  tick.value = 0
  if (data.session?.status === 'running') startTicking()
  else stopTicking()
}

const isRunning = computed(() => session.value?.status === 'running')

const elapsedSeconds = computed(() => {
  void tick.value // 建立依赖：靠 tick 每秒重算
  if (!isRunning.value) return baseElapsed.value
  return Math.max(0, baseElapsed.value + Math.floor((Date.now() - anchorAt.value) / 1000))
})

const elapsedText = computed(() => {
  const s = elapsedSeconds.value
  return `${pad2(Math.floor(s / 3600))}:${pad2(Math.floor((s % 3600) / 60))}:${pad2(s % 60)}`
})

/** 上一段会话被自动收尾时的提示 —— 文案只这一份，两个入口共用 */
function notifyPrev(prev: TimerPrevResult | null) {
  if (!prev) return
  if (prev.outcome === 'saved') {
    ElMessage.success(`已停止「${prev.task_name}」，记入 ${prev.duration_hours ?? 0} 小时`)
  } else if (prev.outcome === 'too_short') {
    ElMessage.info(`「${prev.task_name}」不到 ${prev.min_seconds ?? 30} 秒，没有记录`)
  } else if (prev.outcome === 'too_long_dropped') {
    ElMessage.warning(
      `「${prev.task_name}」已超过 ${Math.round((prev.long_seconds ?? 14400) / 3600)} 小时，没有自动记入；需要的话请手工补录`,
    )
  }
}

async function refresh() {
  if (loading.value) return
  loading.value = true
  try {
    const res = await timerApi.getRunning()
    apply(res.data)
  } catch {
    // 读不到就保留现状，绝不把「接口挂了」画成「没在计时」——
    // 那会让人以为计时丢了、再点一次，反而造出第二条会话。
  } finally {
    loading.value = false
  }
}

async function start(taskName: string): Promise<boolean> {
  const name = (taskName || '').trim()
  if (!name) {
    ElMessage.warning('请填写任务名称')
    return false
  }
  loading.value = true
  try {
    const res = await timerApi.startTimer(name)
    apply(res.data)
    notifyPrev(res.data.prev)
    return true
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '开始计时失败')
    return false
  } finally {
    loading.value = false
  }
}

/**
 * 停止并入账。
 * 🔴 超长（>4h）的确认**由后端 409 驱动**，前端不自己判阈值 ——
 *    否则改了 4 小时这个数，前端会静默沿用旧值。
 */
async function stop(notes = '', allowLong = false): Promise<TimerStopResult> {
  if (!session.value) throw new Error('没有正在进行的计时')
  loading.value = true
  try {
    const res = await timerApi.stopTimer(session.value.id, notes, allowLong)
    apply(res.data)
    return res.data.result
  } finally {
    loading.value = false
  }
}

async function discard(): Promise<TimerStopResult> {
  if (!session.value) throw new Error('没有正在进行的计时')
  loading.value = true
  try {
    const res = await timerApi.discardTimer(session.value.id)
    apply(res.data)
    return res.data.result
  } finally {
    loading.value = false
  }
}

function bindListeners() {
  if (listenersBound) return
  listenersBound = true
  if (typeof window === 'undefined') return
  // 换标签页 / 切回窗口时对一次后端：别的窗口可能已经停了
  window.addEventListener('focus', () => { void refresh() })
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) void refresh()
  })
}

function init() {
  if (initialised) return
  initialised = true
  bindListeners()
  void refresh()
}

export function useTimer() {
  return {
    session,
    isRunning,
    loading,
    elapsedSeconds,
    elapsedText,
    init,
    refresh,
    start,
    stop,
    discard,
  }
}
