<template>
  <div class="ratio-card" :class="{ 'is-missing': !item.available }">
    <div class="ratio-card__head">
      <span class="ratio-card__label">
        {{ item.label }}
        <!-- 口径气泡：公式 / 要点 / 档位全部来自后端，前端一句文案都不写 -->
        <MetricTooltip :meta="meta" />
      </span>
      <el-tag
        v-if="item.available && item.level"
        :type="tagType"
        size="small"
        effect="light"
      >{{ item.level_label }}</el-tag>
    </div>

    <div class="ratio-card__value-row">
      <template v-if="item.available">
        <span class="ratio-card__value" :class="item.level ?? 'normal'">
          {{ item.value }}
        </span>
        <span class="ratio-card__unit">{{ item.unit }}</span>
      </template>
      <span v-else class="ratio-card__value is-none">数据不可用</span>
    </div>

    <!-- 档位刻度条：区间由后端下发，本组件不含任何阈值 -->
    <RatioScaleBar
      v-if="item.available && item.bands"
      :bands="item.bands"
      :value="item.value"
    />

    <!-- 不设绝对判定线的指标（净增长 / 支出质量）：说明它只能读方向 -->
    <div v-else-if="item.available && !item.bands" class="ratio-card__noband">
      不设绝对判定线 —— 看趋势方向
    </div>

    <!-- 分子 / 分母：让「这个数怎么来的」有据可查 -->
    <div v-if="legs.length" class="ratio-card__legs">
      <div v-for="leg in legs" :key="leg.label" class="ratio-card__leg">
        <span class="ratio-card__leg-label">{{ leg.label }}</span>
        <span class="ratio-card__leg-value">{{ formatSignedAmount(leg.value) }}</span>
      </div>
    </div>

    <!-- 各指标的补充口径 -->
    <div v-if="notes.length" class="ratio-card__notes">
      <div v-for="note in notes" :key="note.label" class="ratio-card__note">
        <span class="ratio-card__note-label">{{ note.label }}</span>
        <span class="ratio-card__note-value">{{ note.value }}</span>
      </div>
    </div>

    <!-- 净值增长率的残差解读 + 期初对照入口 -->
    <div v-if="item.key === 'net_worth_growth' && item.available && residualNote" class="ratio-card__residual">
      <el-icon><TrendCharts /></el-icon>
      <span>{{ residualNote }}</span>
      <el-button
        v-if="prevYearmon"
        link
        type="primary"
        size="small"
        @click="emit('expand-opening', prevYearmon)"
      >期初 vs 期末</el-button>
    </div>

    <div v-if="item.hint" class="ratio-card__hint">{{ item.hint }}</div>

    <!-- 不可用：说清原因与补救动作，不显示 0 -->
    <div v-if="!item.available" class="ratio-card__reason">
      <el-icon><Warning /></el-icon>
      <span>{{ item.reason }}</span>
    </div>

    <div class="ratio-card__formula">{{ item.formula }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TrendCharts, Warning } from '@element-plus/icons-vue'
import RatioScaleBar from './RatioScaleBar.vue'
import MetricTooltip from '../common/MetricTooltip.vue'
import { formatSignedAmount } from '@/shared/utils/format'
import type { RatioItem, RatioLevel, RatioMeta } from '../../types/wealthTypes'

/**
 * 单项比率卡片。
 *
 * 🔴 本组件**不持有阈值、不做除法**：
 *   档位颜色来自 `item.level`，刻度来自 `item.bands`，值直接来自 `item.value`。
 *   要调档位去 `backend/apps/wealth/constants.py` 的 `RATIO_BANDS`。
 *
 * ⚠️ 金额一律走 `formatSignedAmount`（货币符号在符号位之前，如 `¥-1,234.50`，
 *   且自带隐私掩码）。hint / reason 由后端写死为**不含金额**的定性文案，
 *   故可直接渲染 —— 若哪天后端往里塞了金额，那是后端违反了脱敏纪律。
 */
const props = defineProps<{
  item: RatioItem
  /** 口径元信息；为 null 时不显示 ⓘ（而不是显示一个只有标题的空气泡） */
  meta?: RatioMeta | null
}>()
const emit = defineEmits<{ 'expand-opening': [yearmon: string] }>()

const TAG_TYPE: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  good: 'success',
  warn: 'warning',
  danger: 'danger',
  normal: 'info',
}
const tagType = computed(() => TAG_TYPE[props.item.level ?? ''] ?? 'info')

const legs = computed(() => {
  const out: { label: string; value: number | null }[] = []
  if (props.item.numerator) out.push(props.item.numerator)
  if (props.item.denominator) out.push(props.item.denominator)
  return out
})

function asNumber(v: unknown): number | null {
  return typeof v === 'number' ? v : null
}

const prevYearmon = computed(() => {
  const v = props.item.extra?.prev_yearmon
  return typeof v === 'string' && v ? v : ''
})

const residualNote = computed(() => {
  const residual = asNumber(props.item.extra?.residual)
  if (residual === null) return ''
  if (residual > 0.01) return `残差 ${formatSignedAmount(residual)}：涨得比存下的多（投资收益或漏记收入）`
  if (residual < -0.01) return `残差 ${formatSignedAmount(residual)}：没跟上储蓄（亏损或漏记支出）`
  return '残差 ≈ 0：净资产变化可由储蓄完全解释'
})

