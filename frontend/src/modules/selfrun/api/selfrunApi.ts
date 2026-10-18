/** 自我运转 · 接口层
 *
 * 🔴 三条约定（与后端 `views.py` 对齐）：
 *
 * 1. **列表端点返回裸数组**（后端 `pagination_class = None`）——
 *    别写成 `res.data.results`，那会得到 `undefined` 而**不报错**，
 *    页面表现是「一条都没有」，看着像「功能没做」。
 * 2. **`GET` 不写库** —— 「当前周期」在还没有数据时返回 `period.id === null`
 *    的**虚拟对象**，可以放心刷新。
 * 3. **每个写操作都回 `written`**（本次写了哪几张表）—— 界面上可以显示，
 *    出问题时一眼看出哪步没写。
 */
import request from '@/shared/utils/request'
import type {
  CurrentPeriodResponse, KpiTemplate, OverviewResponse, PeriodOption, PeriodType,
  PlanScope, PreviewResult, SelfRunCheckin, SelfRunMetric, SelfRunMetricLog,
  SelfRunMetricPlan, SelfRunPeriod, SelfRunStage, StageSummary, TargetsResponse,
  TemplateEnum, Written,
} from '../types/selfrunTypes'

// ══════════════════════════════════════════════════════════════
// T1 · 制定配置
// ══════════════════════════════════════════════════════════════

/** 模板库（**可自定义增删改**）。
 *
 * 🔴 「模板是**拷贝**不是引用」—— 这里改了/删了都**不影响已建阶段**。
 * ⚠️ 返回的是 `{templates, enum}` 而**不是裸数组**（枚举与列表同源下发）。
 */
export function getTemplates(params?: { period_type?: PeriodType }) {
  return request<{ templates: KpiTemplate[]; enum: TemplateEnum }>({
    url: '/selfrun/templates/', method: 'get', params,
  })
}

/** 新建一条自定义模板。🔴 `key` **由后端生成**（`custom_<8位>`），前端不许编。 */
export function createTemplate(data: Record<string, unknown>) {
  return request<{ template: KpiTemplate; written: Written }>({
    url: '/selfrun/templates/', method: 'post', data,
  })
}

/** 改模板。⚠️ `key` 不可改（它是 `SelfRunMetric.template_key` 的指向）。 */
export function updateTemplate(id: number, data: Record<string, unknown>) {
  return request<{ template: KpiTemplate; changed: string[]; written: Written }>({
    url: `/selfrun/templates/${id}/`, method: 'patch', data,
  })
}

/** 删模板。返回「曾被几条 KPI 引用过」—— 那些 KPI **不受影响**，只是来源失去指向。 */
export function deleteTemplate(id: number) {
  return request<{
    deleted: { id: number; key: string; name: string }
    used_by_metrics: number
    note: string
    written: Written
  }>({ url: `/selfrun/templates/${id}/`, method: 'delete' })
}

/** **纯试算，绝不落库**（可以放心点一百次）。 */
export function previewMetric(data: Record<string, unknown>) {
  return request<PreviewResult & { written: Written }>({
    url: '/selfrun/metrics/preview/', method: 'post', data,
  })
}

/** 生效新阶段 —— **一个事务写 3 张表**（stage + metric×N + metric_log×N）。 */
export function createStage(data: Record<string, unknown>) {
  return request<{ stage: SelfRunStage; metrics: SelfRunMetric[]; written: Written }>({
    url: '/selfrun/stages/', method: 'post', data,
  })
}

/** 用某个阶段的配置开新阶段（**不复制历史**；指纹必然不同）。 */
export function copyStage(data: { from_stage_id: number; name: string; start_date?: string }) {
  return request<{
    stage: SelfRunStage; metrics: SelfRunMetric[]
    copied_from: { id: number; name: string }; note: string; written: Written
  }>({ url: '/selfrun/stages/copy/', method: 'post', data })
}

export function listStages(params?: { status?: string }) {
  return request<SelfRunStage[]>({ url: '/selfrun/stages/', method: 'get', params })
}

export function getStage(id: number) {
  return request<{
    stage: SelfRunStage; metrics: SelfRunMetric[]; periods: SelfRunPeriod[]
    logs: SelfRunMetricLog[]; summary: StageSummary; written: Written
  }>({ url: `/selfrun/stages/${id}/`, method: 'get' })
}

/** ⚠️ 只能改 `note` / `end_date` —— 送 `start_date` 后端回 **400**（不静默忽略）。 */
export function patchStage(id: number, data: { note?: string; end_date?: string | null }) {
  return request<{ stage: SelfRunStage; written: Written }>({
    url: `/selfrun/stages/${id}/`, method: 'patch', data,
  })
}

