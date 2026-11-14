<template>
  <el-card shadow="never" class="whc">
    <template #header>
      <div class="whc-head">
        <span>{{ title }}</span>
        <span class="whc-head-right">
          <span v-if="whatHappened" class="whc-hint">
            有记录的 {{ whatHappened.day_count }} 天
          </span>
          <el-radio-group v-if="canTimeline" v-model="view" size="small">
            <el-radio-button value="timeline">时段</el-radio-button>
            <el-radio-button value="list">清单</el-radio-button>
          </el-radio-group>
          <!-- 月度不给时段轴：31 列挤进抽屉/卡片，每列 20px，块里放不下一个字。
               说一句是为了回答「为什么这周有图、这月没有」，不是辩解。 -->
          <span v-else-if="whatHappened && isMonthly" class="whc-hint">
            （月度列太多，用清单）
          </span>
        </span>
      </div>
    </template>

    <div v-if="!whatHappened" class="whc-hint">读取中…</div>

    <template v-else-if="whatHappened.days.length">
      <div class="whc-attr-row">
        <span v-for="a in whatHappened.attr_totals" :key="a.label" class="whc-attr">
          {{ a.label }} <b>{{ fmt(a.hours) }}</b>h
        </span>
      </div>

      <WhatHappenedTimeline
        v-if="view === 'timeline' && whatHappened.blocks.length"
        :columns="whatHappened.columns"
        :blocks="whatHappened.blocks"
        :span="whatHappened.span"
        :truncated="whatHappened.truncated"
        :attr-totals="whatHappened.attr_totals"
      />

      <div v-else class="whc-days">
        <div v-for="d in whatHappened.days" :key="d.date" class="whc-day">
          <span class="whc-day-when">{{ d.weekday }}<i>{{ d.md }}</i></span>
          <span class="whc-day-what">
            <span v-for="it in d.items" :key="it.task_name" class="whc-day-item">
              <i class="whc-dot-mini" :class="{ loss: it.attribution === '流失' }" />
              {{ it.task_name }}<em>{{ fmt(it.hours) }}h</em>
            </span>
            <span v-if="d.more" class="whc-day-more">等 {{ d.more }} 项</span>
          </span>
          <span class="whc-day-total">{{ fmt(d.total_hours) }}h</span>
        </div>
      </div>
    </template>

    <div v-else class="whc-hint">
      这一期没有任何时间记录 —— 不是「什么都没做」，是没记。
    </div>
  </el-card>
</template>

<script setup lang="ts">
/**
 * 「这一周我做了什么」—— 时段轴 / 清单两种看法，一张卡片装完。
 *
 * 🔴 两个页面共用本组件，**不许各写一份**：
 *    · 历史复盘抽屉（`ReviewPanel`）：看已归档的期
 *    · 本周状态页（`PeriodPanel`）：「归档这一周」按钮下方
 *    同一句话在两处渲染，复制出去的那份早晚会与这份分家 ——
 *    而且分家时不报错，只是两个页面数不一样。
 *
 * 🔴 三块数据全部来自后端 `what_happened`，组件一个都不自己算：
 *    `days` / `columns+blocks` / `span`。这里只决定「怎么摆」。
 *
 * ⚠️ 月度**没有**时段轴（`isMonthly`）—— 31 列每列不到 20px，
 *    块里放不下一个字。不是没做，是做了也读不出来。
 */
import { computed, ref, watch } from 'vue'
import WhatHappenedTimeline from './WhatHappenedTimeline.vue'
import { fmt } from '../types/selfrunTypes'
import type { PeriodType, WhatHappened } from '../types/selfrunTypes'

const props = defineProps<{
  /** `null` = 还没取到（显示「读取中…」，不伪装成「这一期没记录」） */
  whatHappened: WhatHappened | null
  /** 卡片标题 —— 周说「这一周」，月说「这一个月」，由页面按当期给 */
  title: string
  periodType: PeriodType
  /**
   * 切期时用它重置视图。**同一周期类型换一期**（周→周）时 `periodType`
   * 不变，只靠它才能把「上次选了清单」清回默认 —— 否则打开这一期看到的
   * 是上一期的看法，而这件事完全不报错。
   */
  periodKey: string
}>()

const isMonthly = computed(() => props.periodType === 'monthly')

/** 时段轴只给周，且得有块 —— 没块时切过去是一张空白图 */
const canTimeline = computed(
  () => !isMonthly.value && (props.whatHappened?.blocks.length ?? 0) > 0,
)

const view = ref<'timeline' | 'list'>(isMonthly.value ? 'list' : 'timeline')

// 换期就回到默认看法（周看时段、月看清单）。
// 不用 `whatHappened` 当依赖：同一期内刷新也会换对象，那会把用户刚切的视图打回去。
watch(() => props.periodKey, () => {
  view.value = isMonthly.value ? 'list' : 'timeline'
})
</script>

<style scoped>
.whc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-weight: 600;
}
.whc-head-right { display: flex; align-items: center; gap: 8px; }
.whc-hint { font-size: 12px; color: var(--el-text-color-secondary); }

/* 归因合计：成长 / 体验 / 维持 / 流失 */
.whc-attr-row {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.whc-attr b {
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}

/* 清单：按天一条，具体的事才勾得起回忆 */
.whc-days { display: flex; flex-direction: column; max-height: 320px; overflow: auto; }
.whc-day {
  display: flex;
  gap: 12px;
  align-items: baseline;
  padding: 7px 0;
  font-size: 12px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.whc-day-when { width: 62px; flex: none; color: var(--el-text-color-secondary); }
.whc-day-when i { font-style: normal; margin-left: 4px; color: var(--el-text-color-placeholder); }
.whc-day-what { flex: 1; min-width: 0; display: flex; flex-wrap: wrap; gap: 4px 12px; padding-right: 8px; }
.whc-day-item { display: inline-flex; align-items: center; gap: 5px; color: var(--el-text-color-primary); }
.whc-day-item em { font-style: normal; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.whc-day-total { flex: none; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.whc-day-more { color: var(--el-text-color-placeholder); }
.whc-dot-mini {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--el-color-success); flex: none;
}
.whc-dot-mini.loss { background: var(--el-color-danger); }
</style>
