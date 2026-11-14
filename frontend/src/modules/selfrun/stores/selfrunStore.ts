import { acceptHMRUpdate, defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '../api/selfrunApi'
import type {
  CurrentPeriodResponse, Heartbeat, KpiTemplate, PeriodExtras, PeriodOption, PeriodStatusExplain,
  PeriodType, PlanScope, SelfRunMetric, SelfRunMetricLog, SelfRunPeriod, SelfRunStage,
  TemplateEnum,
} from '../types/selfrunTypes'

/** 一个「当前周期」的视图态（周、月各一份，两把尺子**正交**，互不覆盖）。 */
interface PeriodView {
  stage: SelfRunStage | null
  period: SelfRunPeriod | null
  /**
   * 当期标识（`2026-W42` / `2026-10`）—— 🔴 **没有阶段时也有值**。
   *
   * 它的用处就一个：让「本周状态」与「本月状态」两页在还没有阶段时
   * 仍然**看得出自己在哪一页**（否则两页一字不差）。
   * 值由后端下发 —— 前端不自己算 ISO 周（跨年会静默差一周）。
   */
  key: string
  /** 半开区间左端。⚠️ `end` 是**不含**的右端，别当「最后一天」显示。 */
  start: string
  end: string
  /** `true` = 现算（进行中）；`false` = 读冻结快照（已归档） */
  live: boolean
  hint: string
  explain: PeriodStatusExplain | null
  /**
   * 当期现算的补充（`what_happened` / `goals` / `time_loss` / `outcomes`）。
   * 🔴 **后端一直在返回，前端以前把它丢了**（`applyCurrent` 只挑了七个字段）——
   *    结果是「本周状态」页拿不到时段轴，只能去复盘抽屉看。
   *    `null` = 还没取到，或还没有进行中的阶段（两者不是一回事，用时分开说）。
   */
  extras: PeriodExtras | null
}

function emptyView(): PeriodView {
  return {
    stage: null, period: null, key: '', start: '', end: '',
    live: true, hint: '', explain: null, extras: null,
  }
}

export const useSelfRunStore = defineStore('selfrun', () => {
  // ── 门面 ────────────────────────────────────────────────
  const loading = ref(false)
  const stage = ref<SelfRunStage | null>(null)
  const metrics = ref<SelfRunMetric[]>([])
  const logs = ref<SelfRunMetricLog[]>([])
  const heartbeatInfo = ref<Heartbeat | null>(null)
  /** 🔴 配色由后端下发（前端不做第二份彩色表）；拿不到时各自兜底灰 */
  const colors = ref<{ verdict: Record<string, string>; period: Record<string, string> }>({
    verdict: {}, period: {},
  })

  // ── 两把尺子（周 / 月）─────────────────────────────────
  const weekly = ref<PeriodView>(emptyView())
  const monthly = ref<PeriodView>(emptyView())

  // ── 历史周期（T3 归档面板用）───────────────────────────
  const periods = ref<SelfRunPeriod[]>([])

  // ── T1 模板库（**可自定义**；增删改都落库）───────────────
  const templates = ref<KpiTemplate[]>([])
  /** 🔴 枚举（含取数器清单）**由后端下发** —— 前端不抄第三份，抄了必漏改且静默 */
  const templateEnum = ref<TemplateEnum | null>(null)

  // ── T1b 按期修订 ────────────────────────────────────────
  const periodOptions = ref<PeriodOption[]>([])

  const hasStage = computed(() => stage.value !== null && stage.value.status !== 'closed')
  const weeklyMetrics = computed(() => metrics.value.filter(m => m.period_type === 'weekly'))
  const monthlyMetrics = computed(() => metrics.value.filter(m => m.period_type === 'monthly'))

  function applyCurrent(periodType: PeriodType, res: CurrentPeriodResponse) {
    const view: PeriodView = {
      stage: res.stage,
      period: res.period,
      key: res.period_key,
      start: res.period_start,
      end: res.period_end,
      live: res.live,
      hint: res.hint ?? '',
      explain: res.status_explain ?? null,
      extras: res.extras ?? null,
    }
    if (periodType === 'weekly') weekly.value = view
    else monthly.value = view
    if (res.colors) colors.value = res.colors
    if (res.heartbeat) heartbeatInfo.value = res.heartbeat
  }

  /** 拉「当前阶段 + KPI 清单」 —— 阶段详情接口一次给全（含变更留痕）。
   *
   *  🔴 必须带 `shape=leaf`：分层之后长阶段与它的小阶段**同时**是 `active`，
   *     只按 `status` 取第一条会拿到长阶段（排序按 `-start_date, -id`，
   *     起点相同就按 id 大的在前）⇒ 页头显示「0 条 KPI」、周/月读一个
   *     永不判定的阶段，而且**不报错**。判据与后端 `get_open_stage()` 同源。
   */
  async function loadStage(silent = false) {
    if (!silent) loading.value = true
    try {
      // 先看有没有进行中的阶段；没有就直接清空（不去赌 id）
      const res = await api.listStages({ status: 'active', shape: 'leaf' })
      let list = res.data
      if (!list.length) {
        const paused = await api.listStages({ status: 'paused', shape: 'leaf' })
        list = paused.data
      }
      if (!list.length) {
        stage.value = null
        metrics.value = []
        logs.value = []
        // ⚠️ 这里**不**清 `weekly` / `monthly`：那两份视图由 `loadBothPeriods()`
        //    无条件刷新（就算没有阶段，「当期是哪一期」也要拿得到）。
        return
      }
      stage.value = list[0]
      const detail = await api.getStage(list[0].id)
      metrics.value = detail.data.metrics
      logs.value = detail.data.logs
    } finally {
      loading.value = false
    }
  }

  async function loadPeriod(periodType: PeriodType) {
    const res = await api.getCurrentPeriod(periodType)
    applyCurrent(periodType, res.data)
    return res.data
  }

  /** 两把尺子**并列**拉 —— 页头要同时显示「本周」与「本月」两个判定。 */
  async function loadBothPeriods() {
    await Promise.all([loadPeriod('weekly'), loadPeriod('monthly')])
  }

  async function loadPeriods(params?: { period_type?: PeriodType; stage_id?: number; limit?: number }) {
    const res = await api.listPeriods(params)
    periods.value = res.data
    return res.data
  }

  // ── T1 模板库 ───────────────────────────────────────────

  /**
   * 拉模板库 + 随列表下发的枚举。
   * 🔴 **写操作之后也要重拉** —— `used_count` 是现算的，不重拉就一直是旧数。
   */
  async function loadTemplates() {
    const res = await api.getTemplates()
    templates.value = res.data.templates
    templateEnum.value = res.data.enum
    return res.data
  }

  async function createTemplate(data: Record<string, unknown>) {
    const res = await api.createTemplate(data)
    await loadTemplates()
    return res.data
  }

  async function updateTemplate(id: number, data: Record<string, unknown>) {
    const res = await api.updateTemplate(id, data)
    await loadTemplates()
    return res.data
  }

  async function deleteTemplate(id: number) {
    const res = await api.deleteTemplate(id)
    await loadTemplates()
    return res.data
  }

  // ── T1b 按期修订 ────────────────────────────────────────

  async function loadPeriodOptions(periodType: PeriodType, count = 6) {
    const res = await api.getPeriodOptions(periodType, count)
    periodOptions.value = res.data.options
    return res.data.options
  }

  /** 设定某一期的目标 —— **写完回读**（口径只有后端一份，前端不自己推算）。 */
  async function setPlan(metricId: number, data: {
    period_key: string; scope: PlanScope
    goal_value: number | null; floor_value: number | null
    goal_why?: string; floor_why?: string; note?: string
  }) {
    const res = await api.setPlan(metricId, data)
    await refreshAfterWrite()
    return res.data
  }

  async function cancelPlan(metricId: number, planId: number) {
    const res = await api.deletePlan(metricId, planId)
    await refreshAfterWrite()
    return res.data
  }

  /** 首次进页面：阶段 + 两把尺子。 */
  async function bootstrap() {
    await loadStage()
    // 🔴 无条件拉 —— 「当期是哪一期」**与有没有阶段无关**。
    //    少了这一步，没有阶段时 `weekly.key` / `monthly.key` 都是空，
    //    「本周状态」与「本月状态」两页就一字不差（分不出自己在哪一页）。
    await loadBothPeriods()
  }

  /** 任何一次写操作之后调用 —— **写完回读**，不靠前端自己推算（口径只有后端一份）。 */
  async function refreshAfterWrite() {
    await loadStage(true)
    await loadBothPeriods()
  }

  async function checkin(metricId: number, value: number, checkinDate?: string, note?: string) {
    const res = await api.createCheckin({
      metric: metricId, value, checkin_date: checkinDate, note,
    })
    await refreshAfterWrite()
    return res.data
  }

  async function reverseCheckin(id: number) {
    const res = await api.reverseCheckin(id)
    await refreshAfterWrite()
    return res.data
  }

  async function updateMetric(id: number, data: Record<string, unknown>) {
    const res = await api.patchMetric(id, data)
    await refreshAfterWrite()
    return res.data
  }

  async function retireMetric(id: number, reason = '') {
    await api.retireMetric(id, reason)
    await refreshAfterWrite()
  }

  async function reviveMetric(id: number, reason = '') {
    await api.reviveMetric(id, reason)
    await refreshAfterWrite()
  }

  async function pause(payload: { reason?: string; resume_at?: string; note?: string }) {
    if (!stage.value) return
    await api.pauseStage(stage.value.id, payload)
    await refreshAfterWrite()
  }

  async function resume() {
    if (!stage.value) return
    await api.resumeStage(stage.value.id)
    await refreshAfterWrite()
  }

  async function heartbeat() {
    const res = await api.heartbeat(true)
    if (res.data.stage) heartbeatInfo.value = (await api.getCurrentPeriod('weekly')).data.heartbeat ?? null
    return res.data
  }

  async function closePeriod(payload: {
    period_type: PeriodType; period_key: string
    skipped_metric_ids?: number[]; answer_sheet?: Record<string, unknown>
  }) {
    const res = await api.closePeriod(payload)
    await refreshAfterWrite()
    await loadPeriods({ limit: 50 })
    return res.data
  }

  async function saveReview(periodId: number, payload: {
    review_text?: string; answer_sheet?: Record<string, unknown>
  }) {
    const res = await api.patchPeriod(periodId, payload)
    await loadPeriods({ limit: 50 })
    return res.data
  }

  async function reopenPeriod(periodId: number, reason: string) {
    const res = await api.reopenPeriod(periodId, reason)
    await refreshAfterWrite()
    await loadPeriods({ limit: 50 })
    return res.data
  }

  return {
    // state
    loading, stage, metrics, logs, heartbeatInfo, colors,
    weekly, monthly, periods,
    templates, templateEnum, periodOptions,
    // getters
    hasStage, weeklyMetrics, monthlyMetrics,
    // actions
    loadStage, loadPeriod, loadBothPeriods, loadPeriods, bootstrap, refreshAfterWrite,
    checkin, reverseCheckin, updateMetric, retireMetric, reviveMetric,
    pause, resume, heartbeat, closePeriod, saveReview, reopenPeriod,
    loadTemplates, createTemplate, updateTemplate, deleteTemplate,
    loadPeriodOptions, setPlan, cancelPlan,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后页面上跑的还是旧定义（模板新、数据旧，看起来像「功能没做」）。
if (import.meta.hot) {
  acceptHMRUpdate(useSelfRunStore, import.meta.hot)
}
