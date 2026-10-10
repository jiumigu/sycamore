import request from '@/shared/utils/request'
import type { CalendarQueryParams, CoverageInput, BudgetInput, BillCreateData, CurrentAgeWeek } from '../types/wealthTypes'
import type { LiabilityFormData, ReceivableFormData } from '../types/wealthTypes'
import type {
  AssetAccountFormData, AssetSnapshotFormData,
} from '../types/wealthTypes'
import type { ClassifyRuleFormData } from '../types/wealthTypes'

export function getCalendar(params?: CalendarQueryParams) {
  return request({ url: '/wealth/calendar/', method: 'get', params })
}

export function getWeeklySummary(weekIndex: number) {
  return request({ url: `/wealth/weekly_summary/${weekIndex}/`, method: 'get' })
}

export function getCurrentScenario() {
  return request({ url: '/wealth/scenario/current/', method: 'get' })
}

export function updateCurrentScenario(data: Record<string, unknown>) {
  return request({ url: '/wealth/scenario/current/', method: 'put', data })
}

export function calculateCoverage(data: CoverageInput) {
  return request({ url: '/wealth/calculate_coverage/', method: 'post', data })
}

/** 反算：本金 + 目标天数 → 每日可提取额（纯试算，后端不写任何表） */
export function calculateBudget(data: BudgetInput) {
  return request({ url: '/wealth/calculate_budget/', method: 'post', data })
}

export function getLifeSummary(params?: { user_id?: number }) {
  return request({ url: '/wealth/summary/', method: 'get', params })
}

export function getBillsByWeek(params: { week_index: number; user_id?: number }) {
  return request({ url: '/wealth/bills/by_week/', method: 'get', params })
}

export function initCalendar(data: { user_id?: number; birth_date?: string }) {
  return request({ url: '/wealth/calendar/init/', method: 'post', data })
}

/** 月度日历 */
export function getMonthlyCalendar(params: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/monthly_calendar/', method: 'get', params })
}

/** 单日明细 */
export function getDailyDetail(params: { date: string; user_id?: number }) {
  return request({ url: '/wealth/daily_detail/', method: 'get', params })
}

/** 月度汇总 */
export function getMonthlySummary(params: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/monthly_summary/', method: 'get', params })
}

/** 快速记账 */
export function createBill(data: BillCreateData) {
  return request({ url: '/wealth/bill/create/', method: 'post', data })
}

// ══════════════════════════════════════════
// 月度复盘 API
// ══════════════════════════════════════════

/** 月度复盘汇总 */
export function getMonthlyReview(params: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/review/monthly_summary/', method: 'get', params })
}

/** 收支趋势 */
export function getTrendData(params: { months?: number; user_id?: number }) {
  return request({ url: '/wealth/review/trend/', method: 'get', params })
}

/** 分类排行 */
export function getCategoryRanking(params: { year: number; month: number; type?: string; user_id?: number }) {
  return request({ url: '/wealth/review/category_ranking/', method: 'get', params })
}

/** 历史复盘列表 */
export function getMonthlyList(params: { page?: number; page_size?: number; user_id?: number }) {
  return request({ url: '/wealth/review/monthly_list/', method: 'get', params })
}

/** 创建复盘数据 */
export function createBalanceList(data: Record<string, unknown>) {
  return request({ url: '/wealth/review/balance_list/', method: 'post', data })
}

/** 更新复盘数据 */
export function updateBalanceList(data: Record<string, unknown>) {
  return request({ url: '/wealth/review/balance_list/', method: 'put', data })
}

/** 同比环比分析 */
export function getCompareData(params: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/review/compare/', method: 'get', params })
}

/** 生成复盘数据 */
export function generateBalanceInfo(data: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/review/generate/', method: 'post', data })
}

// ══════════════════════════════════════════
// 资产盘点 API（资产负债表口径）
// ══════════════════════════════════════════

/** 资产全景 */
export function getCashFlowOverview(params?: { yearmon?: string }) {
  return request({ url: '/wealth/cashflow/overview/', method: 'get', params })
}

/** 资产趋势 */
export function getAssetTrend(params?: { months?: number; user_id?: number }) {
  return request({ url: '/wealth/cashflow/trend/', method: 'get', params })
}

/** 盘点快照 CRUD */
export function saveSnapshot(data: Record<string, unknown>) {
  return request({ url: '/wealth/cashflow/snapshot/', method: 'post', data })
}

