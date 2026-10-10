<template>
  <div class="ratio-scale" v-if="segments.length">
    <div class="ratio-scale__track">
      <div
        v-for="(seg, idx) in segments"
        :key="idx"
        class="ratio-scale__seg"
        :style="{ width: seg.width + '%', background: levelColor(seg.level) }"
        :title="seg.rangeText"
      />
      <!-- 当前值指针：三角形朝下压在轨道上 -->
      <div
        v-if="marker.left !== null"
        class="ratio-scale__marker"
        :style="{ left: marker.left + '%' }"
      >
        <span class="ratio-scale__marker-dot" />
        <span v-if="marker.clamped" class="ratio-scale__marker-over">›</span>
      </div>
    </div>
    <div class="ratio-scale__labels">
      <span
        v-for="(seg, idx) in segments"
        :key="idx"
        class="ratio-scale__label"
        :style="{ width: seg.width + '%' }"
      >{{ seg.width >= 14 ? seg.label : '' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { levelColor } from '../../utils/ratioLevel'
import type { RatioBand } from '../../types/wealthTypes'

/**
 * 判定区间刻度条 —— **档位宽度按区间宽度成比例**画。
 *
 * ⚠️ 刻意不做「线性坐标轴」：末档的上界是 `null`（如「≥ 6 个月」没有上限），
 *   线性轴需要一个最大值，而那个最大值只能靠猜 —— 猜一个 24 个月就等于
 *   悄悄引入了一个不存在的阈值。按区间宽度成比例则不需要任何虚构数字：
 *   末档取「已知区间里最宽的一段」作为名义宽度，仅用于画图。
 *   因此指针在末档内的位置**不表示精确比例**，精确值始终以数字为准
 *   （`clamped` 时指针贴右侧并显 `›`）。
 */
const props = defineProps<{
  bands: RatioBand[] | null
  value: number | null
}>()

const segments = computed(() => {
  const bands = props.bands ?? []
  if (!bands.length) return []
  const widths = bands.map((b) => (b[1] === null ? null : b[1] - b[0]))
  const known = widths.filter((w): w is number => w !== null && w > 0)
  const ref = known.length ? Math.max(...known) : 1
  const resolved = widths.map((w) => w ?? ref)
  const total = resolved.reduce((a, w) => a + w, 0) || 1
  return bands.map((b, i) => ({
    lo: b[0],
    hi: b[1],
    level: b[2],
    label: b[3],
    width: (resolved[i] / total) * 100,
    nominal: resolved[i],
    rangeText: b[1] === null ? `${b[0]}+` : `${b[0]} – ${b[1]}`,
  }))
})

const marker = computed<{ left: number | null; clamped: boolean }>(() => {
  const v = props.value
  if (v === null || v === undefined || !segments.value.length) {
    return { left: null, clamped: false }
  }
  let acc = 0
  for (const seg of segments.value) {
    if (seg.hi === null || v < seg.hi) {
      const frac = Math.min(Math.max((v - seg.lo) / (seg.nominal || 1), 0), 1)
      return {
        left: Math.min(acc + frac * seg.width, 100),
        clamped: seg.hi === null && v > seg.lo + seg.nominal,
      }
    }
    acc += seg.width
  }
  return { left: 100, clamped: false }
})
</script>

<style scoped>
.ratio-scale { margin: 10px 0 4px; }
.ratio-scale__track {
  position: relative;
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: visible;
}
.ratio-scale__seg {
  height: 100%;
  opacity: 0.85;
}
.ratio-scale__seg:first-child { border-radius: 4px 0 0 4px; }
.ratio-scale__seg:last-child { border-radius: 0 4px 4px 0; }
.ratio-scale__marker {
  position: absolute;
  top: -5px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
}
.ratio-scale__marker-dot {
  width: 2px;
  height: 18px;
  border-radius: 1px;
  background: var(--el-text-color-primary);
}
.ratio-scale__marker-over {
  margin-left: 1px;
  font-size: 12px;
  line-height: 1;
  color: var(--el-text-color-primary);
}
.ratio-scale__labels {
  display: flex;
  margin-top: 3px;
}
.ratio-scale__label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  text-align: center;
  overflow: hidden;
  white-space: nowrap;
}
</style>
