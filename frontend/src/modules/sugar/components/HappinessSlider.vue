<template>
  <div class="happiness-slider">
    <div class="slider-labels">
      <span
        v-for="i in 10" :key="i"
        class="label-dot"
        :class="{ active: modelValue >= i }"
        :style="{ background: getColor(i) }"
        @click="$emit('update:modelValue', i)"
      >
        {{ i }}
      </span>
    </div>
    <el-slider
      :model-value="modelValue"
      :min="1"
      :max="10"
      :step="0.1"
      :format-tooltip="(v: number) => v.toFixed(1)"
      @update:model-value="$emit('update:modelValue', $event)"
      :marks="marks"
      :show-stops="false"
      class="slider-main"
    />
    <div class="slider-result">
      <span class="result-emoji">{{ emoji }}</span>
      <span class="result-text" :style="{ color: textColor }">
        {{ modelValue.toFixed(1) }} — {{ label }}
      </span>
      <span class="result-reward">可获得 {{ reward }} 元奖励</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ modelValue: number }>()
const emit = defineEmits<{ 'update:modelValue': [v: number] }>()

function getColor(v: number): string {
  if (v <= 3) return '#9CA3AF'
  if (v <= 5) return '#60A5FA'
  if (v <= 7) return '#34D399'
  if (v <= 8.5) return '#FBBF24'
  return '#F97316'
}

const textColor = computed(() => getColor(props.modelValue))

const emoji = computed(() => {
  const v = props.modelValue
  if (v <= 3) return '😊'
  if (v <= 5) return '🙂'
  if (v <= 7) return '😄'
  if (v <= 8.5) return '🥰'
  return '🤩'
})

const label = computed(() => {
  const v = props.modelValue
  if (v <= 3) return '小开心'
  if (v <= 5) return '开心'
  if (v <= 7) return '很高兴'
  if (v <= 8.5) return '超开心'
  return '幸福爆炸'
})

const reward = computed(() => {
  const v = props.modelValue
  if (v <= 3) return '1 元'
  if (v <= 5) return '3 元'
  if (v <= 7) return '5 元'
  if (v <= 8.5) return '8 元'
  return '10 元'
})

const marks = computed(() => {
  const m: Record<number, string> = {}
  ;[1, 3, 5, 7, 8.5, 10].forEach(v => { m[v] = '' })
  return m
})
</script>

<style scoped lang="scss">
.happiness-slider {
  .slider-labels {
    display: flex;
    gap: 4px;
    margin-bottom: 12px;

    .label-dot {
      flex: 1;
      height: 32px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 600;
      color: #9CA3AF;
      background: #F3F4F6;
      cursor: pointer;
      transition: all 0.2s;

      &.active {
        color: #fff;
        transform: scale(1.05);
      }

      &:hover { transform: scale(1.08); }
    }
  }

  .slider-main {
    padding: 0 4px;
    :deep(.el-slider__runway) { height: 6px; }
    :deep(.el-slider__bar) { height: 6px; }
    :deep(.el-slider__button) { width: 18px; height: 18px; border: 3px solid; }
  }

  .slider-result {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
    padding: 10px 14px;
    background: #F9FAFB;
    border-radius: 10px;

    .result-emoji { font-size: 20px; }

    .result-text {
      font-size: 14px;
      font-weight: 600;
    }

    .result-reward {
      margin-left: auto;
      font-size: 12px;
      color: #10B981;
      font-weight: 500;
    }
  }
}
</style>
