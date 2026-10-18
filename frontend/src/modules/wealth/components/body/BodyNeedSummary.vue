<!--
  身上之物 · 顶部计数（v3.62.4）

  这一块只回答一个问题：**还有几件没搞定。**

  🔴 `pending_count` 与点进去看到的行数**必须一致** —— 两者走后端同一个判据
     （`body_service.is_pending`），前端不重写一遍筛选条件。
     两处各写一遍，就会出现「念 5 件、点进去 3 行」：两个数都对不上，
     而且没人会去查。

  ⚠️ 四个小档（全部 / 待寻 / 寻找中 / 已找到）里，后三个的**文字来自接口**
     （`/body/meta/` 的 `find_statuses`），前端一个字都不复写 ——
     复写的那份改后端时不会被改到，而界面上照旧说得通。

  ⚠️ 只有「全部 / 还没搞定 / 进度」这三类能点着筛 —— 它们分别对应一个筛选维度。
     让一个纯展示的数字长成可点的样子，会让人以为点了能筛出别的东西
     （同物件资产四卡：金额卡刻意不可点）。
-->
<template>
  <div class="body-summary">
    <div
      class="body-summary__head"
      :class="{ 'is-active': active === 'pending', 'is-clickable': true }"
      @click="toggle('pending')"
    >
      <div class="body-summary__head-main">
        <span class="body-summary__head-num">{{ summary?.pending_count ?? 0 }}</span>
        <span class="body-summary__head-text">件还没搞定</span>
        <MetricTooltip :meta="metaByKey.pending_count" :width="360" />
      </div>
      <div class="body-summary__head-sub">
        「待寻」与「寻找中」都算在里面；定下来了就不在这一栏
      </div>
    </div>

    <div class="body-summary__chips">
      <button
        type="button"
        class="body-summary__chip"
        :class="{ 'is-active': active === 'all' }"
        @click="toggle('all')"
      >
        全部 <b>{{ summary?.total ?? 0 }}</b>
      </button>
      <button
        v-for="option in store.findStatusOptions"
        :key="option.value"
        type="button"
        class="body-summary__chip"
        :class="{ 'is-active': active === option.value }"
        @click="toggle(option.value)"
      >
        {{ option.label }} <b>{{ countOf(option.value) }}</b>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import MetricTooltip from '../common/MetricTooltip.vue'
import { useBodyStore } from '../../stores/bodyStore'
import type { BodySummary } from '../../types/bodyTypes'
import type { RatioMeta } from '../../types/wealthTypes'

const props = defineProps<{
  summary: BodySummary | null
  /** key → 口径元信息（取不到就不渲染气泡，不硬编码文案） */
  metaByKey: Record<string, RatioMeta>
  /** 当前的筛选口径：'' 之外的值来自本组件的 toggle */
  active: string
}>()
const emit = defineEmits<{
  filter: [value: string]
}>()

const store = useBodyStore()

/** 枚举计数按**值**取 —— 键名由后端按 `BODY_FIND_STATUS_CHOICES` 生成 */
function countOf(value: string): number {
  const data = props.summary as unknown as Record<string, number> | null
  return data?.[value] ?? 0
}

/**
 * 再点一次同一个 = 取消筛选（与四卡、生存资源盘点的交互习惯一致）。
 *
 * ⚠️ 出口不许关掉自己：这里只是回到「不筛」，四个档仍然都在。
 */
function toggle(value: string) {
  emit('filter', props.active === value ? '' : value)
}
</script>

<style scoped>
.body-summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.body-summary__head {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.body-summary__head.is-clickable {
  cursor: pointer;
}
.body-summary__head.is-clickable:hover {
  border-color: var(--el-color-primary-light-5);
}
.body-summary__head.is-active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-7) inset;
}
.body-summary__head-main {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.body-summary__head-num {
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}
.body-summary__head-text {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.body-summary__head-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.body-summary__chips {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.body-summary__chip {
  padding: 4px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  background: var(--el-fill-color-blank);
  font-size: 13px;
  color: var(--el-text-color-regular);
  cursor: pointer;
  font-family: inherit;
  transition: border-color 0.15s, color 0.15s, background-color 0.15s;
}
.body-summary__chip:hover {
  border-color: var(--el-color-primary-light-5);
}
.body-summary__chip.is-active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.body-summary__chip b {
  margin-left: 2px;
  font-variant-numeric: tabular-nums;
}
</style>
