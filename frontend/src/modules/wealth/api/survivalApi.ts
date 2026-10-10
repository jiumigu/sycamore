/**
 * 生存资源盘点（v3.59.0，P3-A 一期）接口封装
 *
 * ⚠️ 列表端点全是**裸数组**（后端显式 `pagination_class = None`）。
 *    如果哪天被 DRF 全局分页包成 `{count, results}`，前端按数组消费会**静默变空** ——
 *    看起来像「一条数据都没有」，实际是格式变了。store 里对每个数组都做了兜底。
 */

import request from '@/shared/utils/request'
import type {
  SurvivalAnalysis,
  SurvivalCategory,
  SurvivalCategoryFormData,
  SurvivalCombo,
  SurvivalComboFormData,
  SurvivalComboMember,
  SurvivalComboMemberDetail,
  SurvivalComboMemberFormData,
  SurvivalEssential,
  SurvivalEssentialFormData,
  SurvivalEssentialLevel,
  SurvivalEssentialReconcile,
  SurvivalEssentialScope,
  SurvivalEssentialSeedResult,
  SurvivalFlow,
  SurvivalFlowBatchFormData,
  SurvivalFlowFormData,
  SurvivalFlowSummary,
  SurvivalItem,
  SurvivalItemFormData,
  SurvivalLineDetail,
  SurvivalMeta,
  SurvivalRecipe,
  SurvivalRecipeComboLine,
  SurvivalRecipeComboLineFormData,
  SurvivalRecipeFormData,
  SurvivalSeedResult,
  SurvivalSnapshotCreateFormData,
  SurvivalStocktake,
  SurvivalStocktakeFormData,
  SurvivalUnit,
  SurvivalUnitFormData,
  SurvivalWorksheetRow,
} from '../types/survivalTypes'

// ── 综合分析 / 口径 ──

/** 首屏一次取全：各类别时长 + 短板 + 双腿对照 + 三年覆盖率 */
export function getSurvivalAnalysis(params?: { date?: string }) {
  return request({ url: '/wealth/survival/analysis/', method: 'get', params })
}

/** 枚举与口径的单一出口（前端不硬编码任何选项文案） */
export function getSurvivalMeta() {
  return request({ url: '/wealth/survival/meta/', method: 'get' })
}

/** 只要口径元信息的裸数组（气泡提示用，与 /wealth/ratios/meta/ 同结构） */
export function getSurvivalMetricMeta() {
  return request({ url: '/wealth/survival/metrics/meta/', method: 'get' })
}

// ── 类别 ──

export function getSurvivalCategories(params?: { include_units?: number }) {
  return request({ url: '/wealth/survival/categories/', method: 'get', params })
}

export function createSurvivalCategory(data: SurvivalCategoryFormData) {
  return request({ url: '/wealth/survival/categories/', method: 'post', data })
}

export function updateSurvivalCategory(id: number, data: Partial<SurvivalCategoryFormData>) {
  return request({ url: `/wealth/survival/categories/${id}/`, method: 'patch', data })
}

export function deleteSurvivalCategory(id: number) {
  return request({ url: `/wealth/survival/categories/${id}/`, method: 'delete' })
}

/** 初始化四个默认类别与常用单位（幂等；**不预设任何物品与库存**） */
export function seedSurvivalDefaults(data?: { overwrite?: boolean }) {
  return request({ url: '/wealth/survival/categories/seed/', method: 'post', data: data ?? {} })
}

// ── 消耗单位 ──

export function getSurvivalUnits(params?: { category_id?: number }) {
  return request({ url: '/wealth/survival/units/', method: 'get', params })
}

export function createSurvivalUnit(data: SurvivalUnitFormData) {
  return request({ url: '/wealth/survival/units/', method: 'post', data })
}

export function updateSurvivalUnit(id: number, data: Partial<SurvivalUnitFormData>) {
  return request({ url: `/wealth/survival/units/${id}/`, method: 'patch', data })
}

export function deleteSurvivalUnit(id: number) {
  return request({ url: `/wealth/survival/units/${id}/`, method: 'delete' })
}

// ── 物品 ──

export function getSurvivalItems(params?: {
  category_id?: number
  satiety?: string
  status?: string
}) {
  return request({ url: '/wealth/survival/items/', method: 'get', params })
}

export function createSurvivalItem(data: SurvivalItemFormData) {
  return request({ url: '/wealth/survival/items/', method: 'post', data })
}

export function updateSurvivalItem(id: number, data: Partial<SurvivalItemFormData>) {
  return request({ url: `/wealth/survival/items/${id}/`, method: 'patch', data })
}

export function deleteSurvivalItem(id: number) {
  return request({ url: `/wealth/survival/items/${id}/`, method: 'delete' })
}

