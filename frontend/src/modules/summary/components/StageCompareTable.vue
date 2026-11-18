<template>
  <div class="sct">
    <div class="sct__note">{{ data.note }}</div>

    <div v-if="!data.stages.length" class="sct__empty">
      还没有建过人生阶段 —— 在「自我运转 › 阶段」里新建一段，这里就会出现对照
    </div>

    <div v-else class="sct__scroll">
      <div class="sct__grid">
        <div class="sct__head-cell">阶段</div>
        <div v-for="m in data.modules" :key="m.module" class="sct__head-cell is-col">
          <span class="sct__head-top">
            <span class="sct__dot" :style="{ background: m.color }"></span>
            <span class="sct__head-label">{{ m.label }}</span>
          </span>
          <em>{{ m.label_text }}</em>
        </div>
        <div class="sct__head-cell is-col">最短板</div>

        <template v-for="row in data.stages" :key="row.stage_id">
          <div class="sct__stage">
            <div class="sct__stage-name">
              {{ row.name }}
              <!--
                类型标签只说「这一段在不在跑 KPI」，不判好坏：
                `记录` 不是「没做」，是「只记了一笔」（求学期、谋生期）。
              -->
              <el-tag size="small" :type="row.kind === 'run' ? 'primary' : 'info'" effect="plain">
                {{ row.kind === 'run' ? '运转' : '记录' }}
              </el-tag>
            </div>
            <div class="sct__stage-range">{{ rangeText(row) }}</div>
          </div>

          <div v-for="c in cells(row)" :key="c.meta.module" class="sct__cell" :title="cellTitle(c)">
            <template v-if="c.cov && c.cov.pct != null">
              <span class="sct__pct">{{ c.cov.pct }}%</span>
              <span class="sct__frac">
                {{ c.cov.covered }}/{{ c.cov.periods }} {{ c.cov.period_word }}
              </span>
              <!-- 分母被裁到「系统可观测起点」：不标出来，读者会以为
                   这一段里每天都可记录，而其实是系统那时还不存在 -->
              <span v-if="c.cov.clipped" class="sct__flag">
                {{ cutText(c.cov.visible_from) }}
              </span>
            </template>
            <template v-else>
              <span class="sct__pct is-na">—</span>
              <span class="sct__frac">{{ reasonText(c.cov) }}</span>
            </template>
          </div>

          <div class="sct__cell sct__weakest">
            <template v-if="row.weakest">
              <span class="sct__pct">{{ row.weakest.label }}</span>
              <span class="sct__frac">{{ row.weakest.coverage_pct }}%</span>
            </template>
            <template v-else>
              <span class="sct__pct is-na">—</span>
              <span class="sct__frac">{{ weakestNaText(row) }}</span>
            </template>
          </div>
        </template>
      </div>
    </div>

    <div class="sct__foot">
      覆盖率 = 该阶段内有记录的期数 ÷ 该有的期数。两个阶段可以比覆盖率，
      但<strong>不比强度</strong> —— 强度是绝对量（步/天 vs 元/月），
      并排会被读成「哪段人生过得好」。
      「早于数据」指那段日子在系统开始记录之前，<strong>不是你没做</strong>。
    </div>
  </div>
</template>

<script setup lang="ts">
import type { StageCompareData, StageCompareRow, StageCoverage } from '../types/summaryTypes'

const props = defineProps<{ data: StageCompareData }>()

interface Cell {
  meta: StageCompareData['modules'][number]
  cov: StageCoverage | null
}

/**
 * 一行 × 七维的取值表
 *
 * 🔴 在脚本里先算好再交给模板，模板里不再出现 `row.coverage[mod]` 这种
 *    下标取值 —— 它在模板里是「可能 undefined」，要么全篇 `?.` + `!`，
 *    要么像这样一次定型。顺便把「没有这个维度」与「维度算不出来」分开。
 */
function cells(row: StageCompareRow): Cell[] {
  return props.data.modules.map((meta) => ({ meta, cov: row.coverage[meta.module] ?? null }))
}

/**
 * 阶段区间的一句话
 *
 * 🔴 阶段还没结束时不能说「到 2029-09-30，共 14 天」——
 *    `end` 是计划终点、`days` 只算到今天，两者放在一句话里会自相矛盾。
 */
function rangeText(row: StageCompareRow): string {
  const start = row.start
  if (row.in_future) return `${start} 起（还没开始）`
  if (!row.end) return `${start} 起 · 已 ${row.days} 天`
  const eff = row.end_effective ?? row.end
  if (eff < row.end) return `${start} ~ ${eff}（计划到 ${row.end}）· 已 ${row.days} 天`
  return `${start} ~ ${row.end} · ${row.days} 天`
}

