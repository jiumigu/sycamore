import request from '@/shared/utils/request'
import type {
  CompletenessData, DailyGuardData, FrequentNamesData, ImportPreview, MetaLedgerData,
  OverlapCheckData, SourceOverview, SunburstData, TaskRenameResult, WeeklyStructure,
} from '../types/temporalTypes'

// ─── 每日记录 (OneDay) ───

export function getOneDayList(params?: Record<string, unknown>) {
  return request({ url: '/temporal/oneday/', method: 'get', params })
}

export function getOneDayDetail(id: number) {
  return request({ url: `/temporal/oneday/${id}/`, method: 'get' })
}

export function createOneDay(data: Record<string, unknown>) {
  return request({ url: '/temporal/oneday/', method: 'post', data })
}

export function updateOneDay(id: number, data: Record<string, unknown>) {
  return request({ url: `/temporal/oneday/${id}/`, method: 'put', data })
}

export function deleteOneDay(id: number) {
  return request({ url: `/temporal/oneday/${id}/`, method: 'delete' })
}

export function getOneDayStats() {
  return request({ url: '/temporal/oneday/stats/', method: 'get' })
}

export function getWeekCount() {
  return request<{ count: number }>({ url: '/temporal/oneday/week_count/', method: 'get' })
}

export function getWeekStats() {
  return request<{ count: number; step_count: number; weekly_expense: number }>({
    url: '/temporal/oneday/week_stats/',
    method: 'get',
  })
}

export function bulkDeleteOneDay(ids: number[]) {
  return request({ url: '/temporal/oneday/bulk_delete/', method: 'delete', data: { oids: ids } })
}

export function getYearlyHeatmap(year: number) {
  return request({ url: `/temporal/oneday/yearly_heatmap/?year=${year}`, method: 'get' })
}

export function openLogseq(path: string) {
  return request({ url: '/temporal/open-logseq/', method: 'get', params: { path } })
}

// ─── 任务时间追踪 (Tasks) ───

export function getTaskList(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/', method: 'get', params })
}

/**
 * 记录来源总览：全库按批次 + 按来源类型汇总（v3.64.33）。
 *
 * 🔴 必须走接口取，**不要**从前端列表自己数 —— 任务列表是分页的，
 *    数出来的只是当前页，「41 条未标注」会变成「这页有 3 条」。
 * 分类口径（哪些批次算 CSV 导入 / 未标注 / 其它来源）全在后端
 * `services.classify_source`，前端只显示下发的 `label`。
 */
export function getTaskSources() {
  return request<SourceOverview>({ url: '/temporal/tasks/sources/', method: 'get' })
}

export function getTaskDetail(id: number) {
  return request({ url: `/temporal/tasks/${id}/`, method: 'get' })
}

export function getTaskNames() {
  return request({ url: '/temporal/tasks/task_names/', method: 'get' })
}

/**
 * 最近 N 个月最频繁的任务名（手工新增弹窗的快捷候选）。
 *
 * 排序口径（按次数 → 时长 → 最近使用）与窗口（自然月）都在后端，
 * 前端只传参数、只读结果 —— 别在这儿再算一遍「最近 3 个月」。
 */
export function getFrequentTaskNames(params: { months?: number; limit?: number } = {}) {
  return request<FrequentNamesData>({
    url: '/temporal/tasks/frequent_names/',
    method: 'get',
    params,
  })
}

export function importTaskCsv(data: FormData) {
  return request({ url: '/temporal/tasks/import_csv/', method: 'post', data, headers: { 'Content-Type': undefined } })
}

/**
 * CSV 导入**预演**（只读）：先看这份文件会撞上什么，再决定要不要落。
 *
 * 与 `importTaskCsv` 收同一个 `file`，但**不写库**（不建 TaskMeta、不刷周缓存）。
 * 返回按 `contained/edge/review/likely_dup` 分好类的清单，口径在
 * `services.classify_overlap`。
 */
export function previewImportCsv(data: FormData) {
  return request<ImportPreview>({
    url: '/temporal/tasks/preview_import/',
    method: 'post',
    data,
    headers: { 'Content-Type': undefined },
  })
}

/**
 * 查「这段时间有没有别的记录」—— 新增/编辑保存**之前**调，只读不写库。
 *
 * 🔴 后端只回答「撞了哪些」，不阻断保存：本库里重叠是合法形态
 *    （大段「牛马工作」内再细分「代码编程」）。是否继续由用户看着清单决定。
 */
export function checkTaskOverlap(params: {
  start_time: string
  end_time: string
  exclude_id?: number
  task_name?: string
}) {
  return request<OverlapCheckData>({
    url: '/temporal/tasks/check_overlap/',
    method: 'get',
    params,
  })
}