/**
 * 保存前试算（v3.59.11）—— **不写库**，返回与明细表同形的行
 *
 * 🔴 刻意走后端而不是前端自己把 `数量 × 一份能用几次` 乘一遍：
 *    那份公式与 `survival_calc` 迟早会分叉，而**分叉是静默的** ——
 *    试算说 150 天、保存后明细表里写着 123.7 年，两边都像一个正常的数。
 *    这里拿到的 `expected` 与保存后看到的是同一行代码算出来的。
 * ⚠️ 校验也复用保存那一个表单序列化器：试算放行、一保存报 400 比没有试算更误导。
 */
export function previewSurvivalItem(data: SurvivalItemFormData) {
  return request({ url: '/wealth/survival/items/preview/', method: 'post', data })
}

// ── 配餐配方 ──

export function getSurvivalRecipes(params?: { category_id?: number; with_lines?: number }) {
  return request({ url: '/wealth/survival/recipes/', method: 'get', params })
}

export function createSurvivalRecipe(data: SurvivalRecipeFormData) {
  return request({ url: '/wealth/survival/recipes/', method: 'post', data })
}

export function updateSurvivalRecipe(id: number, data: Partial<SurvivalRecipeFormData>) {
  return request({ url: `/wealth/survival/recipes/${id}/`, method: 'patch', data })
}

export function deleteSurvivalRecipe(id: number) {
  return request({ url: `/wealth/survival/recipes/${id}/`, method: 'delete' })
}

// ── 组合（v3.59.13） ──

/** 组合列表 —— 后端返回**裸数组**（被全局分页包住会静默变空） */
export function getSurvivalCombos(params?: { category_id?: number }) {
  return request({ url: '/wealth/survival/combos/', method: 'get', params })
}

export function createSurvivalCombo(data: SurvivalComboFormData) {
  return request({ url: '/wealth/survival/combos/', method: 'post', data })
}

export function updateSurvivalCombo(id: number, data: Partial<SurvivalComboFormData>) {
  return request({ url: `/wealth/survival/combos/${id}/`, method: 'patch', data })
}

export function deleteSurvivalCombo(id: number) {
  return request({ url: `/wealth/survival/combos/${id}/`, method: 'delete' })
}

// ── 类型再导出：组件按需取用，避免各处重复 import 两个文件 ──

export type {
  SurvivalAnalysis, SurvivalCategory, SurvivalItem, SurvivalMeta,
  SurvivalRecipe, SurvivalSeedResult, SurvivalStocktake, SurvivalUnit,
  SurvivalWorksheetRow,
  SurvivalEssential, SurvivalEssentialFormData, SurvivalEssentialLevel,
  SurvivalEssentialReconcile, SurvivalEssentialScope, SurvivalEssentialSeedResult,
  SurvivalCombo, SurvivalComboFormData, SurvivalComboMember,
  SurvivalComboMemberFormData, SurvivalRecipeComboLine, SurvivalRecipeComboLineFormData,
  SurvivalLineDetail, SurvivalComboMemberDetail,
}

// ── 盘点快照（v3.59.0 二期） ──

/** 历史列表 —— 后端按日期**倒序**返回（表格最近的在上） */
export function getSurvivalSnapshots(params?: { limit?: number }) {
  return request({ url: '/wealth/survival/snapshots/', method: 'get', params })
}

/** 单份快照（含类别明细） */
export function getSurvivalSnapshot(id: number) {
  return request({ url: `/wealth/survival/snapshots/${id}/`, method: 'get' })
}

/** 盘点：把此刻算出来的结论落成一份 */
export function createSurvivalSnapshot(data: SurvivalSnapshotCreateFormData) {
  return request({ url: '/wealth/survival/snapshots/', method: 'post', data })
}

/** 删掉一期盘点（快照本身**不可修改**，只能删掉重盘） */
export function deleteSurvivalSnapshot(id: number) {
  return request({ url: `/wealth/survival/snapshots/${id}/`, method: 'delete' })
}

/** 趋势序列（按日期升序）+ 与上一期的对比 */
export function getSurvivalSnapshotTrend(params?: { limit?: number }) {
  return request({ url: '/wealth/survival/snapshots/trend/', method: 'get', params })
}

// ── 实盘盘点（v3.59.3） ──

/**
 * 盘点工作表：要盘哪些物品、系统记的是多少、上次盘是什么时候
 *
 * 三个参数都可选、可组合。⚠️ `item_ids` 传空串或写坏时后端会**当成不按 id 过滤**
 * （而不是「一件都不选」）—— 否则参数写错会伪装成「你的清单是空的」。
 */
export function getSurvivalWorksheet(params?: {
  category_id?: number
  item_ids?: string
  keyword?: string
}) {
  return request({ url: '/wealth/survival/stocktakes/worksheet/', method: 'get', params })
}

/** 盘点历史 —— 后端按日期**倒序**返回（最近一次在最上面） */
export function getSurvivalStocktakes(params?: { limit?: number }) {
  return request({ url: '/wealth/survival/stocktakes/', method: 'get', params })
}