// ══════════════════════════════════════════════════════════════
// T1b · 按期修订（「每周 / 每月修订下一周、月的 KPI」）
// ══════════════════════════════════════════════════════════════

/** 「哪几期可以修订」= 上一期 + 本期 + 往后 N 期。
 *
 * 🔴 周期标识**只由后端算**：前端拿 `Date` 自己算 ISO 周，在跨年边界
 *    （12-29 属于下一年 W01）会**静默差一周**，而且不报错。
 */
export function getPeriodOptions(periodType: PeriodType, count = 6) {
  return request<{ period_type: PeriodType; options: PeriodOption[]; written: Written }>({
    url: '/selfrun/period-options/', method: 'get',
    params: { period_type: periodType, count },
  })
}

/** 某一期的**生效目标**清单（修订界面用）。
 *
 * ⚠️ 这里**不跑取数器** —— 修订目标不需要把 7 个 reader 全跑一遍；
 *    与「本周状态」共用 `services.resolve_targets` 同一份口径。
 * ⚠️ `period_key` 不传 ⇒ 后端按「本期」给你。
 */
export function getTargets(periodType: PeriodType, periodKey?: string) {
  return request<TargetsResponse>({
    url: '/selfrun/targets/', method: 'get',
    params: { period_type: periodType, period_key: periodKey },
  })
}

/** 某一条 KPI 改过哪几期（**裸数组**）。 */
export function listPlans(metricId: number) {
  return request<SelfRunMetricPlan[]>({
    url: `/selfrun/metrics/${metricId}/plans/`, method: 'get',
  })
}

/** 设定某一条 KPI 在**某一期**的目标。
 *
 * 🔴 `goal_value` / `floor_value` **必须显式传**（可为 `null`）——
 *    「省略」与「显式传 null」是两件事：省略会让「我没动这条底线」变成
 *    「把底线删了」，而且**不报错**。
 * 🔴 落在**已归档**的期 ⇒ 后端回 **409**。
 */
export function setPlan(metricId: number, data: {
  period_key: string
  scope: PlanScope
  goal_value: number | null
  floor_value: number | null
  goal_why?: string
  floor_why?: string
  note?: string
}) {
  return request<{ plan: SelfRunMetricPlan; log: SelfRunMetricLog; written: Written }>({
    url: `/selfrun/metrics/${metricId}/plans/`, method: 'post', data,
  })
}

/** 取消某一期的设定（回到上一层口径）。
 *
 * ⚠️ 这里**真的是删除** —— 配置不是流水（流水才适用「撤销 ≠ 删除」），
 *    留痕由变更记录承担。同样受归档闸门约束。
 */
export function deletePlan(metricId: number, planId: number) {
  return request<{ deleted: number; log: SelfRunMetricLog; written: Written }>({
    url: `/selfrun/metrics/${metricId}/plans/${planId}/`, method: 'delete',
  })
}

// ══════════════════════════════════════════════════════════════
// T2 · 执行
// ══════════════════════════════════════════════════════════════

/** 本周 / 本月状态。🔴 当期没有数据行时返回**虚拟对象**（`period.id === null`）。 */
export function getCurrentPeriod(periodType: PeriodType) {
  return request<CurrentPeriodResponse>({
    url: '/selfrun/periods/current/', method: 'get', params: { period_type: periodType },
  })
}

export function listCheckins(params?: { metric_id?: number }) {
  return request<SelfRunCheckin[]>({ url: '/selfrun/checkins/', method: 'get', params })
}

/** 手工登记（每次都是一笔新流水，不幂等）。⚠️ `source_kind='auto'` 的条目后端会拒。 */
export function createCheckin(data: {
  metric: number; value: number; checkin_date?: string; note?: string
}) {
  return request<{ checkin: SelfRunCheckin; written: Written }>({
    url: '/selfrun/checkins/', method: 'post', data,
  })
}

/** 🔴 `DELETE` **实为冲销** —— 补一条负值，**原记录保留**（撤销 ≠ 删除）。 */
export function reverseCheckin(id: number) {
  return request<{
    reversal: SelfRunCheckin; original: SelfRunCheckin; note: string; written: Written
  }>({ url: `/selfrun/checkins/${id}/`, method: 'delete' })
}

/** 改 KPI 配置 —— **不新建行** + 每次留痕。`reason` 是必问的。 */
export function patchMetric(id: number, data: Record<string, unknown>) {
  return request<{ metric: SelfRunMetric; logs: SelfRunMetricLog[]; written: Written }>({
    url: `/selfrun/metrics/${id}/`, method: 'patch', data,
  })
}

