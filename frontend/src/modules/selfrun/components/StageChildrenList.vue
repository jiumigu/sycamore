<!-- 长阶段账本 · 小阶段列表
     ────────────────────────────────────────────────────────────
     一行一个小阶段：名字 / 区间 / 状态 / 达标率 / 进详情。

     🔴 **达标率是那个小阶段的，不是长阶段的**。长阶段没有 `SelfRunPeriod`，
        自己不产生任何判定 —— 这里的每个数都是遍历 `stage.children` 现算的
        （后端复用 `compute_stage_summary()`，与「阶段总结」同一个函数）。

     ⚠️ 「进详情」只给**正在跑的那一个**小阶段：
        `SelfRunHub` 的周/月/总结三页读的都是「当前阶段」（`store.stage`），
        没有「打开任意一个阶段」的能力。给已收尾的小阶段挂一个按钮，
        点下去会打开**另一个**阶段的数字 —— 那比没有按钮坏得多。
        已收尾的小阶段：它的每周结论在「历史复盘」里（那页不按阶段过滤）。
-->
<template>
  <div class="stage-children">
    <div v-if="!children.length" class="sc-empty">
      还没有小阶段 —— 长阶段可以先建、后挂小阶段，所以现在这样子是正常的。
    </div>

    <div v-for="c in children" :key="c.id" class="sc-row">
      <div class="sc-main">
        <span class="sc-name">{{ c.name }}</span>
        <el-tag size="small" effect="plain" :type="tagType(c.status_display)">{{ c.status_display }}</el-tag>
      </div>

      <div class="sc-range">{{ c.range_label }}</div>

      <div class="sc-rate">
        <!-- `null` ≠ 0%：`null` 是「一次都还没判定过」 -->
        <template v-if="c.reach_rate === null">
          <span class="sc-null">—</span>
          <span class="sc-sub">还没有判定过的期</span>
        </template>
        <template v-else>
          <span class="sc-pct">{{ (c.reach_rate * 100).toFixed(1) }}%</span>
          <span class="sc-sub">{{ c.hit }}/{{ c.judged }} 次达标</span>
        </template>
      </div>

      <div class="sc-act">
        <el-button
          v-if="c.id === openStageId"
          link type="primary" size="small"
          @click="goWeek"
        >进本周状态</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { LedgerChild } from '../types/selfrunTypes'

defineProps<{
  children: LedgerChild[]
  /** 当前真正在跑的那个阶段的 id（不是长阶段的 id）；不匹配的行不给入口 */
  openStageId: number | null
}>()

const router = useRouter()

/** 状态 → 标签配色。⚠️ 词是后端给的（`status_display`），这里只上色不判 */
function tagType(statusDisplay: string): 'success' | 'warning' | 'info' {
  if (statusDisplay === '进行中') return 'success'
  if (statusDisplay === '暂停中') return 'warning'
  return 'info'
}

/** 走**路由名**不走路径字面量；这里刻意不传 id ——
 *  周页读的是「当前阶段」，传了 id 它也不认（认了就是两套口径）。 */
function goWeek() {
  router.push({ name: 'selfrun-week' })
}
</script>

<style scoped>
.sc-empty {
  font-size: 13px; color: var(--el-text-color-secondary);
  padding: 10px 0;
}
.sc-row {
  display: grid;
  grid-template-columns: minmax(150px, 1.2fr) minmax(200px, 1.6fr) minmax(120px, 0.9fr) 96px;
  gap: 12px;
  align-items: center;
  padding: 10px 4px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.sc-row:first-child { border-top: none; }
.sc-main { display: flex; align-items: center; gap: 8px; min-width: 0; }
.sc-name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc-range { font-size: 13px; color: var(--el-text-color-regular); }
.sc-rate { display: flex; flex-direction: column; gap: 2px; }
.sc-pct { font-weight: 700; }
.sc-null { font-weight: 700; color: var(--el-text-color-placeholder); }
.sc-sub { font-size: 12px; color: var(--el-text-color-secondary); }
.sc-act { text-align: right; }
</style>
