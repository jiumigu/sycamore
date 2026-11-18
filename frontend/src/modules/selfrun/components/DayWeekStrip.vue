<!--
  7 格色带 · **唯一实现**（v3.64.77）

  它出现在两处：今日页底部、本周状态页底部。两处都画同一件事
  ——「这几天各走了哪一格、成没成」——所以只允许一份。

  🔴 图例（四格的词与配色）由**后端**给（`legend`），组件不内置任何词表：
     今日页传 `payload.quadrants`，本周状态页传接口的 `legend`；
     组件自己写一份就等于第二套口径，改一处漏一处、且不报错。

  🔴 空格子必须画成「一个空框」，不能留白：
     「这周都没定档」与「这一块压根没渲染」在留白下长得一样。
-->
<template>
  <div class="dws">
    <div class="dws-band">
      <span
        v-for="d in days" :key="d.date"
        class="dws-cell"
        :class="{
          'has-mark': !!d.quadrant,
          'is-today': !!today && d.date === today,
          'is-unsettled': d.quadrant && !d.outcome && d.quadrant !== 'rest',
          'is-missed': d.outcome === 'missed',
        }"
        :style="d.quadrant ? { '--c': colorOf(d.quadrant) } : undefined"
        :title="titleOf(d)"
      ></span>
    </div>
    <div class="dws-text">
      {{ weekText }}
      <span v-if="note" class="dws-note">{{ note }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type {
  DayLegendItem, DayQuadrant, DayWeekCell, DayWeekSummary,
} from '../types/selfrunTypes'

const props = withDefaults(defineProps<{
  days: DayWeekCell[]
  summary: DayWeekSummary | null
  legend: DayLegendItem[]
  /** 高亮哪一天。历史周不传 —— 那一段里没有「今天」。 */
  today?: string
  /** 右侧那句提醒。默认说清「这不是考核」；仪表盘小卡里可以传给 `''` 收掉。 */
  note?: string
}>(), { today: '', note: '不参与判定' })

function labelOf(q: DayQuadrant): string {
  return props.legend.find((x) => x.quadrant === q)?.label ?? ''
}

function colorOf(q: DayQuadrant): string {
  return props.legend.find((x) => x.quadrant === q)?.color ?? 'var(--el-border-color)'
}

/** 16px 的方块放不下三种状态，所以全放悬浮说明里。
 *
 *  ⚠️ 风干**不说「没结算」**：它本来就不结算，说了就等于提示你去补一件
 *     系统明确不要求的事。
 */
function titleOf(d: DayWeekCell): string {
  if (!d.quadrant) return `${d.date} 没定档`
  const parts = [d.date, labelOf(d.quadrant)]
  if (d.quadrant !== 'rest') {
    parts.push(d.outcome === 'done' ? '成了' : d.outcome === 'missed' ? '没成' : '没结算')
  }
  if (d.is_backfilled) parts.push('补记')
  return parts.join(' · ')
}

/** ⚠️ 补记的日子在色带上与「当天记的」长得一样，但复盘时不是一回事 ——
 *  这一句只数天数，不评价。 */
const weekText = computed(() => {
  const s = props.summary
  if (!s) return ''
  if (!s.marked_days) return '这周还没定过档'
  let text = `这周定过 ${s.marked_days} 天，结了 ${s.settled_days} 天`
  if (s.missed_days) text += `，其中 ${s.missed_days} 天没成`
  if (s.unsettled_days) text += `；还有 ${s.unsettled_days} 天没结算`
  return text
})
</script>

<style scoped>
.dws {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.dws-band { display: flex; gap: 4px; }
/* 空格子要看得出来是个格子：浅底 + 一道细边。只填底色时它几乎隐形，
   于是「这周都没定档」和「这一周压根没画」看起来一样。
   ⚠️ 边框用 `--el-border-color`（不是 `-lighter`）：后者在白色卡片上
      几乎与背景同色，七个空格会糊成一片。 */
.dws-cell {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  background: var(--el-fill-color);
  border: 1px solid var(--el-border-color);
}
/* 定了档：整格上色，边框让位给颜色 */
.dws-cell.has-mark { background: var(--c); border-color: transparent; }
/* 今天：外圈加一道边，不是换颜色 —— 颜色已经是「哪一格」了 */
.dws-cell.is-today { box-shadow: 0 0 0 2px var(--el-color-primary-light-5); }
/* 定了没结算：半透明 + 虚边。它**不是**「没成」 */
.dws-cell.is-unsettled {
  opacity: 0.55;
  border-style: dashed;
  border-color: var(--el-text-color-placeholder);
}
/* 没成：一道斜线。颜色仍保留，因为你还是走了那一格 */
.dws-cell.is-missed {
  background-color: var(--c);
  background-image: linear-gradient(
    135deg, transparent 42%, var(--el-bg-color) 42%, var(--el-bg-color) 58%, transparent 58%
  );
}
.dws-text { font-size: 12px; color: var(--el-text-color-secondary); }
.dws-note { margin-left: 6px; color: var(--el-text-color-placeholder); }
</style>
