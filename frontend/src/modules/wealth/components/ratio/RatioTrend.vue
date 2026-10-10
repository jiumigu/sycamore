<template>
  <div class="ratio-trend">
    <div class="ratio-trend__head">
      <div>
        <span class="ratio-trend__title">比率趋势</span>
        <span class="ratio-trend__sub">
          值全部由后端算好 —— 前端不做除法，也不判档位
        </span>
      </div>
      <el-select
        :model-value="months"
        size="small"
        style="width: 110px"
        @update:model-value="(v: number) => emit('update:months', v)"
      >
        <el-option v-for="opt in MONTH_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
    </div>

    <div v-if="!trend || !sparks.length" class="ratio-trend__empty">暂无趋势数据</div>
    <div v-else class="ratio-trend__grid">
      <div v-for="s in sparks" :key="s.key" class="ratio-trend__item">
        <div class="ratio-trend__item-head">
          <span class="ratio-trend__item-label">{{ s.label }}</span>
          <span v-if="s.last" class="ratio-trend__item-value" :class="s.last.level ?? 'normal'">
            {{ s.last.available ? `${s.last.value}${s.unit}` : '—' }}
            <template v-if="s.last.level_label">· {{ s.last.level_label }}</template>
          </span>
        </div>
        <svg class="ratio-trend__svg" viewBox="0 0 240 56" preserveAspectRatio="none">
          <!-- 零线：跨 0 的指标（净值增长 / 支出质量）才有意义 -->
          <line
            v-if="s.zeroY !== null"
            x1="0" :y1="s.zeroY" x2="240" :y2="s.zeroY"
            stroke="var(--el-border-color)" stroke-dasharray="3 3" stroke-width="1"
          />
          <!-- 断点即「这个月算不出来」—— 不许用 0 连成一条平线 -->
          <path
            v-for="(d, i) in s.paths"
            :key="i"
            :d="d"
            fill="none"
            stroke="var(--el-color-primary)"
            stroke-width="1.5"
            vector-effect="non-scaling-stroke"
          />
          <circle
            v-for="(dot, i) in s.dots"
            :key="'d' + i"
            :cx="dot.x" :cy="dot.y" r="2.5"
            :fill="dot.color"
          />
        </svg>
        <div class="ratio-trend__axis">
          <span>{{ s.firstYm }}</span>
          <span>{{ s.lastYm }}</span>
        </div>
      </div>
    </div>

    <div v-if="trend && trend.excluded.length" class="ratio-trend__excluded">
      <el-icon><InfoFilled /></el-icon>
      <span>
        以下指标不进趋势：
        <template v-for="(ex, i) in trend.excluded" :key="ex.key">
          {{ ex.label }}（{{ ex.reason }}）<span v-if="i < trend.excluded.length - 1">；</span>
        </template>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import { levelColor } from '../../utils/ratioLevel'
import type { RatioTrend, RatioTrendPoint } from '../../types/wealthTypes'

/**
 * 比率趋势 —— 每条线一个 sparkline。
 *
 * ⚠️ 三条口径，违反即回归：
 *   ① **缺月必须画成断点**。后端用 `available=false` 表达「这个月算不出来」，
 *      若前端把它当 0 补点，会画出一条「净资产这个月没变化」的平线 ——
 *      与「本月没盘点」是完全相反的两个结论。
 *   ② 比率是百分比/月数，**不是金额**，故不做金额掩码
 *      （与 `goals.progress_percentage` 同一条判据：百分比非隐私项）。
 *      掩了趋势线就失去全部意义。
 *   ③ 档位颜色只看 `point.level`；本组件没有任何阈值。
 *
 * 用 SVG 而非 ECharts：sparkline 不需要交互，也不涉及 ECharts 的
 * `setOption` merge / resize 重算那两个历史坑（见 §14）。
 */
const props = defineProps<{
  trend: RatioTrend | null
  months: number
  items: { key: string; label: string; unit: string }[]
}>()
const emit = defineEmits<{ 'update:months': [months: number] }>()

const MONTH_OPTIONS = [
  { value: 6, label: '近 6 个月' },
  { value: 12, label: '近 12 个月' },
  { value: 24, label: '近 24 个月' },
  { value: 36, label: '近 36 个月' },
]

const W = 240
const H = 56
const PAD = 6

const sparks = computed(() => {
  const trend = props.trend
  if (!trend) return []
  const series = trend.series ?? {}
  // 顺序以总览给的 items 为准（后端 RATIO_ORDER），再补上 items 里没有的键，
  // 避免「趋势区少了一条线而没人发现」。
  const ordered: { key: string; label: string; unit: string }[] = []
  const seen = new Set<string>()
  for (const it of props.items) {
    if (series[it.key]) { ordered.push(it); seen.add(it.key) }
  }
  for (const key of Object.keys(series)) {
    if (!seen.has(key)) ordered.push({ key, label: key, unit: '' })
  }

  return ordered.map((it) => {
    const points = series[it.key] ?? []
    const nums = points
      .filter((p) => p.available && p.value !== null)
      .map((p) => p.value as number)
    if (!nums.length) {
      return {
        ...it, paths: [], dots: [], zeroY: null,
        last: null, firstYm: '', lastYm: '',
      }
    }
    let lo = Math.min(...nums)
    let hi = Math.max(...nums)
    if (hi - lo < 1e-9) { lo -= 1; hi += 1 }
    const span = hi - lo
    const yOf = (v: number) => PAD + (1 - (v - lo) / span) * (H - PAD * 2)
    const xOf = (i: number) => (points.length <= 1 ? W / 2 : (i / (points.length - 1)) * W)

    const paths: string[] = []
    const dots: { x: number; y: number; color: string }[] = []
    let segment: string[] = []
    points.forEach((p: RatioTrendPoint, i: number) => {
      const ok = p.available && p.value !== null
      if (!ok) {
        if (segment.length) { paths.push(segment.join(' ')); segment = [] }
        return
      }
      const x = xOf(i)
      const y = yOf(p.value as number)
      segment.push(`${segment.length ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`)
      dots.push({ x, y, color: levelColor(p.level) })
    })
    if (segment.length) paths.push(segment.join(' '))

    const last = [...points].reverse().find((p) => p.available) ?? points[points.length - 1] ?? null
    return {
      ...it,
      paths,
      dots,
      zeroY: lo <= 0 && hi >= 0 ? yOf(0) : null,
      last: last ?? null,
      firstYm: points[0]?.ym ?? '',
      lastYm: points[points.length - 1]?.ym ?? '',
    }
  })
})
</script>

<style scoped>
.ratio-trend__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.ratio-trend__title { font-size: 15px; font-weight: 600; }
.ratio-trend__sub {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.ratio-trend__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}
.ratio-trend__item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px 12px;
}
.ratio-trend__item-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
}
.ratio-trend__item-label { color: var(--el-text-color-regular); }
.ratio-trend__item-value { font-weight: 600; }
.ratio-trend__item-value.good { color: #52c41a; }
.ratio-trend__item-value.warn { color: #e6a23c; }
.ratio-trend__item-value.danger { color: #f5222d; }
.ratio-trend__item-value.normal { color: var(--el-text-color-primary); }
.ratio-trend__svg {
  width: 100%;
  height: 56px;
  margin-top: 6px;
  overflow: visible;
}
.ratio-trend__axis {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.ratio-trend__empty {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}
.ratio-trend__excluded {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 14px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