/** 单次盘点（含明细） */
export function getSurvivalStocktake(id: number) {
  return request({ url: `/wealth/survival/stocktakes/${id}/`, method: 'get' })
}

/**
 * 提交一次盘点。
 *
 * ⚠️ 只提交实盘数：账面由服务端在提交那一刻读（见类型文件里的说明）。
 *    提交成功后库存会被校准成实盘数 —— 这一点要告知用户，不能悄悄改。
 */
export function createSurvivalStocktake(data: SurvivalStocktakeFormData) {
  return request({ url: '/wealth/survival/stocktakes/', method: 'post', data })
}

/** 删掉一条盘点记录 —— ⚠️ **不会**回滚库存（库存是被核实过的事实） */
export function deleteSurvivalStocktake(id: number) {
  return request({ url: `/wealth/survival/stocktakes/${id}/`, method: 'delete' })
}

// ── 必需品基准清单与缺口对账（v3.59.7） ──
//
// 这一组回答的是**另一个问题**：不是「够撑多久」，而是「漏了什么」。
// 基准项 = 「一个人生活本该有什么」（可增删改，不含数量）；
// 物品   = 「我实际有多少」。两者靠 item_id 对上，对不上就是缺口。

/**
 * 基准清单 + 逐项对账 —— 裸数组
 *
 * ⚠️ 默认按**紧迫度**排（该先处理的在前）：核心优先 → 档位严重度 → 天数升序。
 *    要看录入顺序（管理界面）传 `sort: 'order'`。
 *    一张按名字排的对账表，等于把最要紧的那件藏进中间几行。
 */
export function getSurvivalEssentials(params?: {
  category_id?: number
  scope?: string
  sort?: 'urgency' | 'order'
}) {
  return request({ url: '/wealth/survival/essentials/', method: 'get', params })
}

export function createSurvivalEssential(data: SurvivalEssentialFormData) {
  return request({ url: '/wealth/survival/essentials/', method: 'post', data })
}

export function updateSurvivalEssential(
  id: number,
  data: Partial<SurvivalEssentialFormData>,
) {
  return request({ url: `/wealth/survival/essentials/${id}/`, method: 'patch', data })
}

/**
 * 删一件基准项 —— 只影响这把尺子
 *
 * ⚠️ 与删物品刻意不同：**不动任何库存**。关联的物品是用户的资产，
 *    不该因为少了一条认知就跟着消失。
 */
export function deleteSurvivalEssential(id: number) {
  return request({ url: `/wealth/survival/essentials/${id}/`, method: 'delete' })
}

/** 对账的汇总与最短的一件（明细走列表端点，不在这里重复下发） */
export function getSurvivalEssentialReconcile() {
  return request({ url: '/wealth/survival/essentials/reconcile/', method: 'get' })
}

/**
 * 写入必需品基准清单（幂等；**不预设任何库存数量**）
 *
 * ⚠️ 只给「名字 + 归属 + 提示」这把尺子，不给数量 —— 数量是用户自己的事实。
 *    归属类别不存在时走 `missing_categories` 报告，不凭空建类别。
 */
export function seedSurvivalEssentials(data?: { overwrite?: boolean }) {
  return request({ url: '/wealth/survival/essentials/seed/', method: 'post', data: data ?? {} })
}

// ── 库存流水（v3.60.18 · P0）──
// ⚠️ 列表端点同样是**裸数组**（后端 ViewSet 不走全局分页）。
// 🔴 **登记入口在物品上，不在这个页签里** —— 这里只负责「查」。

export function getSurvivalFlows(params?: {
  item_id?: number
  category_name?: string
  channel?: string
  reason?: string
  date_from?: string
  date_to?: string
  keyword?: string
  limit?: number
}) {
  return request({ url: '/wealth/survival/flows/', method: 'get', params })
}

/**
 * 记一笔（`delta` 正负皆可）；带 `rows` 时按批量处理。
 *
 * ⚠️ 两个入口共用一个端点：单件与批量是同一件事的两种规模，
 *    分开成两条路径会让「批量提交」有第二套校验。
 */
export function createSurvivalFlow(data: SurvivalFlowFormData | SurvivalFlowBatchFormData) {
  return request({ url: '/wealth/survival/flows/', method: 'post', data })
}

/** 撤销 = 补一条反向流水（**不是删除**）。一条流水最多被冲销一次。 */
export function reverseSurvivalFlow(id: number) {
  return request({ url: `/wealth/survival/flows/${id}/reverse/`, method: 'post' })
}

/** 按月汇总 —— 「这个月吃掉多少」。⚠️ 跨单位不相加，按 `by_unit` 分列看。 */
export function getSurvivalFlowSummary(params?: { month?: string }) {
  return request({ url: '/wealth/survival/flows/summary/', method: 'get', params })
}
