<template>
  <div class="ratio-panel">
    <div class="panel-header">
      <div class="panel-header__left">
        <h3>财务规划比率</h3>
        <span class="panel-header__hint">
          判定区间由后端下发 —— 前端只上色、不做除法、不持有阈值
        </span>
      </div>
      <div class="panel-header__right">
        <el-select
          :model-value="store.anchorYearmon"
          size="small"
          placeholder="最新一期"
          clearable
          style="width: 140px"
          :disabled="!store.anchors.length"
          @update:model-value="handleAnchorChange"
        >
          <el-option
            v-for="ym in store.anchors"
            :key="ym"
            :label="ym"
            :value="ym"
          />
        </el-select>
        <el-button size="small" :loading="store.loading" @click="refresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div v-if="!store.overview" class="ratio-panel__empty">
      {{ store.loading ? '加载中…' : '暂无比率数据' }}
    </div>

    <template v-else>
      <!-- 取数来源与资产位置：让「分子取自哪张表、哪一期」可见 -->
      <div class="source-strip">
        <div class="source-strip__item">
          <span class="label">锚定月</span>
          <span class="value">{{ store.overview.anchor_yearmon }}</span>
        </div>
        <div class="source-strip__item">
          <span class="label">资产来源</span>
          <span class="value">{{ store.overview.asset_source_label }}</span>
        </div>
        <div class="source-strip__item">
          <span class="label">净资产</span>
          <span class="value">{{ money(pos.net_worth) }}</span>
          <span v-if="pos.carried" class="sub warn">
            取自 {{ pos.yearmon }}（本月未盘点）
          </span>
        </div>
        <div class="source-strip__item">
          <span class="label">现金类资产</span>
          <span class="value">{{ money(pos.liquid) }}</span>
        </div>
        <div class="source-strip__item">
          <span class="label">负债台账</span>
          <span class="value">{{ liabilityText }}</span>
        </div>
      </div>

      <div v-if="!pos.available" class="source-warning">
        <el-icon><Warning /></el-icon>
        <span>资产位置取不到：{{ pos.reason }} —— 依赖资产的比率将整体判为「数据不足」</span>
      </div>

      <!-- 六项比率 -->
      <div class="ratio-grid">
        <RatioCard
          v-for="item in store.overview.ratios"
          :key="item.key"
          :item="item"
          :meta="store.metaByKey[item.key] ?? null"
          @expand-opening="openOpening"
        />
      </div>

      <!-- 缺口清单：不可用项集中一处，每条都带补救动作 -->
      <div v-if="store.overview.gaps.length" class="gap-box">
        <div class="gap-box__title">
          <el-icon><Warning /></el-icon>
          还有 {{ store.overview.gaps.length }} 项算不出来 —— 不是因为差，是因为缺数据
        </div>
        <div v-for="gap in store.overview.gaps" :key="gap.key" class="gap-box__row">
          <span class="gap-box__label">{{ gap.label }}</span>
          <span class="gap-box__reason">{{ gap.reason }}</span>
          <span v-if="gap.hint" class="gap-box__hint">{{ gap.hint }}</span>
        </div>
      </div>

      <el-divider />

      <RatioTrend
        :trend="store.trend"
        :months="store.trendMonths"
        :items="trendItems"
        @update:months="store.setTrendMonths($event)"
      />
    </template>

    <!-- 净增长率的期初 vs 期末对照 -->
    <el-dialog
      v-model="openingVisible"
      :title="`净值增长率 · 期初 vs 期末`"
      width="560px"
    >
      <div v-if="store.loadingOpening" class="opening-loading">加载中…</div>
      <div v-else-if="opening && !opening.available" class="opening-missing">
        {{ opening.reason }}
      </div>
      <table v-else-if="opening" class="opening-table">
        <thead>
          <tr>
            <th>项目</th>
            <th>{{ opening.yearmon }}（期初）</th>
            <th>{{ pos.yearmon }}（期末）</th>
            <th>变化</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in openingRows" :key="row.label">
            <td class="opening-table__label">{{ row.label }}</td>
            <td>{{ money(row.start) }}</td>
            <td>{{ money(row.end) }}</td>
            <td>{{ delta(row.end, row.start) }}</td>
          </tr>
        </tbody>
      </table>
      <template #footer>
        <el-button @click="openingVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Refresh, Warning } from '@element-plus/icons-vue'
import RatioCard from './RatioCard.vue'
import RatioTrend from './RatioTrend.vue'
import { useRatioStore } from '../../stores/ratioStore'
import { formatSignedAmount } from '@/shared/utils/format'
import type { RatioAssetPosition } from '../../types/wealthTypes'

/**
 * 财务规划比率面板（P2-A）。
 *
 * 三件事必须由本面板负责，别的组件看不到：
 *   ① **锚定月**：比率是「看哪一期」的截面，锚定月一换整组数都变；
 *      选择器的候选来自资产快照期别（后端 `available_anchor_months`），
 *      不是账单期别 —— 选一个没有快照的月份只会得到一屏「数据不足」。
 *   ② **取数来源**：新科目体系与旧表是两把尺子，整条序列一起切。
 *      `asset_source_label` 与 `carried` 标记必须显式展示，否则用户会
 *      以为比率已经跑在新体系上 / 以为本月已经盘点过。
 *   ③ **期初对照**：净值增长率的期初位置是**第二个时点**，按需下钻，
 *      不跟总览一起拉（详见 ratioStore 的说明）。
 */
const store = useRatioStore()
const openingVisible = ref(false)