export function getTaskStats(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/stats/', method: 'get', params })
}

export function getTaskTrend(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/trend/', method: 'get', params })
}

export function getTaskBalance(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/balance/', method: 'get', params })
}

export function getTaskRanking(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/ranking/', method: 'get', params })
}

export function getTaskDistribution(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/distribution/', method: 'get', params })
}

export function getTaskCalendar(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/calendar/', method: 'get', params })
}

// ⚠️ 原「周度时间追踪」两个封装（`getWeeklyTracking` / `refreshWeeklyCache`，指向已废弃的
//    30h 达标表接口）已删 —— 唯一调用方 `WeeklyTrackingView.vue` 已一并移除。
//    替代品是 `getWeeklyStructure`（168h 周结构，实时聚合源表）。
//    后端 `/temporal/weekly-tracking/` 按 v0.3 设计稿**刻意保留**，别再把它接回前端。

export function createTask(data: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/', method: 'post', data })
}

export function updateTask(id: number, data: Record<string, unknown>) {
  return request({ url: `/temporal/tasks/${id}/`, method: 'patch', data })
}

export function deleteTask(id: number) {
  return request({ url: `/temporal/tasks/${id}/`, method: 'delete' })
}

export function getTaskContrib(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/contrib/', method: 'get', params })
}

export function getOnedayContrib() {
  return request({ url: '/temporal/oneday/contrib/', method: 'get' })
}

/**
 * 每日任务明细（点贡献图格子看当天）。
 *
 * ⚠️ `scope`：贡献图那侧**必须**传 `'contrib'` —— 后端据此排除不计入贡献图的睡眠类
 * 任务（名单在后端 `temporal/constants.py`，前端**不复制这份名单**）。
 * 不传 = 当天全部任务（通用口径），供将来别处复用。
 */
export function getTaskDailyDetail(params: { date: string; scope?: 'contrib' }) {
  return request<{ date: string; total?: number; items: any[] }>({ url: '/temporal/tasks/daily_detail/', method: 'get', params })
}

export function getOnedayDailyDetail(params: { date: string }) {
  return request<{ date: string; total?: number; items: any[] }>({ url: '/temporal/oneday/daily_detail/', method: 'get', params })
}

// ─── 三层分类（L1 归因 / L2 活动类型 / L3 task_name）───

export function getTaskMeta(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/meta/', method: 'get', params })
}

/** 分类台账：全量 task_name + 时长/次数/最近使用 + 有效归因及来源 */
export function getMetaLedger(params?: Record<string, unknown>) {
  return request<MetaLedgerData>({ url: '/temporal/tasks/meta_ledger/', method: 'get', params })
}

export function getUnclassified(params?: Record<string, unknown>) {
  return request<{ count: number; items: any[] }>({ url: '/temporal/tasks/unclassified/', method: 'get', params })
}

export function batchSetMeta(data: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/batch_set_meta/', method: 'post', data })
}

/**
 * 改名 / 合并：把一个任务名变成另一个。
 *
 * 🔴 新名已存在 = **合并**（记录并过去、源行删掉），由后端判定 ——
 *    前端不要自己拿台账行去猜「这个名字有没有人用过」：列表一旦被筛选过就会猜错，
 *    用户点确定前看到「改名」、做完却是「合并」。
 * `dry_run: 1` 只算不写，弹窗的影响预览走它。
 */
export function renameTaskName(data: { task_name: string; new_name: string; dry_run?: 0 | 1 }) {
  return request<TaskRenameResult>({
    url: '/temporal/tasks/rename_task_name/', method: 'post', data,
  })
}

/** 删一行台账 —— 后端只在名下 0 条记录时放行 */
export function deleteTaskName(data: { task_name: string }) {
  return request({ url: '/temporal/tasks/delete_task_name/', method: 'post', data })
}

/**
 * 今天的三条线（睡眠 / 午睡 / 流失）。
 *
 * 🔴 阈值与「达标」判定全在后端 `constants.DAILY_GUARD_LINES`；
 *    这里只负责把结果取回来，**不要在前端再算一遍**（会得到两个口径）。
 */
export function getDailyGuards(params: { date?: string } = {}) {
  return request<DailyGuardData>({ url: '/temporal/tasks/daily_guards/', method: 'get', params })
}

export function getSunburst(params?: Record<string, unknown>) {
  return request<SunburstData>({ url: '/temporal/tasks/sunburst/', method: 'get', params })
}

export function getCompleteness(params?: Record<string, unknown>) {
  return request<CompletenessData>({ url: '/temporal/tasks/completeness/', method: 'get', params })
}

export function getWeeklyStructure(params?: Record<string, unknown>) {
  return request<WeeklyStructure>({ url: '/temporal/weekly-structure/', method: 'get', params })
}
