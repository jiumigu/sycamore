<template>
  <div class="calendar-header">
    <div class="calendar-header__nav">
      <el-button text size="small" @click="$emit('navigate', -1)">
        <el-icon><ArrowLeft /></el-icon>
      </el-button>

      <el-select
        v-model="localYear"
        size="small"
        style="width: 90px"
        @change="onYearChange"
      >
        <el-option
          v-for="y in yearRange"
          :key="y"
          :label="`${y}年`"
          :value="y"
        />
      </el-select>

      <el-select
        v-model="localMonth"
        size="small"
        style="width: 80px"
        @change="onMonthChange"
      >
        <el-option
          v-for="m in 12"
          :key="m"
          :label="`${m}月`"
          :value="m"
        />
      </el-select>

      <el-button text size="small" @click="$emit('navigate', 1)">
        <el-icon><ArrowRight /></el-icon>
      </el-button>

      <el-button size="small" class="calendar-header__today" @click="$emit('today')">
        今日
      </el-button>
    </div>

    <div class="calendar-header__view-switch">
      <el-button
        :type="viewMode === 'monthly' ? 'primary' : 'default'"
        size="small"
        @click="$emit('switch-view', 'monthly')"
      >
        月视图
      </el-button>
      <el-button
        :type="viewMode === 'heatmap' ? 'primary' : 'default'"
        size="small"
        @click="$emit('switch-view', 'heatmap')"
      >
        宏观热力图
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import type { CalendarViewMode } from '../../types/wealthTypes'

const props = defineProps<{
  year: number
  month: number
  viewMode: CalendarViewMode
}>()

const emit = defineEmits<{
  navigate: [delta: number]
  today: []
  'update:year': [year: number]
  'update:month': [month: number]
  'switch-view': [mode: CalendarViewMode]
}>()

const yearRange = computed(() => {
  const current = new Date().getFullYear()
  const start = current - 60
  const end = current + 2
  const years: number[] = []
  for (let y = start; y <= end; y++) years.push(y)
  return years
})

const localYear = computed({
  get: () => props.year,
  set: (v) => emit('update:year', v),
})

const localMonth = computed({
  get: () => props.month,
  set: (v) => emit('update:month', v),
})

function onYearChange() { /* auto-triggers via v-model */ }
function onMonthChange() { /* auto-triggers via v-model */ }
</script>

<style scoped lang="scss">
.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;

  &__nav {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  &__today {
    margin-left: 8px;
  }

  &__view-switch {
    display: flex;
    gap: 4px;
  }
}
</style>