/**
 * 补充口径按 key 分别渲染 —— 刻意不做「通用键值遍历」：
 *   `extra` 里既混着金额（净储蓄）又混着比例（填写率 0–1）、
 *   年月串与布尔，通用渲染会把 0.74 印成「¥0.74」。
 *   逐个 key 显式声明，看着啰嗦，但不会印错单位。
 */
const notes = computed(() => {
  const e = props.item.extra ?? {}
  const out: { label: string; value: string }[] = []

  if (props.item.key === 'net_worth_growth') {
    const start = typeof e.period_start === 'string' ? e.period_start : ''
    const end = typeof e.period_end === 'string' ? e.period_end : ''
    if (start || end) {
      out.push({
        label: '储蓄区间',
        value: `${start || '—'} → ${end || '—'}（${e.bound === 'month' ? '按自然月' : '按盘点日'}）`,
      })
    }
    const saving = asNumber(e.net_saving)
    if (saving !== null) out.push({ label: '期间净储蓄', value: formatSignedAmount(saving) })
    if (prevYearmon.value) out.push({ label: '期初', value: prevYearmon.value })
    return out
  }

  if (props.item.key === 'expense_quality') {
    const coverage = asNumber(e.coverage)
    if (coverage !== null) {
      const filled = asNumber(e.filled_rows)
      const total = asNumber(e.total_rows)
      out.push({
        label: '标注填写率',
        value: `${(coverage * 100).toFixed(1)}%`
          + (filled !== null && total !== null ? `（${filled}/${total} 行）` : ''),
      })
    }
    return out
  }

  const recordMonths = asNumber(e.record_months)
  const windowLabel = typeof e.window_label === 'string' ? e.window_label : ''
  if (recordMonths !== null || windowLabel) {
    out.push({
      label: '取数窗口',
      value: `${windowLabel || '—'}`
        + (recordMonths !== null ? ` · ${recordMonths} 个月有记录` : ''),
    })
  }
  const rigidShare = asNumber(e.rigid_share)
  if (rigidShare !== null) {
    out.push({
      label: '刚性占支出',
      value: `${rigidShare}%`.replace('.0%', '%'),
    })
  }
  return out
})
</script>

<style scoped>
.ratio-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 14px 16px;
  /*
   * 🔴 这里**绝不能**再写 `height: 100%`（v3.60.17 修的排版事故）。
   *
   * 本项目全局 `box-sizing` 是 `content-box`（没有 border-box reset，
   * 实测 documentElement / body 均为 content-box）。在 grid item 上
   * **同时**写 `height: 100%` + `content-box` 时：`height: 100%` 只把
   * **内容盒**铺满网格行（轨道 280.8），边框盒还要多算
   * `padding 14×2 + border 1×2 = 30px` ⇒ 卡片边框盒实高 310.8，
   * 向下溢出轨道 30px、**压住下一行 16px**（30 − gap 14）。
   * 下一行卡片后绘制，其**不透明背景正好盖住上一行底部那 30px**
   * —— 用户看到的就是「卡片交叠在一起」。
   *
   * ⚠️ 两个条件**必须同时成立**才出问题，任一单独存在都正常（四组实测）：
   *   A `auto` + `border-box`（当前代码）  overlap = −14px ✔（＝ 正常 gap）
   *   B `100%` + `border-box`             overlap = −14px ✔
   *   C `auto` + `content-box`            overlap = −14px ✔
   *   D `100%` + `content-box`（旧版）     overlap = **+16px** ✘
   * 四组卡内 `scrollHeight − clientHeight` **全为 0** —— 卡内文字从未被
   * 压缩；看着像「hint 与 formula 压在一起」，其实是被下一行卡片盖住。
   *
   * 同行等高由父级 `.ratio-grid` 的 `align-items: stretch` 保证（已显式声明），
   * 不需要卡片自己撑高度。下面的 `border-box` 是防御：万一有人加回
   * `height`，边框盒也只会正好铺满（＝ 上表 B 组）。
   */
  box-sizing: border-box; /* 防御：将来若有人把 height 加回来，边框盒也只会正好铺满 */
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
}
.ratio-card.is-missing { background: var(--el-fill-color-lighter); }
.ratio-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.ratio-card__label { font-size: 13px; color: var(--el-text-color-regular); }
.ratio-card__value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 6px;
}
.ratio-card__value { font-size: 24px; font-weight: 600; }
.ratio-card__value.is-none {
  font-size: 15px;
  font-weight: 500;
  color: var(--el-text-color-placeholder);
}
.ratio-card__value.good { color: #52c41a; }
.ratio-card__value.warn { color: #e6a23c; }
.ratio-card__value.danger { color: #f5222d; }
.ratio-card__value.normal { color: var(--el-text-color-primary); }
.ratio-card__unit { font-size: 12px; color: var(--el-text-color-secondary); }

.ratio-card__legs {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.ratio-card__leg {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  line-height: 1.8;
}
.ratio-card__leg-label { color: var(--el-text-color-secondary); }
.ratio-card__leg-value { color: var(--el-text-color-regular); }

.ratio-card__notes { margin-top: 6px; }
.ratio-card__note {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  line-height: 1.8;
}
.ratio-card__note-label { color: var(--el-text-color-secondary); flex: none; }
.ratio-card__note-value { color: var(--el-text-color-regular); text-align: right; }

.ratio-card__noband {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.ratio-card__residual {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.ratio-card__hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.ratio-card__reason {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-color-warning);
}
.ratio-card__formula {
  margin-top: auto;
  padding-top: 10px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
</style>
