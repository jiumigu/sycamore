<template>
  <div class="pct">
    <div class="pct__lead">
      按<strong>月</strong>对齐两组量，看它们是否同涨同跌。
      系数是秩相关（<span class="pct__mono">ρ</span>），不是因果 ——
      两个月同时变大，不说明谁推动了谁。
    </div>

    <div v-if="!data.pairs.length" class="pct__empty">
      还没有可配对的量
    </div>

    <el-table v-else :data="data.pairs" size="small" class="pct__table" :show-header="true">
      <el-table-column label="配对" min-width="200">
        <template #default="{ row }">
          <div class="pct__pair">
            <span class="pct__pair-name">{{ row.left_label }} ↔ {{ row.right_label }}</span>
            <span class="pct__pair-why">{{ row.why }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="月数" width="72" align="right">
        <template #default="{ row }">
          <span class="pct__num">{{ row.n }}</span>
        </template>
      </el-table-column>

      <el-table-column label="ρ" width="72" align="right">
        <template #default="{ row }">
          <!--
            🔴 样本不足时系数照给，但整行灰掉 —— 一个 n=6 的 0.8
               比 n=80 的 0.3 更容易被当真，必须让「少」看得出来。
          -->
          <span class="pct__num" :class="{ 'is-weak': row.reason === 'not_enough' }">
            {{ rhoText(row) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="结论" min-width="168">
        <template #default="{ row }">
          <div class="pct__verdict">
            <el-tag
              v-if="row.level"
              size="small"
              :type="TAG_TYPE[row.level] ?? 'info'"
              effect="plain"
            >{{ row.level_label }}</el-tag>
            <span v-else class="pct__na">{{ naText(row) }}</span>
            <span v-if="row.robust === false" class="pct__flag">去掉极端月后不成立</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="形状" width="86" align="center">
        <template #default="{ row }">
          <!--
            迷你散点：横轴 = 左量、纵轴 = 右量（各自按自身最大最小归一）。
            它不承担读数，只回答「这点云像不像一条斜线」——
            所以不画坐标轴、不标刻度。
          -->
          <svg v-if="row.points.length >= 3" class="pct__spark" viewBox="0 0 64 28" aria-hidden="true">
            <circle
              v-for="(p, i) in spark(row)"
              :key="i"
              :cx="p.cx"
              :cy="p.cy"
              r="1.5"
              :fill="SPARK_COLOR[row.level ?? ''] ?? '#c0c4cc'"
            />
          </svg>
          <span v-else class="pct__na">—</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="pct__foot">
      <div>
        判档看 <span class="pct__mono">|ρ|</span>：≥ {{ bandText.strong }} 明显、
        {{ bandText.weak }}–{{ bandText.strong }} 弱、&lt; {{ bandText.weak }} 无明显关系；
        共同月份少于 <strong>{{ data.min_n }}</strong> 个月的只给系数、不下结论。
      </div>
      <div>
        「去掉极端月后不成立」= 把左量最高和最低的各一个月剔掉，相关性就跌破
        {{ data.robust_min }} —— 说明这个结论是被一两个月份撑起来的。
      </div>
      <div v-if="coverageText">
        可配对的数据：{{ coverageText }}（{{ data.coverage.years[0] }}–{{ data.coverage.years[1] }}）。
        <strong>没有共同月份就不进表</strong> —— 「那月没记」不等于「那月是 0」。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PairCheckData, PairCheckRow } from '../types/summaryTypes'

const props = defineProps<{ data: PairCheckData }>()

const TAG_TYPE: Record<string, 'primary' | 'warning' | 'info'> = {
  strong: 'primary',
  weak: 'warning',
  none: 'info',
}

const SPARK_COLOR: Record<string, string> = {
  strong: '#6366F1',
  weak: '#F59E0B',
  none: '#C0C4CC',
}

const METRIC_LABEL: Record<string, string> = {
  times: '投入时间',
  expense: '支出',
  income: '收入',
  sugar_level: '快乐程度',
  steps: '步数',
}

/** 阈值从后端来，前端不写死 */
const bandText = computed(() => {
  const find = (key: string) => props.data.bands.find((b) => b.key === key)?.lower ?? '—'
  return { strong: find('strong'), weak: find('weak') }
})

const coverageText = computed(() => {
  const m = props.data.coverage?.metrics ?? {}
  return Object.entries(m)
    .map(([k, n]) => `${METRIC_LABEL[k] ?? k} ${n} 个月`)
    .join('、')
})

/** 系数文案：`null` 不显示 0 —— 那是「算不出」，不是「没关系」 */
function rhoText(row: PairCheckRow): string {
  if (row.reason === 'constant') return '—'
  if (row.spearman == null) return '—'
  return row.spearman.toFixed(3)
}

/** 不判档时的原因（样本不足 ≠ 没关系，两件事） */
function naText(row: PairCheckRow): string {
  switch (row.reason) {
    case 'no_data':
      return '没有共同月份'
    case 'not_enough':
      return `样本不足（${row.n} < ${props.data.min_n}）`
    case 'constant':
      return '有一侧常年不变'
    default:
      return '—'
  }
}

/**
 * 散点归一
 *
 * 横竖各按自身 min/max 拉伸到 4–60 / 24–4（y 轴翻转）。
 * 只关心形状，不关心量级 —— 两个量的单位不同，同一刻度没有意义。
 */
function spark(row: PairCheckRow): { cx: number; cy: number }[] {
  const xs = row.points.map((p) => p.x)
  const ys = row.points.map((p) => p.y)
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)]
  const [y0, y1] = [Math.min(...ys), Math.max(...ys)]
  const spanX = x1 - x0
  const spanY = y1 - y0
  return row.points.map((p) => ({
    // 一侧完全不变时（span=0）落在中线，不除零
    cx: spanX ? 4 + ((p.x - x0) / spanX) * 56 : 32,
    cy: spanY ? 24 - ((p.y - y0) / spanY) * 20 : 14,
  }))
}
</script>

<style scoped>
.pct {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pct__lead {
  font-size: 11px;
  line-height: 1.7;
  color: var(--el-text-color-placeholder);
}
.pct__lead strong {
  color: var(--el-text-color-secondary);
  font-weight: 600;
}
.pct__mono {
  font-family: var(--el-font-family-mono, ui-monospace, monospace);
  color: var(--el-text-color-regular);
}
.pct__empty {
  padding: 24px 0;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}

.pct__table :deep(.el-table__cell) {
  padding: 6px 0;
}
.pct__pair {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.pct__pair-name {
  font-size: 13px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}
.pct__pair-why {
  font-size: 10px;
  line-height: 1.5;
  color: var(--el-text-color-placeholder);
}
.pct__num {
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}
/* 样本不足：数字照给，但压低 —— 别让 n=6 的系数看起来同样可信 */
.pct__num.is-weak {
  font-weight: 400;
  color: var(--el-text-color-placeholder);
}
.pct__verdict {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}
.pct__na {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.pct__flag {
  font-size: 10px;
  color: var(--el-color-warning);
  line-height: 1.4;
}
.pct__spark {
  width: 64px;
  height: 28px;
  display: block;
}
.pct__foot {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
  line-height: 1.7;
  color: var(--el-text-color-placeholder);
}
.pct__foot strong {
  font-weight: 600;
  color: var(--el-text-color-secondary);
}
</style>