export function retireMetric(id: number, reason = '') {
  return request<{ metric: SelfRunMetric; written: Written }>({
    url: `/selfrun/metrics/${id}/retire/`, method: 'post', data: { reason },
  })
}

export function reviveMetric(id: number, reason = '') {
  return request<{ metric: SelfRunMetric; written: Written }>({
    url: `/selfrun/metrics/${id}/revive/`, method: 'post', data: { reason },
  })
}

/** 整个阶段暂停（休耕）—— 周期照常流转，归档时判 `fallow`。 */
export function pauseStage(id: number, data: { reason?: string; resume_at?: string; note?: string }) {
  return request<{ stage: SelfRunStage; written: Written }>({
    url: `/selfrun/stages/${id}/pause/`, method: 'post', data,
  })
}

export function resumeStage(id: number) {
  return request<{ stage: SelfRunStage; written: Written }>({
    url: `/selfrun/stages/${id}/resume/`, method: 'post',
  })
}

/** 「回访即握手」—— **不判好坏、不改任何 KPI**。同一天最多写一次。 */
export function heartbeat(seen = true) {
  return request<{ stage: SelfRunStage | null; written: Written }>({
    url: '/selfrun/heartbeat/', method: 'post', data: { seen },
  })
}

// ══════════════════════════════════════════════════════════════
// T3 · 复盘
// ══════════════════════════════════════════════════════════════

export function listPeriods(params?: { period_type?: PeriodType; stage_id?: number; limit?: number }) {
  return request<SelfRunPeriod[]>({ url: '/selfrun/periods/', method: 'get', params })
}

/** 归档 = 定格。⚠️ 系统**不自动归档** —— 归不归档是你的动作。 */
export function closePeriod(data: {
  period_type: PeriodType; period_key: string
  skipped_metric_ids?: number[]; answer_sheet?: Record<string, unknown>
}) {
  return request<{
    period: SelfRunPeriod; backfill_days: number; note: string; written: Written
  }>({ url: '/selfrun/periods/close/', method: 'post', data })
}

export function getPeriod(id: number) {
  return request<{ period: SelfRunPeriod; written: Written }>({
    url: `/selfrun/periods/${id}/`, method: 'get',
  })
}

/** 归档后**仍可写**的只有 `review_text` / `answer_sheet`（记忆型 ≠ 数据型）。 */
export function patchPeriod(id: number, data: {
  review_text?: string; answer_sheet?: Record<string, unknown>
}) {
  return request<{ period: SelfRunPeriod; written: Written }>({
    url: `/selfrun/periods/${id}/`, method: 'patch', data,
  })
}

/** 重开（改历史判定的**唯一出口**，且留痕 + 必须写原因）。 */
export function reopenPeriod(id: number, reason: string) {
  return request<{ period: SelfRunPeriod; written: Written }>({
    url: `/selfrun/periods/${id}/reopen/`, method: 'post', data: { reason },
  })
}

// ══════════════════════════════════════════════════════════════
// T4 · 事后分析
// ══════════════════════════════════════════════════════════════

/** `GET` 看数字（**实时算**）；`summary_snapshot` 是「你写那段话时看到的数」。 */
export function getStageSummary(id: number) {
  return request<{
    stage: SelfRunStage; summary: StageSummary
    summary_snapshot: StageSummary | null; summary_at: string | null; written: Written
  }>({ url: `/selfrun/stages/${id}/summary/`, method: 'get' })
}

/** 写阶段总结 —— **T4 唯一落库的分析**（同时冻结当时的数字）。 */
export function saveStageSummary(id: number, text: string) {
  return request<{ stage: SelfRunStage; summary_snapshot: StageSummary; written: Written }>({
    url: `/selfrun/stages/${id}/summary/`, method: 'post', data: { text },
  })
}

/** 收尾阶段（写 `end_date` + `status='closed'`）。必须**先写总结**。 */
export function closeStage(id: number, data?: { text?: string; end_date?: string | null }) {
  return request<{ stage: SelfRunStage; written: Written }>({
    url: `/selfrun/stages/${id}/close/`, method: 'post', data: data ?? {},
  })
}

// ══════════════════════════════════════════════════════════════
// 跨模块（仪表盘小卡）
// ══════════════════════════════════════════════════════════════

export function getSelfRunOverview() {
  return request<OverviewResponse>({ url: '/selfrun/overview/', method: 'get' })
}
