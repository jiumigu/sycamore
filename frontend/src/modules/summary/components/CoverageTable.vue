<template>
  <div class="cov">
    <div class="cov__head">
      <span class="cov__head-label">维度</span>
      <span class="cov__head-cov">覆盖率 · 有记录 / 该有的</span>
      <span class="cov__head-int">强度（有记录时）</span>
      <span class="cov__head-total">总量</span>
    </div>

    <div
      v-for="m in modules"
      :key="m.module"
      class="cov__row"
      :class="{ 'is-weakest': m.module === weakestModule }"
      @click="$emit('view-module', m.module)"
    >
      <span class="cov__name">
        <span class="cov__dot" :style="{ background: m.color }"></span>
        <span class="cov__label">{{ m.label }}</span>
        <el-tag v-if="m.module === weakestModule" size="small" type="warning" class="cov__tag">
          最短板
        </el-tag>
      </span>

      <span class="cov__cov">
        <!-- 算不出来（该年还没开始）⇒ 空条 + —，不给 0% -->
        <span class="cov__bar">
          <span
            v-if="m.coverage.pct !== null"
            class="cov__bar-fill"
            :style="{ width: Math.min(m.coverage.pct, 100) + '%', background: m.color }"
          ></span>
        </span>
        <span class="cov__pct">
          {{ m.coverage.pct === null ? '—' : m.coverage.pct + '%' }}
        </span>
        <span class="cov__frac">
          {{ m.coverage.covered }}/{{ m.coverage.periods }} {{ m.coverage.period_word }}
        </span>
      </span>

      <span class="cov__int">
        <template v-if="m.coverage.intensity !== null">
          {{ number(m.coverage.intensity, m.module) }}
          <span class="cov__unit">{{ m.coverage.intensity_unit }}</span>
        </template>
        <span v-else class="cov__muted">—</span>
      </span>

      <span class="cov__total">
        <span class="cov__total-main">
          {{ totalText(m) }}
          <span v-if="m.zero_reason" class="cov__flag">{{ reasonText(m.zero_reason) }}</span>
        </span>
        <!--
          「对目标」挂在总量下面，因为它和总量是同一个事实的两面：
          净额多少、离目标多远。分两列会让人以为它们是两个独立指标。
          🔴 负数照实显示（净流出年份是负达成率，不是 0%）——
             写成 0% 就看不出「亏了多少」，那是之前的问题。
        -->
        <span
          v-if="m.achievement_pct !== null"
          class="cov__ach"
          :class="{ 'is-neg': m.achievement_pct < 0 }"
        >
          对目标 {{ m.achievement_pct }}%
          <em v-if="m.achievement_target !== null && m.axis_max !== null">
            （{{ targetText(m) }}）
          </em>
        </span>
      </span>
    </div>

    <div class="cov__foot">
      覆盖率回答「有没有断」，强度回答「记的时候做了多少」——
      两个数不能相加，也不该合成一个分。
    </div>
  </div>
</template>

<script setup lang="ts">
import { formatSignedAmount } from '@/shared/utils/format'
import { zeroReasonText } from '../constants/zeroReason'
import type { ModulePoint } from '../types/summaryTypes'

defineProps<{
  modules: ModulePoint[]
  weakestModule?: string | null
}>()

defineEmits<{ 'view-module': [module: string] }>()

/**
 * 强度：金额走唯一金额入口，其它按本地千分位。
 * 🔴 不在这里做「多少算好」的判断 —— 条长短本身就是信息，
 *    阈值一旦写进 UI 就成了第二把尺子。
 */
function number(value: number, module: string): string {
  if (module === 'wealth') return formatSignedAmount(value, 2)
  return value.toLocaleString('zh-CN', { maximumFractionDigits: 1 })
}

/** 总量：万元量级统一折成「元」再走金额入口，避免出现「-1.69 万元」这种符号在单位外面的写法 */
function totalText(m: ModulePoint): string {
  if (m.display_value === null) return '—'
  if (m.unit === '万元') return formatSignedAmount(m.raw_value, 2)
  return `${m.display_value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })} ${m.unit}`
}