export function updateSnapshot(data: Record<string, unknown>) {
  return request({ url: '/wealth/cashflow/snapshot/', method: 'put', data })
}

export function deleteSnapshot(params: { baid: number }) {
  return request({ url: '/wealth/cashflow/snapshot/', method: 'delete', data: params })
}

/** 盘点历史列表 */
export function getSnapshotList(params?: { page?: number; page_size?: number }) {
  return request({ url: '/wealth/cashflow/snapshot/list/', method: 'get', params })
}

/** 复制上月数据 */
export function copyLastSnapshot(data: { yearmon: string }) {
  return request({ url: '/wealth/cashflow/copy/', method: 'post', data })
}

// ══════════════════════════════════════════
// 定期存款 API
// ══════════════════════════════════════════

/** 定期存款统计 */
export function getRegularStats() {
  return request({ url: '/wealth/regular/stats/', method: 'get' })
}

/** 到期提醒列表 */
export function getRegularExpiring(params?: { days?: number }) {
  return request({ url: '/wealth/regular/expiring/', method: 'get', params })
}

/** 定期存款列表 */
export function getRegularList(params?: { bankinfo?: string; flag?: number; keyword?: string }) {
  return request({ url: '/wealth/regular/list/', method: 'get', params })
}

/** 银行列表 */
export function getRegularBanks() {
  return request({ url: '/wealth/regular/banks/', method: 'get' })
}

/** 新增定期存款 */
export function createRegular(data: Record<string, unknown>) {
  return request({ url: '/wealth/regular/0/', method: 'post', data })
}

/** 获取单条存款详情 */
export function getRegularDetail(id: number) {
  return request({ url: `/wealth/regular/${id}/`, method: 'get' })
}

/** 更新定期存款 */
export function updateRegular(id: number, data: Record<string, unknown>) {
  return request({ url: `/wealth/regular/${id}/`, method: 'put', data })
}

/** 删除定期存款 */
export function deleteRegular(id: number) {
  return request({ url: `/wealth/regular/${id}/`, method: 'delete' })
}

/** 到期处理 */
export function processMature(id: number, data: Record<string, unknown>) {
  return request({ url: `/wealth/regular/${id}/mature/`, method: 'post', data })
}

/** 批量更新到期状态 */
export function updateRegularStatus() {
  return request({ url: '/wealth/regular/update_status/', method: 'post' })
}

/** 获取当前年龄周数（后端读周历表 —— 「现在」的唯一真源，不按出生日期现算） */
export function getCurrentAgeWeek() {
  return request<CurrentAgeWeek>({ url: '/wealth/age-week/', method: 'get' })
}

