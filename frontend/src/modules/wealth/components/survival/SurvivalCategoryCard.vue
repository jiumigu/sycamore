<!--
  生存资源盘点 · 类别卡（四卡骨架）

  🔴 卡上**只显示后端算好的数**，一个除法都不做。
     三档与期望值全部来自 `/wealth/survival/analysis/`。

  ⚠️ 期望值为 null 时显示「算不出来」并说明原因，**绝不给 0** ——
     0 是「真的撑 0 天」的结论，「还没配好单位 / 配方缺件」是完全不同的状态，
     显示成 0 会让人以为明天就断粮。

  ⚠️ 口径口径来自后端 `constants.SURVIVAL_METRIC_NOTES`（经 /survival/meta/ 下发），
     本组件不写一句口径文案。
-->
<template>
  <div
    class="survival-card"
    :class="{ 'survival-card--active': active, 'survival-card--untrusted': !result.trustworthy }"
    @click="$emit('select', result.category_id)"
  >
    <div class="survival-card__head">
      <el-icon class="survival-card__icon"><component :is="iconComponent" /></el-icon>
      <span class="survival-card__name">{{ result.name }}</span>
      <MetricTooltip v-if="meta" :meta="meta" :width="340" />
      <el-tag v-if="!result.trustworthy" type="warning" size="small" effect="plain">
        配置待完善
      </el-tag>
    </div>

    <div class="survival-card__value">
      <span class="survival-card__value-num">{{ expectedText }}</span>
      <span class="survival-card__value-unit">期望可撑</span>
    </div>

    <div class="survival-card__range">
      {{ rangeText }}<span v-if="spreadText" class="survival-card__spread">· {{ spreadText }}</span>
    </div>

    <div class="survival-card__foot">
      <span v-if="result.usable_item_count" class="survival-card__foot-item">
        {{ result.usable_item_count }} 件可用
      </span>
      <span v-else class="survival-card__foot-item survival-card__foot-item--empty">
        还没有可用物品
      </span>
      <span v-if="result.snack_days !== null" class="survival-card__foot-item">
        零食另 {{ formatDays(result.snack_days) }}
      </span>
      <span v-if="result.hours_total !== null" class="survival-card__foot-item">
        可读 {{ formatHours(result.hours_total) }}
      </span>
    </div>

    <!-- 短板只在算得出来时才说，算不出来时上方已显示原因 -->
    <div v-if="bottleneckText" class="survival-card__bottleneck">
      <el-icon><Bottom /></el-icon>
      <span>{{ bottleneckText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Bottom, Box, Food, Handbag, Notebook, Reading } from '@element-plus/icons-vue'
import MetricTooltip from '../common/MetricTooltip.vue'
import { formatDays, formatHours, formatSpread } from '../../utils/survivalFormat'
import type { SurvivalCategoryResult } from '../../types/survivalTypes'
import type { RatioMeta } from '../../types/wealthTypes'

const props = defineProps<{
  result: SurvivalCategoryResult
  /** 口径元信息；取不到时不渲染气泡（而不是渲染一个空的） */
  meta?: RatioMeta | null
  active?: boolean
}>()

defineEmits<{ select: [id: number] }>()

const ICONS: Record<string, unknown> = {
  Food, Handbag, Notebook, Reading, Box,
}

const iconComponent = computed(() => ICONS[props.result.icon] ?? Box)

const expectedText = computed(() => formatDays(props.result.expected))
const rangeText = computed(() => {
  const { optimistic: o, pessimistic: p } = props.result.days
  if (o === null || p === null) return '三档估不出来'
  return `${formatDays(p)} ~ ${formatDays(o)}`
})
const spreadText = computed(() => (
  props.result.spread === null ? '' : formatSpread(props.result.spread)
))

/** 短板指向：配餐类指的是配方里哪一样先断 */
const bottleneckText = computed(() => {
  const recipes = props.result.recipes ?? []
  for (const recipe of recipes) {
    if (recipe.bottleneck_item) {
      return `短板「${recipe.recipe_name}」→ ${recipe.bottleneck_item}`
    }
  }
  const capped = recipes.find((r) => r.capped_by_expiry)
  if (capped) return `受保质期封顶：${capped.recipe_name}`
  return ''
})
</script>

<style scoped>
.survival-card {
  padding: 14px 16px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.survival-card:hover {
  border-color: var(--el-color-primary-light-5);
}
.survival-card--active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-8);
}
.survival-card--untrusted {
  background: var(--el-color-warning-light-9);
}
.survival-card__head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.survival-card__icon {
  font-size: 16px;
  color: var(--el-color-primary);
}
.survival-card__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.survival-card__value {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.survival-card__value-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}
.survival-card__value-unit {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-card__range {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.survival-card__spread {
  margin-left: 6px;
  color: var(--el-text-color-secondary);
}
.survival-card__foot {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-card__foot-item--empty {
  color: var(--el-color-warning);
}
.survival-card__bottleneck {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px;
  color: var(--el-color-danger);
}
</style>