/**
 * 目标换算回物理量后的一句话（财富：¥50,000；健康：50 万步；阅读：20 本）。
 * 后端给的是「点」，1 点 = divisor 个物理单位 —— 这里只做单位还原，不改数值。
 */
function targetText(m: ModulePoint): string {
  const t = m.achievement_target
  if (t === null) return ''
  if (m.unit === '万元') return formatSignedAmount(t, 0)
  if (m.unit === '万步') return `${(t / 10000).toLocaleString('zh-CN')} 万步`
  if (m.unit === '万字') return `${(t / 10000).toLocaleString('zh-CN')} 万字`
  return `${t.toLocaleString('zh-CN', { maximumFractionDigits: 0 })} ${m.unit}`
}

function reasonText(reason?: string | null): string {
  return zeroReasonText(reason ?? null)
}
</script>

<style scoped>
.cov {
  display: flex;
  flex-direction: column;
  /* 容器查询的锚：窄屏时要按**卡片实际宽度**收缩，不能按视口 —— 
     页面有侧边栏，视口 820 时卡片内容只有 ~480。 */
  container-type: inline-size;
}
.cov__head,
.cov__row {
  display: grid;
  grid-template-columns: 128px minmax(0, 1fr) 132px 118px;
  align-items: center;
  gap: 10px;
}
.cov__head {
  padding: 0 6px 6px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.cov__head-cov { text-align: left; }
.cov__head-int,
.cov__head-total { text-align: right; }

.cov__row {
  padding: 9px 6px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
  cursor: pointer;
  border-radius: 4px;
}
.cov__row:last-of-type { border-bottom: none; }
.cov__row:hover { background: var(--el-fill-color-light); }
.cov__row.is-weakest { background: var(--el-color-warning-light-9); }

.cov__name {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.cov__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.cov__label {
  font-size: 13px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}
.cov__tag { transform: scale(0.86); }

.cov__cov {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.cov__bar {
  flex: 1;
  min-width: 0;
  height: 8px;
  border-radius: 4px;
  background: var(--el-fill-color);
  overflow: hidden;
}
.cov__bar-fill {
  display: block;
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}
.cov__pct {
  width: 46px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}
.cov__frac {
  width: 84px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.cov__int {
  text-align: right;
  font-size: 13px;
  color: var(--el-text-color-regular);
  font-variant-numeric: tabular-nums;
}
.cov__unit {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.cov__total {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
  text-align: right;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}
.cov__total-main {
  white-space: nowrap;
}
/* 达成率：与总量同一个格子的第二行，因为它们是同一个事实的两面 */
.cov__ach {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  white-space: nowrap;
}
.cov__ach em {
  font-style: normal;
  opacity: 0.8;
}
.cov__ach.is-neg {
  color: var(--el-color-danger);
  font-weight: 600;
}
.cov__muted { color: var(--el-text-color-placeholder); }
.cov__flag {
  display: inline-block;
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 3px;
  background: var(--el-fill-color);
  font-size: 10px;
}
/*
  窄卡片：先丢「42/292 天」这一列（它是提示，不是主信息），
  再收窄固定列。绝不靠缩小字号硬塞 —— 那会把表格变成一堵墙。
*/
@container (max-width: 620px) {
  .cov__head,
  .cov__row {
    grid-template-columns: 92px minmax(0, 1fr) 92px 100px;
    gap: 8px;
  }
  .cov__frac { display: none; }
  /* 最短板标签让位：该行本来就有底色，雷达卡里还有一句话点名 */
  .cov__tag { display: none; }
  .cov__pct { width: 40px; font-size: 12px; }
  .cov__label { font-size: 12px; }
  .cov__ach { font-size: 9px; }
}
@container (max-width: 460px) {
  .cov__head,
  .cov__row {
    grid-template-columns: 78px minmax(0, 1fr) 82px;
    gap: 6px;
  }
  .cov__head-total,
  .cov__total { display: none; }
}

/* 表脚注：这里的口径说明是「读一次就够」的，放在表末尾最省位置 */
.cov__foot {
  padding: 10px 6px 0;
  font-size: 11px;
  line-height: 1.6;
  color: var(--el-text-color-placeholder);
}

</style>
