<!-- 自我运转 · 配置变更留痕（「制定配置」的页内子页面）
     ────────────────────────────────────────────────────────────
     为什么单独给它一页：它跟「本阶段 KPI」是**两种读法** ——
     那边回答「现在是什么样」（状态），这边回答「什么时候变成了这样」（时间轴）。
     并排摆在一屏上时，改完 KPI 要往下滚很远才看得到刚留下的那一行，
     等于「留了痕但看不见」。

     🔴 每一行必须**翻成人话**：`{"goal_value":"12.00"}` 这种 JSON 摆在那里
        等于没有留痕 —— 「改了」但看不出改成什么。所以下面逐字翻译。
-->
<template>
  <el-card shadow="never" class="cl-card">
    <template #header>
      <div class="cl-head">
        <span class="cl-title">配置变更留痕</span>
        <span class="cl-hint">
          每一次改动都留一行 —— 包括「哪一期换过尺子」。
          这里只读，不提供撤销：<b>配置的改动靠「再改回去」纠正</b>，不像流水那样冲销。
        </span>
        <span class="cl-spacer" />
        <span class="cl-count">{{ store.logs.length }} 条</span>
      </div>
    </template>

    <el-table :data="store.logs" size="small" empty-text="还没有变更记录">
      <el-table-column prop="at" label="时间" width="150">
        <template #default="{ row }">{{ (row.at ?? '').slice(0, 16) }}</template>
      </el-table-column>
      <el-table-column prop="metric_name" label="KPI" min-width="110" />
      <el-table-column prop="action_display" label="动作" width="96" />
      <el-table-column label="变更" min-width="220">
        <template #default="{ row }">
          <span class="cl-mono">{{ changeText(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="原因" min-width="160">
        <template #default="{ row }">
          {{ row.reason_display || (row.reason_note ? '' : '—') }}
          <span v-if="row.reason_note" class="cl-hint">{{ row.reason_note }}</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="cl-foot">
      会出现在这里的动作：按模板建 KPI · 改目标 / 底线 / 名称 / 单位 · 改取数口径 ·
      退役 · 恢复 · <b>按期设定或取消某一期的目标</b>（plan_changed）。
      归档那一刻冻住的结论<b>不在</b>这里 —— 它在「历史复盘」与「阶段总结」。
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { useSelfRunStore } from '../stores/selfrunStore'
import type { SelfRunMetricLog } from '../types/selfrunTypes'

const store = useSelfRunStore()

/**
 * 这一行变更怎么写给人看。
 *
 * 🔴 口径值必须**渲染成人能读的**：`{"goal_value":"12.00"}` 这种 JSON 摆在那里，
 *    等于没有留痕（「改了」但看不出改成什么）。所以这里逐字翻成人话。
 * ⚠️ `plan_changed` 单独一支：它的 `from_value` / `to_value` 是
 *    `{goal_value, floor_value}` 而不是标量，走下面的通用分支会打印出 `[object Object]`。
 *    而且 `to_value` 为 `null` 是**取消设定**（不是「改成 null」），话要说得不一样。
 */
function changeText(row: SelfRunMetricLog): string {
  if (row.action === 'created') return '按模板建了这条'
  if (row.action === 'retired') return '退役'
  if (row.action === 'revived') return '恢复'
  if (row.action === 'plan_changed') {
    const to = row.to_value as { goal_value?: number | null; floor_value?: number | null } | null
    const from = row.from_value as { goal_value?: number | null; floor_value?: number | null } | null
    const f = (v?: number | null) => (v === null || v === undefined ? '—' : String(v))
    if (!to) return `${row.field_name}：取消设定（原 ${f(from?.goal_value)} / ${f(from?.floor_value)}）`
    return `${row.field_name}：${f(from?.goal_value)} / ${f(from?.floor_value)} → ${f(to.goal_value)} / ${f(to.floor_value)}`
  }
  const field = FIELD_LABEL[row.field_name ?? ''] ?? row.field_name ?? ''
  return `${field}：${plain(row.from_value)} → ${plain(row.to_value)}`
}

/** 字段名翻成人话 —— 直接把 `source_config` 摆出来等于没解释 */
const FIELD_LABEL: Record<string, string> = {
  goal_value: '目标',
  floor_value: '底线',
  name: '名称',
  unit: '单位',
  direction: '方向',
  agg: '口径',
  source_config: '取数配置',
  goal_why: '目标依据',
  floor_why: '底线依据',
  status: '状态',
  period_type: '周期',
}

/** 🔴 `null` 显示「—」不显示 `null`：`null` 是「没有这一档」，不是「值叫 null」 */
function plain(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
</script>

<style scoped>
.cl-card { border-radius: 10px; }
.cl-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.cl-title { font-weight: 600; }
.cl-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }
.cl-spacer { flex: 1; }
.cl-count { font-size: 12px; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.cl-mono { font-variant-numeric: tabular-nums; font-size: 12px; }

.cl-foot {
  margin-top: 10px; padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.7;
}
</style>