/** 空形状而非 `{}` 强转：接口不可用时字段仍齐全，取值处不必再判一次 */
const EMPTY_POSITION: RatioAssetPosition = {
  available: false,
  yearmon: null,
  snapshot_date: null,
  source: null,
  liquid: null,
  receivable: null,
  financial_assets: null,
  self_use_total: null,
  total_assets: null,
  borrow: null,
  net_worth: null,
  carried: false,
  reason: null,
}

const pos = computed<RatioAssetPosition>(
  () => store.overview?.asset_position ?? EMPTY_POSITION,
)
const opening = computed(() => store.openingPosition)

/** 金额一律走 formatSignedAmount —— 货币符号在符号位之前，且自带隐私掩码 */
function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return formatSignedAmount(v, 2, false)
}

/**
 * 变化列**刻意不着色**。
 *   按符号上色（+绿 / −红）在「借款」这一行会给出反向信号 ——
 *   借款增加被画成绿色，等于把负债扩张说成好消息。
 *   要按语义上色就得逐行声明方向，而那份方向表后端没给，
 *   故宁可不上色，也不上一个会误读的颜色。
 */
function delta(end: number | null | undefined, start: number | null | undefined): string {
  if (end === null || end === undefined || start === null || start === undefined) return '—'
  return formatSignedAmount((end ?? 0) - (start ?? 0), 2, true)
}

const liabilityText = computed(() => {
  const s = store.overview?.liability_state
  if (!s) return '—'
  if (s.state === 'empty') return '未录入'
  if (s.state === 'none_active') return `${s.total} 笔，均不在还`
  return `${s.active} 笔在还`
})

const OPENING_ROWS: { label: string; field: keyof RatioAssetPosition }[] = [
  { label: '现金类资产', field: 'liquid' },
  { label: '应收借出', field: 'receivable' },
  { label: '金融资产', field: 'financial_assets' },
  { label: '自用资产', field: 'self_use_total' },
  { label: '总资产', field: 'total_assets' },
  { label: '借款', field: 'borrow' },
  { label: '净资产', field: 'net_worth' },
]

const openingRows = computed(() => {
  const start = opening.value
  const end = pos.value
  if (!start) return []
  return OPENING_ROWS.map((r) => ({
    label: r.label,
    start: (start[r.field] as number | null) ?? null,
    end: (end[r.field] as number | null) ?? null,
  }))
})

/** 趋势区按总览的顺序排 —— 与卡片一一对应，不另起一套顺序 */
const trendItems = computed(() =>
  (store.overview?.ratios ?? []).map((r) => ({
    key: r.key, label: r.label, unit: r.unit,
  })),
)

function refresh() {
  store.clearOpeningPosition()
  store.fetchAll()
}

function handleAnchorChange(value: string | null) {
  store.setAnchor(value ?? '')
}

function openOpening(yearmon: string) {
  openingVisible.value = true
  store.fetchOpeningPosition(yearmon)
}

/**
 * 刻意**不在这里 onMounted 取数** —— 与 ClassifyRulePanel 等既有面板一致：
 * 取数由父视图（CashFlowView）在 onMounted / 刷新时统一驱动。
 * 面板各自取数会让「点一次刷新发几次请求」变得不可预测。
 */
</script>

<style scoped>
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}
.panel-header__left h3 { margin: 0; font-size: 16px; }
.panel-header__hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.panel-header__right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: none;
}

.source-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 22px;
  padding: 10px 14px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  margin-bottom: 14px;
}
.source-strip__item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
}
.source-strip__item .label { color: var(--el-text-color-secondary); }
.source-strip__item .value { font-weight: 600; }
.source-strip__item .sub { color: var(--el-text-color-secondary); }
.source-strip__item .sub.warn { color: var(--el-color-warning); }

.source-warning {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 14px;
  font-size: 12px;
  color: var(--el-color-warning);
}

.ratio-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  /*
   * 同行卡片等高**只由这一条负责**（stretch 是本属性的默认值，
   * 显式写出来是为了让「谁在保证等高」有据可查）。
   * ⚠️ 子项 `.ratio-card` **不能**再用 `height: 100%` 来实现等高 ——
   * 本项目 box-sizing 是 content-box，两者同时存在会让卡片边框盒比
   * 网格轨道多 30px，向下压住下一行 16px（下一行卡片背景把上一行
   * 底部盖掉，看起来就是「卡片交叠」）。原因、四组实测与修法见
   * RatioCard.vue 的注释。
   */
  align-items: stretch;
  margin-bottom: 14px;
}

.gap-box {
  border: 1px solid var(--el-color-warning-light-5);
  background: var(--el-color-warning-light-9);
  border-radius: 6px;
  padding: 12px 14px;
}
.gap-box__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.gap-box__row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  line-height: 1.9;
}
.gap-box__label { font-weight: 600; flex: none; min-width: 92px; }
.gap-box__reason { color: var(--el-text-color-regular); }
.gap-box__hint { color: var(--el-text-color-secondary); }

.ratio-panel__empty {
  padding: 32px;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}

.opening-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.opening-table th,
.opening-table td {
  padding: 7px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  text-align: right;
}
.opening-table th:first-child,
.opening-table td:first-child { text-align: left; }
.opening-table thead th {
  font-weight: 600;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-light);
}
.opening-table__label { color: var(--el-text-color-regular); }
.opening-loading,
.opening-missing {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

@media (max-width: 768px) {
  .panel-header { flex-direction: column; }
  .panel-header__right { width: 100%; }
}
</style>
