/**
 * 生存资源盘点状态（v3.59.0，P3-A 一期）
 *
 * 🔴 这个 store 里**不允许出现任何算法或阈值**：
 *    可支撑餐数、三档天数、短板、瓶颈判定全部在后端算好下发。
 *    前端只做三件事 —— 展示、上色、「算不出来」时把原因说清楚。
 *    在这里补一个 `?? 0` 或一句「其实就是除一下」，
 *    就等于口径有了两份，改后端时必然漏改。
 *
 * ⚠️ 第二个必须理解的行为：`null` **不等于 0**。
 *    「没填单件可用天数」「配方缺件」「单位不可比」都会返回 null + issues，
 *    而 0 是「真的撑 0 天」的结论。四卡上的空值要显示「算不出来」，
 *    绝不能掉成 0 —— 那会把「还没配置」显示成「明天就断粮」。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as survivalApi from '../api/survivalApi'
import type {
  SurvivalAnalysis,
  SurvivalCategory,
  SurvivalCategoryFormData,
  SurvivalCombo,
  SurvivalComboFormData,
  SurvivalEssential,
  SurvivalEssentialFormData,
  SurvivalEssentialReconcile,
  SurvivalEssentialSeedResult,
  SurvivalItem,
  SurvivalItemFormData,
  SurvivalMeta,
  SurvivalRecipe,
  SurvivalRecipeFormData,
  SurvivalSnapshot,
  SurvivalSnapshotCreateFormData,
  SurvivalStocktake,
  SurvivalStocktakeFormData,
  SurvivalTrend,
  SurvivalUnit,
  SurvivalUnitFormData,
  SurvivalWorksheetRow,
} from '../types/survivalTypes'
import type { RatioMeta } from '../types/wealthTypes'

export const useSurvivalStore = defineStore('survival', () => {
  // ─── 状态 ───
  const analysis = ref<SurvivalAnalysis | null>(null)
  const meta = ref<SurvivalMeta | null>(null)
  /** 类别（含单位清单）—— 配置弹窗与筛选下拉都从它取 */
  const categories = ref<SurvivalCategory[]>([])
  const units = ref<SurvivalUnit[]>([])
  const items = ref<SurvivalItem[]>([])
  const recipes = ref<SurvivalRecipe[]>([])
  /** 组合（v3.59.13）—— 分开登记、一起下锅；配方行引用它 */
  const combos = ref<SurvivalCombo[]>([])
  /** 盘点快照 —— **最近的在最前**（表格用；趋势那份是升序，别混用） */
  const snapshots = ref<SurvivalSnapshot[]>([])
  const snapshotTrend = ref<SurvivalTrend | null>(null)
  /**
   * 盘点工作表 —— 摊开的物品清单，逐项对实物用。
   *
   * ⚠️ 它与 `items` 是**两个来源**，别互相替代：
   *    `items` 是主数据（弹窗编辑用），`worksheet` 是某一刻的快照视图，
   *    多了「上次盘点是哪天」「该不该盘」「是否低于补货线」这些**随时间变**的列。
   */
  const worksheet = ref<SurvivalWorksheetRow[]>([])
  /** 实盘盘点历史 —— **最近一次在最上面**（与快照列表同向） */
  const stocktakes = ref<SurvivalStocktake[]>([])
  /**
   * 必需品基准清单（含逐项对账结果）—— **按紧迫度排**，最该处理的在最前。
   *
   * ⚠️ 它与 `items` 是两个来源，别互相替代：
   *    `items` 是「我实际有多少」（库存事实），
   *    `essentials` 是「我本该有什么」+ 两者对上的结果（基准项**没有数量**，
   *    数量在它关联的那件物品上）。
   */
  const essentials = ref<SurvivalEssential[]>([])

  const loading = ref(false)
  const saving = ref(false)
  /** 当前查看的类别 id；null = 还没选（首屏默认落到第一个类别） */
  const activeCategoryId = ref<number | null>(null)
  /** 参考日期，'' = 今天 */
  const referenceDate = ref<string>('')

  // ─── 派生 ───
  /** key → 口径元信息；气泡用它取文案，取不到时返回 null（不渲染空气泡） */
  const metricMetaByKey = computed<Record<string, RatioMeta>>(() => {
    const map: Record<string, RatioMeta> = {}
    for (const item of meta.value?.metric_meta ?? []) map[item.key] = item
    return map
  })

  const activeCategory = computed<SurvivalCategory | null>(
    () => categories.value.find((c) => c.id === activeCategoryId.value) ?? null,
  )

  const activeCategoryResult = computed(
    () => analysis.value?.categories.find((c) => c.category_id === activeCategoryId.value) ?? null,
  )

  const activeUnits = computed(
    () => units.value.filter((u) => u.category_id === activeCategoryId.value),
  )

  /** 有配置问题时要显式提示 —— 「看不见的数据」比「错的数据」更危险 */
  const hasIssues = computed(() => (analysis.value?.issues.length ?? 0) > 0)

  /**
   * 最近两期的对比。
   *
   * ⚠️ 这里**不把 delta 加工成「涨了/跌了」的结论**：`comparable === false` 时
   *    那个差里混着「换了算法」这一项，必须先让界面把 reason 说清楚。
   */
  const snapshotComparison = computed(() => snapshotTrend.value?.comparison ?? null)

  /** 至少两期才谈得上方向 —— 一个点是状态，两个点才有方向 */
  const hasTrendDirection = computed(
    () => snapshotTrend.value?.has_enough_points ?? false,
  )

  /**
   * 该盘的物品：设了盘点周期、且已到期（含从未盘过）。
   *
   * 「该不该盘」由后端判，前端只是筛一下 —— 判据里带着「没设周期就不催」
   * 这条规则，在前端重写一遍迟早会漏掉它，然后所有物品一起标红。
   */
  const dueItems = computed(() => worksheet.value.filter((row) => row.stocktake_due))

  /** 已降到补货线的物品 —— 「看不见的数据」比「错的数据」更危险，得显式列出来 */
  const restockItems = computed(
    () => worksheet.value.filter((row) => row.below_threshold),
  )

  // ─── 必需品对账（派生） ───

  /**
   * 对账汇总 —— **直接取分析里的那一份**，不从 `essentials` 数组自己数一遍。
   *
   * ⚠️ 自己数就会出现「总览说缺 3 件、列表明明有 4 件」这种自相矛盾，
   *    而原因仅仅是其中一处忘了刷新。同一个数字只留一个来源。
   */
  const essentialReconcile = computed<SurvivalEssentialReconcile | null>(
    () => analysis.value?.essentials ?? null,
  )

  const essentialSummary = computed(() => essentialReconcile.value?.summary ?? null)

  /**
   * 核心必需品里最先见底的那一件。
   *
   * ⚠️ 它**不是**「生存短板」的替代品：短板由各类别天数取最小得出，
   *    这条是必需品这一层的读数。两者并列展示，不互相覆盖。
   */
  const essentialShortest = computed(() => essentialReconcile.value?.shortest ?? null)

  const essentialUnclosed = computed(
    () => essentialSummary.value?.unclosed_core ?? [],
  )

  /** 档位 → 中文标签。标签真源在 meta，前端**不写死文案** */
  const essentialLevelLabel = computed<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    for (const opt of meta.value?.essential_levels ?? []) map[opt.value] = opt.label
    return map
  })

  /** 性质 → 中文标签（底线必需 / 改善型） */
  const essentialScopeLabel = computed<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    for (const opt of meta.value?.essential_scopes ?? []) map[opt.value] = opt.label
    return map
  })

  // ─── 取数 ───
  async function fetchAnalysis() {
    try {
      const resp = await survivalApi.getSurvivalAnalysis(
        referenceDate.value ? { date: referenceDate.value } : undefined,
      )
      analysis.value = (resp.data as SurvivalAnalysis) ?? null
    } catch (e) {
      console.error('获取生存资源分析失败:', e)
      analysis.value = null
    }
  }

  /** 口径与枚举只拉一次 —— 它是静态说明，与参考日期无关 */
  async function fetchMeta() {
    if (meta.value) return
    try {
      const resp = await survivalApi.getSurvivalMeta()
      meta.value = (resp.data as SurvivalMeta) ?? null
    } catch (e) {
      console.error('获取生存资源口径失败:', e)
    }
  }

  async function fetchCategories() {
    try {
      const resp = await survivalApi.getSurvivalCategories({ include_units: 1 })
      // 后端返回裸数组；被全局分页包住时这里会拿到 undefined，兜底成空数组
      const rows = (resp.data as SurvivalCategory[]) ?? []
      categories.value = Array.isArray(rows) ? rows : []
      if (activeCategoryId.value === null && categories.value.length) {
        activeCategoryId.value = categories.value[0].id
      }
    } catch (e) {
      console.error('获取物资类别失败:', e)
      categories.value = []
    }
  }

  async function fetchUnits() {
    try {
      const resp = await survivalApi.getSurvivalUnits()
      const rows = (resp.data as SurvivalUnit[]) ?? []
      units.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取消耗单位失败:', e)
      units.value = []
    }
  }

  async function fetchItems() {
    try {
      const resp = await survivalApi.getSurvivalItems()
      const rows = (resp.data as SurvivalItem[]) ?? []
      items.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取物资失败:', e)
      items.value = []
    }
  }

  /**
   * 必需品基准清单 + 逐项对账
   *
   * `sort` 默认 `'urgency'`（后端按紧迫度排）；管理界面要看录入顺序时传 `'order'`。
   */
  async function fetchEssentials(params?: { sort?: 'urgency' | 'order' }) {
    try {
      const resp = await survivalApi.getSurvivalEssentials(params)
      // 后端返回裸数组；被全局分页包住时这里会拿到 undefined，兜底成空数组
      const rows = (resp.data as SurvivalEssential[]) ?? []
      essentials.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取必需品基准清单失败:', e)
      essentials.value = []
    }
  }

  async function fetchRecipes() {
    try {
      const resp = await survivalApi.getSurvivalRecipes()
      const rows = (resp.data as SurvivalRecipe[]) ?? []
      recipes.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取配餐配方失败:', e)
      recipes.value = []
    }
  }

  async function fetchCombos() {
    try {
      const resp = await survivalApi.getSurvivalCombos()
      const rows = (resp.data as SurvivalCombo[]) ?? []
      combos.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取组合失败:', e)
      combos.value = []
    }
  }

  async function fetchSnapshots() {
    try {
      const resp = await survivalApi.getSurvivalSnapshots()
      const rows = (resp.data as SurvivalSnapshot[]) ?? []
      snapshots.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取盘点快照失败:', e)
      snapshots.value = []
    }
  }

  async function fetchSnapshotTrend() {
    try {
      const resp = await survivalApi.getSurvivalSnapshotTrend()
      snapshotTrend.value = (resp.data as SurvivalTrend) ?? null
    } catch (e) {
      console.error('获取盘点趋势失败:', e)
      snapshotTrend.value = null
    }
  }

  /**
   * 盘点工作表（全量）—— 清单页与类别明细的「上次盘点 / 该不该盘」列都取自它。
   *
   * ⚠️ 不传参数就是全量。它是**共享状态**，任何只想看几行的调用点
   *    都不要改它 —— 用 `fetchWorksheetRows()` 拿一份临时的，
   *    否则清单页的列会在弹窗关掉之后整片落空（静默错）。
   */
  async function fetchWorksheet(params?: {
    category_id?: number
    item_ids?: number[]
    keyword?: string
  }) {
    try {
      const resp = await survivalApi.getSurvivalWorksheet(params ? {
        category_id: params.category_id,
        item_ids: params.item_ids?.length ? params.item_ids.join(',') : undefined,
        keyword: params.keyword,
      } : undefined)
      const rows = (resp.data as SurvivalWorksheetRow[]) ?? []
      worksheet.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取盘点工作表失败:', e)
      worksheet.value = []
    }
  }

  /**
   * 只要这几件的工作表行，**且不写进共享状态**。
   *
   * 用途：单件盘点弹窗 —— 它只关心一件的最新账面，
   * 拉 43 行是白拉（后端 `get_worksheet(item_ids=...)` 早就支持，
   * 前端一直没传参数，见设计稿 §2.3）。
   *
   * ⚠️ 刻意不复用 `worksheet` —— 那会把共享的全量表替换成子集，
   *    清单页的「上次盘点」列随即整片落空，而且**界面不会报错**。
   *    失败返回空数组：调用方拿不到行就退回「用父级传来的账面」，
   *    不让一次网络抖动挡住盘点这件事。
   */
  async function fetchWorksheetRows(itemIds: number[]): Promise<SurvivalWorksheetRow[]> {
    if (!itemIds.length) return []
    try {
      const resp = await survivalApi.getSurvivalWorksheet({ item_ids: itemIds.join(',') })
      const rows = (resp.data as SurvivalWorksheetRow[]) ?? []
      return Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取盘点工作表（按物品）失败:', e)
      return []
    }
  }

  async function fetchStocktakes() {
    try {
      const resp = await survivalApi.getSurvivalStocktakes()
      const rows = (resp.data as SurvivalStocktake[]) ?? []
      stocktakes.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取盘点历史失败:', e)
      stocktakes.value = []
    }
  }

  /** 首屏：口径 + 类别 + 单位先起，分析与明细随后 —— 卡先出来再填数 */
  async function fetchAll() {
    loading.value = true
    try {
      await Promise.all([fetchMeta(), fetchCategories(), fetchUnits()])
      await Promise.all([
        fetchAnalysis(), fetchItems(), fetchRecipes(), fetchCombos(), fetchSnapshots(),
        fetchSnapshotTrend(), fetchWorksheet(), fetchStocktakes(),
      ])
    } finally {
      loading.value = false
    }
  }

  /** 任何写入之后统一重拉：派生值全在后端算，前端没有自己的缓存要对齐 */
  async function refreshAll() {
    await Promise.all([
      fetchCategories(), fetchUnits(), fetchAnalysis(), fetchItems(), fetchRecipes(),
      fetchCombos(), fetchSnapshots(), fetchSnapshotTrend(), fetchWorksheet(),
      fetchStocktakes(), fetchEssentials(),
    ])
  }

  // ─── 类别 ───
  async function saveCategory(data: SurvivalCategoryFormData, id?: number) {
    saving.value = true
    try {
      if (id) await survivalApi.updateSurvivalCategory(id, data)
      else await survivalApi.createSurvivalCategory(data)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  async function removeCategory(id: number) {
    saving.value = true
    try {
      await survivalApi.deleteSurvivalCategory(id)
      if (activeCategoryId.value === id) activeCategoryId.value = null
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  /** 初始化默认类别与单位（幂等） */
  async function seedDefaults(overwrite = false) {
    saving.value = true
    try {
      const resp = await survivalApi.seedSurvivalDefaults({ overwrite })
      await refreshAll()
      return resp.data
    } finally {
      saving.value = false
    }
  }

  // ─── 单位 ───
  /** 返回新建/更新后的那一行 —— 调用方要拿它把新单位**就地选中** */
  async function saveUnit(data: SurvivalUnitFormData, id?: number) {
    saving.value = true
    try {
      const resp = id
        ? await survivalApi.updateSurvivalUnit(id, data)
        : await survivalApi.createSurvivalUnit(data)
      await refreshAll()
      return resp.data as SurvivalUnit
    } finally {
      saving.value = false
    }
  }

  async function removeUnit(id: number) {
    saving.value = true
    try {
      await survivalApi.deleteSurvivalUnit(id)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  // ─── 物品 ───
  async function saveItem(data: SurvivalItemFormData, id?: number) {
    saving.value = true
    try {
      if (id) await survivalApi.updateSurvivalItem(id, data)
      else await survivalApi.createSurvivalItem(data)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  async function removeItem(id: number) {
    saving.value = true
    try {
      await survivalApi.deleteSurvivalItem(id)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  // ─── 必需品基准清单（v3.59.7） ───

  /**
   * 新增 / 更新一件基准项
   *
   * ⚠️ 两处都要刷新：列表（`essentials`）与分析里的汇总（`analysis.essentials`）。
   *    只刷一处就会出现「列表显示已录入、总览还说缺 1 件」——
   *    而用户会以为是自己看错了。
   */
  async function saveEssential(data: SurvivalEssentialFormData, id?: number) {
    saving.value = true
    try {
      if (id) await survivalApi.updateSurvivalEssential(id, data)
      else await survivalApi.createSurvivalEssential(data)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  /**
   * 删一件基准项
   *
   * ⚠️ 只影响「本该有什么」这把尺子，**不动任何库存** ——
   *    关联的物品是用户的资产，不该因为少了一条认知就跟着消失。
   */
  async function removeEssential(id: number) {
    saving.value = true
    try {
      await survivalApi.deleteSurvivalEssential(id)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  /**
   * 关联一组已有物品（传空数组 = 全部解除）
   *
   * 单独开一个动作而不是让用户在弹窗里填 id：对账的绝大多数操作就是
   * 「把我柜子里这几件挂到那条基准上」，那应该是一次点击，不是一串数字。
   *
   * ⚠️ 解除关联时要送**空数组**、不能省略这个字段 —— 省略是「这次不动它」，
   *    而用户点掉最后一个勾时他的意思是「这件不归它管了」。
   */
  async function linkEssentialItems(essentialId: number, itemIds: number[]) {
    saving.value = true
    try {
      await survivalApi.updateSurvivalEssential(essentialId, { item_ids: itemIds })
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  /**
   * 写入必需品基准清单（幂等）
   *
   * ⚠️ 归属类别不存在时后端走 `missing_categories` 报告，**不凭空建类别** ——
   *    所以这里要把结果原样返回给界面，让用户知道有哪几项被跳过了，
   *    否则他会以为清单本来就这么长。
   */
  async function seedEssentials(overwrite = false) {
    saving.value = true
    try {
      const resp = await survivalApi.seedSurvivalEssentials({ overwrite })
      await refreshAll()
      return resp.data as SurvivalEssentialSeedResult
    } finally {
      saving.value = false
    }
  }

  // ─── 配方 ───
  async function saveRecipe(data: SurvivalRecipeFormData, id?: number) {
    saving.value = true
    try {
      if (id) await survivalApi.updateSurvivalRecipe(id, data)
      else await survivalApi.createSurvivalRecipe(data)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  async function removeRecipe(id: number) {
    saving.value = true
    try {
      await survivalApi.deleteSurvivalRecipe(id)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  // ─── 组合 ───

  /**
   * 保存组合。
   *
   * ⚠️ 改一个组合会**同时影响所有引用它的配方** —— 这是可复用实体的代价，
   *    也是它的收益。保存后一律 `refreshAll`，不试图只改本地那一行：
   *    配方的天数会跟着变，而「改了组合但天数还是旧的」是最难发现的一类不一致。
   */
  /**
   * 保存组合 —— 新建时**返回刚建好的那一条**。
   *
   * 返回值不是装饰：配方弹窗里可以「就地新建组合」，建完必须把新组合填回当前那一行。
   * 只调 `refreshAll()` 的话列表里确实有了它，但用户还得自己去下拉里再找一遍
   * （而且刚建的那条可能因为没配餐位而看不出是不是它）—— 等于白建。
   */
  async function saveCombo(
    data: SurvivalComboFormData,
    id?: number,
  ): Promise<SurvivalCombo | null> {
    saving.value = true
    try {
      let created: SurvivalCombo | null = null
      if (id) {
        await survivalApi.updateSurvivalCombo(id, data)
      } else {
        const resp = await survivalApi.createSurvivalCombo(data)
        created = (resp as { data?: SurvivalCombo })?.data ?? null
      }
      await refreshAll()
      return created
    } finally {
      saving.value = false
    }
  }

  async function removeCombo(id: number) {
    saving.value = true
    try {
      await survivalApi.deleteSurvivalCombo(id)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  // ─── 盘点快照 ───

  /**
   * 盘点：把此刻算出来的结论落成一份。
   *
   * 同一天重复盘点时后端返回 **400 + 可照做的提示**（不是静默覆盖），
   * 所以这里**原样抛出**：调用方要能读到那句话，才能问一句「要覆盖吗」。
   * 把错误吞掉换成「盘点失败」，用户就不知道该怎么继续了。
   */
  async function takeSnapshot(data: SurvivalSnapshotCreateFormData = {}) {
    saving.value = true
    try {
      const resp = await survivalApi.createSurvivalSnapshot(data)
      await Promise.all([fetchSnapshots(), fetchSnapshotTrend()])
      return resp.data as SurvivalSnapshot
    } finally {
      saving.value = false
    }
  }

  async function removeSnapshot(id: number) {
    saving.value = true
    try {
      await survivalApi.deleteSurvivalSnapshot(id)
      await Promise.all([fetchSnapshots(), fetchSnapshotTrend()])
    } finally {
      saving.value = false
    }
  }

  // ─── 实盘盘点（v3.59.3） ───

  /**
   * 提交一次盘点。
   *
   * 🔴 提交成功后**库存会被直接改成实盘数**（盘点即校准）—— 这一点必须
   *    在提交前就告诉用户。它不是一次只读核对，不说明就等于悄悄改了账。
   *
   * ⚠️ 错误**原样抛出**（同 `takeSnapshot`）：后端的报错会说清是哪一行
   *    不对（重复物品 / 负数 / 物品已删），吞成「盘点失败」用户就无从下手。
   */
  async function submitStocktake(data: SurvivalStocktakeFormData) {
    saving.value = true
    try {
      const resp = await survivalApi.createSurvivalStocktake(data)
      // 库存被改过 → 分析、物品、工作表、历史全要重拉。
      // 派生值全在后端，前端没有自己的缓存要对齐（与 refreshAll 的注释同理）。
      await refreshAll()
      return resp.data as SurvivalStocktake
    } finally {
      saving.value = false
    }
  }

  /**
   * 删除一条盘点记录。
   *
   * ⚠️ **不会回滚库存**（后端铁律三）—— 库存是已经被核实过的事实，
   *    删掉的只是凭据。调用方必须在确认框里把这句话说出来，
   *    否则用户会以为「删掉记录 = 撤销那次盘点」，而库存一点没变。
   */
  async function removeStocktake(id: number) {
    saving.value = true
    try {
      await survivalApi.deleteSurvivalStocktake(id)
      await Promise.all([fetchStocktakes(), fetchWorksheet()])
    } finally {
      saving.value = false
    }
  }

  function setActiveCategory(id: number) {
    activeCategoryId.value = id
  }

  async function setReferenceDate(value: string) {
    referenceDate.value = value
    await fetchAnalysis()
  }

  function resetState() {
    analysis.value = null
    categories.value = []
    units.value = []
    items.value = []
    recipes.value = []
    snapshots.value = []
    snapshotTrend.value = null
    worksheet.value = []
    stocktakes.value = []
    essentials.value = []
    combos.value = []
    activeCategoryId.value = null
    referenceDate.value = ''
    // meta 不清 —— 它是静态口径，清了会让下一次挂载多一个请求
  }

  return {
    analysis, meta, categories, units, items, recipes, combos, snapshots, snapshotTrend,
    worksheet, stocktakes, essentials,
    loading, saving, activeCategoryId, referenceDate,
    metricMetaByKey, activeCategory, activeCategoryResult, activeUnits, hasIssues,
    snapshotComparison, hasTrendDirection, dueItems, restockItems,
    essentialReconcile, essentialSummary, essentialShortest, essentialUnclosed,
    essentialLevelLabel, essentialScopeLabel,
    fetchAll, refreshAll, fetchAnalysis, fetchMeta,
    fetchCategories, fetchUnits, fetchItems, fetchRecipes, fetchCombos,
    fetchSnapshots, fetchSnapshotTrend, fetchWorksheet, fetchWorksheetRows,
    fetchStocktakes,
    fetchEssentials,
    saveCategory, removeCategory, seedDefaults,
    saveUnit, removeUnit, saveItem, removeItem, saveRecipe, removeRecipe,
    saveCombo, removeCombo,
    takeSnapshot, removeSnapshot, submitStocktake, removeStocktake,
    saveEssential, removeEssential, linkEssentialItems, seedEssentials,
    setActiveCategory, setReferenceDate, resetState,
  }
})