/** 算不出来的三种原因（都不是 0%）—— 格子里的短文案只在这里拼 */
const REASON_TEXT: Record<string, string> = {
  no_records: '还没有记录',
  before_data: '早于数据',
  no_complete_period: '不足一月',
}

function reasonText(cov?: StageCoverage | null): string {
  if (!cov) return '—'
  return REASON_TEXT[cov.reason ?? ''] ?? '—'
}

/**
 * 格子的悬停说明
 *
 * 格子里只能放 4–6 个字，而「早于数据」「不足一月」都需要一句人话解释，
 * 否则读者会以为是自己没记。三种原因对应三件不同的事，分开说。
 */
function cellTitle(c: Cell): string {
  const { meta, cov } = c
  if (!cov) return `${meta.label}：这个维度还没有数据`
  if (cov.pct == null) {
    switch (cov.reason) {
      case 'no_records':
        return `${meta.label}：这个维度从来没有任何记录（不是这一段没记）`
      case 'before_data':
        return `${meta.label}：这段日子早于系统有记录的时候 —— 那时不是「没做」，是还没有这个系统`
      case 'no_complete_period':
        return `${meta.label}：这一${meta.period_word}还没过完，按月记账的维度要等本期结束才算`
      default:
        return `${meta.label}：算不出来`
    }
  }
  const cut = cov.clipped && cov.visible_from ? `（从 ${cov.visible_from} 起可观测）` : ''
  return `${meta.label}：${cov.covered}/${cov.periods} ${cov.period_word}有记录${cut}`
}

/** 分母被裁：标出「从哪天起才可观测」 */
function cutText(visibleFrom: string | null): string {
  return visibleFrom ? `从 ${visibleFrom}` : '部分可观测'
}

/**
 * 最短板为空的原因
 *
 * 🔴 不能只显示 `—`：用户会以为数据坏了。三种情形分开说 ——
 *    「还没开始」「可比的维度不够」「算不出来」是三件不同的事。
 */
function weakestNaText(row: StageCompareRow): string {
  if (row.in_future) return '还没开始'
  const n = row.comparable_modules ?? 0
  if (n < 2) return n === 0 ? '没有可比的维度' : '只有 1 个维度可比'
  return '—'
}
</script>

<style scoped>
.sct {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sct__note {
  font-size: 11px;
  line-height: 1.6;
  color: var(--el-text-color-placeholder);
}
.sct__empty {
  padding: 24px 0;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}

/*
  七列 + 阶段列 + 最短板列在窄屏一定放不下。
  这里选**横向滚动**而不是缩小字号：缩到 9px 的表格等于没有表。
  `min-width` 保证每列仍有可读宽度。
*/
.sct__scroll {
  overflow-x: auto;
}
.sct__grid {
  display: grid;
  grid-template-columns: 176px repeat(7, minmax(78px, 1fr)) 96px;
  min-width: 860px;
  align-items: stretch;
}

.sct__head-cell {
  padding: 0 6px 6px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  border-bottom: 1px solid var(--el-border-color-lighter);
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.sct__head-cell.is-col {
  align-items: flex-end;
  gap: 1px;
}
.sct__head-top {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.sct__head-label {
  color: var(--el-text-color-regular);
  font-size: 12px;
  white-space: nowrap;
}
.sct__head-cell em {
  font-style: normal;
  font-size: 10px;
  color: var(--el-text-color-placeholder);
}
.sct__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  align-self: center;
}

.sct__stage {
  padding: 9px 6px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
  min-width: 0;
}
.sct__stage-name {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}
.sct__stage-range {
  margin-top: 2px;
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  font-variant-numeric: tabular-nums;
}

.sct__cell {
  padding: 9px 6px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 1px;
  font-variant-numeric: tabular-nums;
}
.sct__pct {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}
.sct__pct.is-na {
  font-weight: 400;
  color: var(--el-text-color-placeholder);
}
.sct__frac {
  font-size: 10px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.sct__flag {
  font-size: 9px;
  color: var(--el-color-warning);
  white-space: nowrap;
}
.sct__weakest {
  border-left: 1px solid var(--el-border-color-lighter);
}

.sct__foot {
  font-size: 11px;
  line-height: 1.7;
  color: var(--el-text-color-placeholder);
}
.sct__foot strong {
  font-weight: 600;
  color: var(--el-text-color-secondary);
}
</style>
