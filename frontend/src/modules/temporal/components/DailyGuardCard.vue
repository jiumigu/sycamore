<template>
  <!--
    今天的三条线（v3.64.13：睡眠 / 午睡 / 流失）。

    🔴 为什么不是一段「温馨提示」：静态文案没有状态、分不出「今天过了没」，
       第一周读一遍、第二周变成背景。这里每条线都有实测值 / 阈值 / 三档状态。
    🔴 为什么必须在仪表盘：护栏要放在每天会打开的第一屏。
       任务清单页是「整理数据」的地方（表格 + 筛选 + 批量改归因），不是每天必看的一页。
    🔴 「流失」不看角色：玩游戏 / 刷短视频 / 看小说 在台账里本来就归流失，
       多标一遍角色等于同一件事量两次，标漏了还会静默失效。

    阈值与状态词全部来自后端（`constants.DAILY_GUARD_LINES`），本组件**不含任何数字**。
  -->
  <el-card v-if="data" shadow="never" class="dg-card">
    <div class="dg-head">
      <span class="dg-title">🌙 今天的三条线</span>
      <span class="dg-date">{{ dateText }}</span>
      <el-button
        size="small"
        text
        type="primary"
        class="dg-more"
        @click="$router.push({ path: '/temporal/tasks', query: { date_from: data.date, date_to: data.date } })"
      >看看今天记了什么 →</el-button>
    </div>

    <div class="dg-lines">
      <div v-for="l in data.lines" :key="l.key" class="dg-line" :class="`is-${l.status}`">
        <div class="dg-line-top">
          <span class="dg-label">{{ l.label }}</span>
          <span class="dg-status">{{ l.status_text }}</span>
        </div>
        <div class="dg-line-bottom">
          <span class="dg-value" :class="{ 'is-empty': l.value_hours === null }">{{ l.value_text }}</span>
          <span class="dg-threshold">{{ l.threshold_text }}</span>
        </div>
        <div class="dg-detail">{{ l.detail_text }}</div>
      </div>
    </div>

    <!-- 零态：还有线没落地时，上面那格全是「未记录」，不解释就像功能坏了。
         🔴 不在这里列举角色名/阈值：那是后端常量的第二份副本，改一次就漂一次。
            具体怎么补，每一格下面的 `detail_text` 已经写清了。 -->
    <div v-if="data.configured_lines < data.lines.length" class="dg-hint">
      还有 {{ data.lines.length - data.configured_lines }} 条线还没落地 ——
      每格下面那行小字写了怎么补（睡眠 / 午睡去「映射编辑器」标角色，流失看台账里有没有任务名归到「流失」）
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getDailyGuards } from '../api/temporalApi'
import type { DailyGuardData } from '../types/temporalTypes'

const data = ref<DailyGuardData | null>(null)

const dateText = computed(() => {
  const d = data.value?.date
  if (!d) return ''
  const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  // 后端给的是 YYYY-MM-DD 本地日期串，直接截断拼，**不要 new Date()**
  // （`new Date('2026-11-01')` 按 UTC 解析，UTC+8 下会退成 10-31）
  const [y, m, day] = d.split('-').map(Number)
  if (!y || !m || !day) return d
  return `${m} 月 ${day} 日 · ${week[new Date(y, m - 1, day).getDay()]}`
})

onMounted(async () => {
  try {
    // `request()` 返回的是 AxiosResponse，数据在 `.data` 里（别再解一层 `.data.data`）
    const res = await getDailyGuards()
    data.value = res.data
  } catch {
    // 读不到就不显示这张卡：仪表盘上不摆一张「全是 —」的假卡片，
    // 那样会让人以为「我今天真的啥也没干」。
    data.value = null
  }
})
</script>

<style scoped>
.dg-card {
  margin-bottom: 16px;
  border-radius: 10px;
  :deep(.el-card__body) { padding: 14px 20px; }
}
.dg-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.dg-title { font-weight: 600; font-size: 15px; }
.dg-date { font-size: 12px; color: var(--el-text-color-secondary); }
.dg-more { margin-left: auto; }

.dg-lines { display: flex; gap: 12px; margin-top: 10px; flex-wrap: wrap; }
.dg-line {
  flex: 1 1 180px;
  min-width: 0;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  border-left: 3px solid var(--el-border-color);
}
/* 配色只跟三档状态走：ok / off / unrecorded —— 不按「哪条线」分别设色 */
.dg-line.is-ok { border-left-color: #10b981; }
.dg-line.is-off { border-left-color: #ef4444; }
.dg-line.is-unrecorded { border-left-color: #cbd5e1; }

.dg-line-top { display: flex; align-items: baseline; gap: 8px; }
.dg-label { font-size: 12px; color: var(--el-text-color-regular); }
.dg-status { margin-left: auto; font-size: 12px; }
.is-ok .dg-status { color: #059669; }
.is-off .dg-status { color: #dc2626; }
.is-unrecorded .dg-status { color: var(--el-text-color-secondary); }

.dg-line-bottom { display: flex; align-items: baseline; gap: 8px; margin-top: 2px; }
.dg-value { font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; }
/* 🔴 `null`（没记录）用 `—`，**不是 0** —— 「没记」和「记了 0 小时」是两件事 */
.dg-value.is-empty { color: var(--el-text-color-placeholder); font-weight: 400; }
.dg-threshold { font-size: 12px; color: var(--el-text-color-secondary); }

.dg-detail { margin-top: 2px; font-size: 12px; line-height: 1.5; color: var(--el-text-color-secondary); }
.dg-hint {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
</style>