/** 导入随手记 CSV 账单 */
export function importCSV(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request({
    url: '/wealth/import/csv/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getBills(params?: Record<string, unknown>) {
  return request({ url: '/wealth/bills/', method: 'get', params })
}

export function createBillRecord(data: Record<string, unknown>) {
  return request({ url: '/wealth/bills/', method: 'post', data })
}

export function updateBill(id: number, data: Record<string, unknown>) {
  return request({ url: `/wealth/bills/${id}/`, method: 'patch', data })
}

export function deleteBill(id: number) {
  return request({ url: `/wealth/bills/${id}/`, method: 'delete' })
}

/** 批量标记必要性（仅支出行生效） */
export function batchSetNecessity(ids: number[], necessity: string) {
  return request({ url: '/wealth/bills/batch-necessity/', method: 'post', data: { ids, necessity } })
}

/** 支出必要性小结（必要/可选/冲动/未标记 笔数与金额） */
export function getNecessityStats(params?: Record<string, unknown>) {
  return request({ url: '/wealth/bills/necessity_stats/', method: 'get', params })
}

/** 批量标记赎回归属（收入/支出均生效） */
export function batchSetPeriodTag(ids: number[], periodTag: string) {
  return request({ url: '/wealth/bills/batch-period-tag/', method: 'post', data: { ids, period_tag: periodTag } })
}

/** 赎回归属小结（为自己/过渡/为别人/不计入/未标记 笔数与金额，收入支出合计） */
export function getPeriodTagStats(params?: Record<string, unknown>) {
  return request({ url: '/wealth/bills/period_tag_stats/', method: 'get', params })
}

export function getBillContrib() {
  return request({ url: '/wealth/bills/contrib/', method: 'get' })
}

export function getBillDailyDetail(params: { date: string }) {
  return request<{ date: string; total?: number; items: any[] }>({ url: '/wealth/bills/daily_detail/', method: 'get', params })
}

// ══════════════════════════════════════════
// 负债明细 / 应收账龄 API（P1-A，v3.58.20）
//
// 列表端点是**裸数组**（后端 pagination_class = None）；
// summary 恒为全量口径，筛选参数只作用于列表。
// ══════════════════════════════════════════

/** 负债逐笔台账 */
export function getLiabilityList(params?: { status?: string; category?: string }) {
  return request({ url: '/wealth/debt/liabilities/', method: 'get', params })
}

export function getLiabilitySummary() {
  return request({ url: '/wealth/debt/liabilities/summary/', method: 'get' })
}

export function createLiability(data: LiabilityFormData) {
  return request({ url: '/wealth/debt/liabilities/', method: 'post', data })
}

export function updateLiability(data: LiabilityFormData) {
  return request({ url: `/wealth/debt/liabilities/${data.id}/`, method: 'patch', data })
}

export function deleteLiability(id: number) {
  return request({ url: `/wealth/debt/liabilities/${id}/`, method: 'delete' })
}

/** 应收借出逐笔台账 */
export function getReceivableList(params?: { status?: string; aging_bucket?: string }) {
  return request({ url: '/wealth/debt/receivables/', method: 'get', params })
}

export function getReceivableSummary() {
  return request({ url: '/wealth/debt/receivables/summary/', method: 'get' })
}

export function createReceivable(data: ReceivableFormData) {
  return request({ url: '/wealth/debt/receivables/', method: 'post', data })
}

export function updateReceivable(data: ReceivableFormData) {
  return request({ url: `/wealth/debt/receivables/${data.id}/`, method: 'patch', data })
}

export function deleteReceivable(id: number) {
  return request({ url: `/wealth/debt/receivables/${id}/`, method: 'delete' })
}

// ══════════════════════════════════════════
// 资产科目主数据 / 资产快照 API（P1-B，v3.58.21）
//
// 列表端点一律**裸数组**（后端 pagination_class = None）：
// 被全局分页包成 {count, results} 时，这里按数组消费会拿到 undefined 而静默显示为空。
// 快照用 limit（最近 N 期）而非分页 —— 月度数据上分页器只是噪声。
// ══════════════════════════════════════════

/** 资产科目主数据 */
export function getAssetAccounts(params?: { include_inactive?: number }) {
  return request({ url: '/wealth/asset/accounts/', method: 'get', params })
}

export function getAssetAccountSummary() {
  return request({ url: '/wealth/asset/accounts/summary/', method: 'get' })
}

export function createAssetAccount(data: AssetAccountFormData) {
  return request({ url: '/wealth/asset/accounts/', method: 'post', data })
}

export function updateAssetAccount(data: AssetAccountFormData) {
  return request({ url: `/wealth/asset/accounts/${data.id}/`, method: 'patch', data })
}

export function deleteAssetAccount(id: number) {
  return request({ url: `/wealth/asset/accounts/${id}/`, method: 'delete' })
}

/** 从旧表列定义生成种子科目（幂等；overwrite=false 时不覆盖已改过的科目） */
export function seedAssetAccounts(overwrite = false) {
  return request({
    url: '/wealth/asset/accounts/seed/', method: 'post', data: { overwrite },
  })
}

/** 资产快照（按 yearmon 幂等） */
export function getAssetSnapshots(params?: { limit?: number; year?: string }) {
  return request({ url: '/wealth/asset/snapshots/', method: 'get', params })
}

export function getAssetSnapshot(id: number) {
  return request({ url: `/wealth/asset/snapshots/${id}/`, method: 'get' })
}

export function getAssetSnapshotByYearmon(yearmon: string) {
  return request({ url: '/wealth/asset/snapshots/by_yearmon/', method: 'get', params: { yearmon } })
}

export function createAssetSnapshot(data: AssetSnapshotFormData) {
  return request({ url: '/wealth/asset/snapshots/', method: 'post', data })
}

/** 更新一期快照（**不允许改年月**，改年月请删除重建） */
export function updateAssetSnapshot(id: number, data: AssetSnapshotFormData) {
  return request({ url: `/wealth/asset/snapshots/${id}/`, method: 'put', data })
}

export function deleteAssetSnapshot(id: number) {
  return request({ url: `/wealth/asset/snapshots/${id}/`, method: 'delete' })
}

/* ── 账单项分类规则 / 归类结果（P1-C）──────────────────────────
 * 规则是主数据（可增删改），结果是派生数据（只读、实时算）。
 * 两者前缀不同（/classify/rules vs /classify/results）正是为了在调用处
 * 一眼看出「这次是在改规则，还是在看结果」。
 * ──────────────────────────────────────────────────────────── */

/** 规则台账（裸数组；include_inactive 时含停用规则） */
export function getClassifyRules(params?: { include_inactive?: number }) {
  return request({ url: '/wealth/classify/rules/', method: 'get', params })
}

export function createClassifyRule(data: ClassifyRuleFormData) {
  return request({ url: '/wealth/classify/rules/', method: 'post', data })
}

export function updateClassifyRule(id: number, data: ClassifyRuleFormData) {
  return request({ url: `/wealth/classify/rules/${id}/`, method: 'patch', data })
}

export function deleteClassifyRule(id: number) {
  return request({ url: `/wealth/classify/rules/${id}/`, method: 'delete' })
}

export function getClassifyRuleSummary() {
  return request({ url: '/wealth/classify/rules/summary/', method: 'get' })
}

/** 按真实分类归纳的种子规则初始化（幂等；overwrite 才会覆盖已改过的规则） */
export function seedClassifyRules(overwrite = false) {
  return request({
    url: '/wealth/classify/rules/seed/', method: 'post', data: { overwrite },
  })
}

/** 候选规则影响预览（**不写库**）—— 命中多少、真正会改动多少 */
export function previewClassifyRule(data: ClassifyRuleFormData & { yearmon?: string }) {
  return request({ url: '/wealth/classify/rules/preview/', method: 'post', data })
}

/** 有账单数据的年月列表（倒序裸数组） */
export function getClassifyPeriods() {
  return request({ url: '/wealth/classify/rules/periods/', method: 'get' })
}

/** 归类汇总（某期或不传 = 全周期）：三个维度 + 覆盖率 + 排除项 */
export function getClassifySummary(params?: { yearmon?: string }) {
  return request({ url: '/wealth/classify/results/', method: 'get', params })
}

/** 未归类候选 —— 回答「下一条规则建在哪儿」 */
export function getClassifyUnclassified(params?: { yearmon?: string; limit?: number }) {
  return request({ url: '/wealth/classify/results/unclassified/', method: 'get', params })
}

/* ── 财务规划比率（P2-A）────────────────────────────────────────
 * 比率是**派生结果**：只读、实时算、无主键。故这里只有 get，
 * 没有任何 create/update —— 想改结果就去改上游（资产快照 / 分类规则 / 负债明细）。
 *
 * 判定区间与级别全部由后端下发，前端不做除法、不持有阈值。
 * ──────────────────────────────────────────────────────────── */

/** 六项比率总览（不传 yearmon = 最新一期） */
export function getRatioOverview(params?: { yearmon?: string }) {
  return request({ url: '/wealth/ratios/', method: 'get', params })
}

/** 逐月比率序列（值已在后端算好） */
export function getRatioTrend(params?: { months?: number }) {
  return request({ url: '/wealth/ratios/trend/', method: 'get', params })
}

/** 可作为锚定月的年月（倒序裸数组）—— 来自资产快照期别 */
export function getRatioAnchors() {
  return request({ url: '/wealth/ratios/anchors/', method: 'get' })
}

/** 单期资产位置（carry_forward 默认开：本月未盘点时取上一期并标 carried） */
export function getRatioAssetPosition(params?: { yearmon?: string; carry_forward?: number }) {
  return request({ url: '/wealth/ratios/asset_position/', method: 'get', params })
}

/**
 * 九项比率的**口径元信息**（公式 + 判定区间 + 口径说明，裸数组）。
 *
 * 这是界面上「气泡提示」的唯一文案源 —— 前端一行口径都不许自己写。
 * 后端 `constants.RATIO_BANDS` 改了公式，气泡跟着变，零前端改动。
 */
export function getRatioMeta() {
  return request({ url: '/wealth/ratios/meta/', method: 'get' })
}
