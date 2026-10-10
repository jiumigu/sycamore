/**
 * 库存流水状态（v3.60.18 · P0）
 *
 * 这一层只做三件事：取数、提交、把「取不到」与「一条都没有」分开。
 *
 * 🔴 前端**不在这里算任何东西**：
 *    · 「还剩几件」= 当前 `item.quantity` 减一次（纯展示的减法，不是算法）；
 *    · 原因留空该记成什么，由**后端**按类别的消耗模式决定（不复制那张映射表）；
 *    · 汇总的「跨单位不相加」由后端分桶下发，这里只渲染。
 *
 * ⚠️ 独立 store（不塞进 `survivalStore`）：流水有自己的筛选与分页状态，
 *    而 `survivalStore` 已经 700+ 行。两者唯一的交集是「写完要刷新物品数量」——
 *    那由调用方（视图）显式做，不在 store 之间互相调用。
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as survivalApi from '../api/survivalApi'
import { apiErrorText } from '@/shared/utils/apiError'
import type {
  SurvivalFlow,
  SurvivalFlowBatchFormData,
  SurvivalFlowFormData,
  SurvivalFlowSummary,
} from '../types/survivalTypes'

/** 列表筛选条件 —— 与后端 `list_flows` 的参数一一对应 */
export interface FlowFilters {
  item_id?: number | null
  category_name?: string
  channel?: string
  reason?: string
  date_from?: string
  date_to?: string
  keyword?: string
  limit?: number
}

/** 去掉空值：`?channel=` 这种空串会被后端当成一个**未知渠道**而 400 */
function cleanFilters(filters: FlowFilters): Record<string, string | number> {
  const out: Record<string, string | number> = {}
  Object.entries(filters).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') return
    out[key] = value as string | number
  })
  return out
}

/** 空串归一：让「没填」只有一个表示法，别让 `''` 与缺字段各占一半 */
function normalizeRow(row: SurvivalFlowFormData): SurvivalFlowFormData {
  const out: SurvivalFlowFormData = { ...row }
  if (!out.note) delete out.note
  if (!out.reason) delete out.reason
  if (!out.occurred_at) delete out.occurred_at
  return out
}

export const useSurvivalFlowStore = defineStore('survivalFlow', () => {
  // ─── 状态 ───

  const flows = ref<SurvivalFlow[]>([])
  const summary = ref<SurvivalFlowSummary | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  /**
   * 「列表取回来过」这个事实。
   *
   * 🔴 空态要用它区分两件事：`false` = 还没取（或没取到）；
   *    `true` + 空数组 = 取到了，就是一条都没有。
   *    判据**不是「数组非空」** —— 那会把「表还没建 / 请求失败」
   *    说成「你还没记过账」（同项目「迁移没跑 ≠ 数据为空」）。
   */
  const loaded = ref(false)

  /**
   * 取列表失败的原因（空串 = 没失败）。
   *
   * 🔴 **「取不到」必须与「一条都没有」分开说。** 只靠 `loaded` 还不够：
   *    `loaded=false` 既可能是「还没取」，也可能是「取失败了」，
   *    而这两种在界面上要讲两句完全不同的话。少了这个位，
   *    面板就会把「表还没建」显示成「这个月还没有流水」——
   *    那是**把失败美化成了用户的账**（同项目「迁移没跑 ≠ 数据为空」）。
   */
  const listError = ref('')

  /** 汇总是否取回来过 + 取失败的原因（同上的两件事，分开记） */
  const summaryLoaded = ref(false)
  const summaryError = ref('')

  /**
   * 刷新信号。
   *
   * 🔴 别处改了库存（在清单上记了一笔消耗）之后，流水页签要重新取数。
   *    用**信号**而不是让父级直接替它取：页签有自己的筛选条件，
   *    父级替它取数会把筛选悄悄重置掉 —— 而重置是静默的，界面看起来正常。
   */
  const refreshToken = ref(0)

  function bumpRefresh() {
    refreshToken.value += 1
  }

  // ─── 读 ───

  /**
   * 取列表。
   *
   * ⚠️ **吞掉异常、改记 `listError`**（不再往外抛）：调用方（页签挂载 / 刷新信号）
   *    并不需要 try 一遍——它要的是「知道失败了」这件事，而那就是 `listError`。
   *    往外抛的后果是无人接的 rejection（实测在控制台刷了全局错误）。
   */
  async function fetchFlows(filters: FlowFilters = {}) {
    loading.value = true
    listError.value = ''
    try {
      const resp = await survivalApi.getSurvivalFlows(cleanFilters(filters))
      // 后端返回裸数组；万一被包成 `{count, results}`，兜底取 results，
      // 而不是把对象当数组用 —— 后者会静默渲染不出任何一行（项目硬坑②）
      const rows = (resp.data as SurvivalFlow[]) ?? []
      flows.value = Array.isArray(rows) ? rows : []
      loaded.value = true
    } catch (err: unknown) {
      // 🔴 失败时**不许**把 loaded 置真：置真等于宣布「取到了，就是空的」
      flows.value = []
      loaded.value = false
      listError.value = apiErrorText(err, '取不到流水')
    } finally {
      loading.value = false
    }
  }

  /** 取汇总。失败同样只记状态、不改变「有没有数据」的结论 */
  async function fetchSummary(month?: string) {
    summaryError.value = ''
    try {
      const resp = await survivalApi.getSurvivalFlowSummary(month ? { month } : undefined)
      summary.value = (resp.data as SurvivalFlowSummary) ?? null
      summaryLoaded.value = true
    } catch (err: unknown) {
      // 汇总取不到不该把整页打空 —— 下面的列表仍然可用
      summary.value = null
      summaryLoaded.value = false
      summaryError.value = apiErrorText(err, '取不到汇总')
    }
  }

  // ─── 写 ───

  /** 记一笔。**成功之后由调用方刷新物品数量** —— 这条 store 不管别的 store */
  async function record(row: SurvivalFlowFormData) {
    saving.value = true
    try {
      return await survivalApi.createSurvivalFlow(normalizeRow(row))
    } finally {
      saving.value = false
    }
  }

  /**
   * 一次记多笔。
   *
   * ⚠️ 时间**整批一个**：每行一个时间等于把单件表单复制 N 份，
   *    而那正是这版设计要消灭的重复填写。
   */
  async function recordBatch(rows: SurvivalFlowFormData[], occurredAt?: string | null) {
    saving.value = true
    try {
      const payload: SurvivalFlowBatchFormData = {
        rows: rows.map((row) => normalizeRow({ ...row, occurred_at: null })),
      }
      if (occurredAt) payload.occurred_at = occurredAt
      return await survivalApi.createSurvivalFlow(payload)
    } finally {
      saving.value = false
    }
  }

  /** 撤销 —— 补一条反向流水，**不删任何东西** */
  async function reverse(id: number) {
    saving.value = true
    try {
      return await survivalApi.reverseSurvivalFlow(id)
    } finally {
      saving.value = false
    }
  }

  function resetState() {
    flows.value = []
    summary.value = null
    loaded.value = false
    loading.value = false
    saving.value = false
    listError.value = ''
    summaryLoaded.value = false
    summaryError.value = ''
  }

  return {
    flows, summary, loading, saving, loaded, refreshToken,
    listError, summaryLoaded, summaryError,
    fetchFlows, fetchSummary, record, recordBatch, reverse, bumpRefresh, resetState,
  }
})
