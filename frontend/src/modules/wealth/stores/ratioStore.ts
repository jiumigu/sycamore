import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type {
  RatioOverview, RatioTrend, RatioAssetPosition, RatioMeta,
} from '../types/wealthTypes'

/**
 * 财务规划比率状态（P2-A）
 *
 * 🔴 这个 store 里**不允许出现任何阈值数字**。
 *   判定线（如「应急金 ≥ 6 个月算健康」）只在后端 `constants.RATIO_BANDS` 存在一份，
 *   随接口以 `bands` 下发；前端只负责**按 level 上色、按 bands 画刻度**。
 *   于是「调阈值」这件事永远只是后端改一个常量，前端零改动 —— 这是本版的全部意义。
 *   曾经的做法是在 HealthMetrics.vue 里写 `months >= target / 2`，
 *   阈值一变前后端就会各说各话，那种写法不要再回来。
 *
 * ⚠️ 第二个必须理解的行为：`value === null` **不等于 0**。
 *   「算不出来」（缺快照 / 支出为 0 / necessity 没填）返回 `available=false` + `value=null` + `reason`，
 *   而 0 是一个**结论**（如「你有 0 个月应急金」）。趋势序列同理，缺月必须画断点。
 *   任何 `?? 0` 都会把「没数据」翻转成最坏结论，别写。
 */

/** 趋势默认回看月数（后端允许 1–36） */
export const RATIO_TREND_MONTHS_DEFAULT = 12

export const useRatioStore = defineStore('ratio', () => {
  // ─── 状态 ───
  /** 六项比率总览（含判定区间、分子分母、不可用原因） */
  const overview = ref<RatioOverview | null>(null)
  /** 逐月比率序列（值已在后端算好，前端不做除法） */
  const trend = ref<RatioTrend | null>(null)
  /** 可作为锚定月的年月（倒序）；来自资产快照期别，不是账单期别 */
  const anchors = ref<string[]>([])
  /** 当前锚定月；'' = 让后端取最新一期 */
  const anchorYearmon = ref<string>('')
  /** 趋势回看月数 */
  const trendMonths = ref<number>(RATIO_TREND_MONTHS_DEFAULT)
  /**
   * 九项比率的口径元信息（公式 + 区间 + 口径说明）。
   *
   * 刻意**不**随锚定月走：口径是「这个指标怎么算」的说明，
   * 与「算哪一期」无关。换锚定月不该重拉它，否则每切一次月份就多一个请求，
   * 而返回内容一字不变。
   */
  const meta = ref<RatioMeta[]>([])

  /** key → 元信息；气泡靠它取值，找不到时返回 null（不渲染气泡而不是渲染空的） */
  const metaByKey = computed<Record<string, RatioMeta>>(() => {
    const map: Record<string, RatioMeta> = {}
    for (const item of meta.value) map[item.key] = item
    return map
  })

  /**
   * 净值增长率的**期初**资产位置。
   *
   * 刻意不并进 `overview`：总览一次只描述「锚定月」这一个时点，
   * 而期初位置是用户展开净值增长率时**按需下钻**的第二个时点。
   * 混进总览会让「换锚定月之后期初还停在旧月份」变成一个必须小心处理的陷阱。
   */
  const openingPosition = ref<RatioAssetPosition | null>(null)

  const loading = ref(false)
  const loadingOpening = ref(false)

  // ─── 取数 ───
  async function fetchOverview() {
    try {
      const resp = await wealthApi.getRatioOverview(
        anchorYearmon.value ? { yearmon: anchorYearmon.value } : undefined,
      )
      const data = (resp.data as RatioOverview) ?? null
      overview.value = data
      // 空锚定时把后端选中的月份回填到选择器，否则下拉框会显示为空、
      // 而界面上的数字其实属于另一个月份 —— 那是会让人误判的错位。
      if (!anchorYearmon.value && data?.anchor_yearmon) {
        anchorYearmon.value = data.anchor_yearmon
      }
    } catch (e) {
      console.error('获取比率总览失败:', e)
    }
  }

  async function fetchTrend() {
    try {
      const resp = await wealthApi.getRatioTrend({ months: trendMonths.value })
      trend.value = (resp.data as RatioTrend) ?? null
    } catch (e) {
      console.error('获取比率趋势失败:', e)
    }
  }

  async function fetchAnchors() {
    try {
      const resp = await wealthApi.getRatioAnchors()
      // 后端返回裸数组；若被全局分页包成 {count, results}，这里会拿到 undefined
      anchors.value = (resp.data as string[]) ?? []
    } catch (e) {
      console.error('获取可选锚定月失败:', e)
    }
  }

  /**
   * 拉某一期的资产位置（按期精确命中，不向前取整）。
   *
   * 用于净值增长率卡片的「期初 vs 期末」对照。
   * ⚠️ `carry_forward=0` 是刻意的：期初那一期若没有盘点，
   *   向前取更早一期会得到「两个不同的期初」，比「没有期初」更误导。
   */
  async function fetchOpeningPosition(yearmon: string) {
    if (!yearmon) {
      openingPosition.value = null
      return
    }
    loadingOpening.value = true
    try {
      const resp = await wealthApi.getRatioAssetPosition({
        yearmon,
        carry_forward: 0,
      })
      openingPosition.value = (resp.data as RatioAssetPosition) ?? null
    } catch (e) {
      console.error('获取期初资产位置失败:', e)
      openingPosition.value = null
    } finally {
      loadingOpening.value = false
    }
  }

  /** 口径元信息 —— 只拉一次，换锚定月不重拉（口径与期别无关） */
  async function fetchMeta() {
    if (meta.value.length) return
    try {
      const resp = await wealthApi.getRatioMeta()
      meta.value = (resp.data as RatioMeta[]) ?? []
    } catch (e) {
      console.error('获取比率口径说明失败:', e)
    }
  }

  /** 期初位置是「跟着某个月的明细」走的，锚定月一换就必须清掉 */
  function clearOpeningPosition() {
    openingPosition.value = null
  }

  async function fetchAll() {
    loading.value = true
    try {
      await Promise.all([fetchAnchors(), fetchMeta()])
      await Promise.all([fetchOverview(), fetchTrend()])
    } finally {
      loading.value = false
    }
  }

  /** 切换锚定月（'' = 回到最新一期） */
  async function setAnchor(value: string) {
    anchorYearmon.value = value
    clearOpeningPosition()
    await fetchOverview()
  }

  /** 切换趋势回看月数（只影响趋势，不动总览） */
  async function setTrendMonths(months: number) {
    trendMonths.value = months
    await fetchTrend()
  }

  function resetState() {
    overview.value = null
    trend.value = null
    anchors.value = []
    anchorYearmon.value = ''
    trendMonths.value = RATIO_TREND_MONTHS_DEFAULT
    openingPosition.value = null
    // meta 不清 —— 它是静态口径，清了会让下一次挂载多一个请求
  }

  return {
    overview, trend, anchors, anchorYearmon, trendMonths, openingPosition,
    meta, metaByKey,
    loading, loadingOpening,
    fetchOverview, fetchTrend, fetchAnchors, fetchOpeningPosition, fetchMeta,
    clearOpeningPosition, fetchAll, setAnchor, setTrendMonths, resetState,
  }
})
