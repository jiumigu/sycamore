<template>
  <div class="happiness-scale">
    <el-slider
      :model-value="modelValue"
      :min="min"
      :max="max"
      show-stops
      @update:model-value="onInput"
    />
    <span class="scale-label">{{ preview }}</span>
  </div>
</template>

<script setup lang="ts">
/**
 * 快乐程度输入 —— **唯一实现**，供「快乐日记」（SugarView）与「收件箱完成弹窗」共用。
 *
 * 为什么要抽出来：这两处原来各写一套刻度，还都不完整 ——
 *   - 快乐日记：滑块 5–20 分，金额 = 分数；
 *   - 收件箱弹窗：五颗星，`星 × 4` 换成 5–20 分，**金额却另填一个固定 5**。
 * 于是同一条小确幸：感受分 12、实际入账 5，流水文案说「获得 12 元」、右边写着 `+¥5.00`。
 *
 * 现在的口径只有一条：**刻度 5–20（区间由后端 `happiness_bands` 下发），金额 = 分数**。
 * 任何地方再需要「星」「档」「系数」，都应改这里，不要在下游再折算一次。
 */
import { computed, onMounted } from 'vue'
import { useSugarStore } from '../stores/sugarStore'
import { happinessLabelOf } from '../types/sugarTypes'

const props = defineProps<{ modelValue: number }>()
const emit = defineEmits<{ 'update:modelValue': [v: number] }>()

const store = useSugarStore()

// 区间由后端下发；`?? 5 / ?? 20` 只是表还没到时的占位（挂载即拉，毫秒级）
const min = computed(() => store.happinessBands?.min ?? 5)
const max = computed(() => store.happinessBands?.max ?? 20)

/** 取不到档位表就**只说分数、不编词**（与卡片同一降级规则） */
const preview = computed(() => {
  const label = happinessLabelOf(store.happinessBands, props.modelValue)
  return label ? `${props.modelValue} — ${label}` : String(props.modelValue)
})

function onInput(v: number | number[]) {
  emit('update:modelValue', Array.isArray(v) ? v[0] : v)
}

// 收件箱不在 sugar 页，bands 可能还没拉过 ⇒ 自己兜一次（失败不抛，只是降级成纯分数）
onMounted(() => {
  if (!store.happinessBands) store.fetchHappinessBands()
})
</script>

<style scoped lang="scss">
.happiness-scale {
  width: 100%;
  .scale-label {
    display: block;
    font-size: 13px;
    color: #666;
    margin-top: 4px;
  }
}
</style>
