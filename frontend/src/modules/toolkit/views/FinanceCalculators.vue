<template>
  <div class="finance-calculators">
    <el-tabs v-model="activeTab" class="finance-tabs">
      <el-tab-pane label="💰 固定开销" name="fixed-expense">
        <FixedExpense />
      </el-tab-pane>
      <el-tab-pane label="💸 自由支配额度" name="free-spending">
        <FreeSpending />
      </el-tab-pane>
      <el-tab-pane label="⏱️ 时薪" name="hourly-wage">
        <HourlyWage />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import FixedExpense from './tools/FixedExpense.vue'
import FreeSpending from './tools/FreeSpending.vue'
import HourlyWage from './tools/HourlyWage.vue'

// 支持从旧工具 key 直达对应 tab（如 /toolkit/hourly-wage → 时薪 tab）
const props = defineProps<{
  toolKey?: string
}>()

const TAB_MAP: Record<string, string> = {
  'fixed-expense': 'fixed-expense',
  'free-spending': 'free-spending',
  'hourly-wage': 'hourly-wage',
}

const activeTab = ref('fixed-expense')

onMounted(() => {
  if (props.toolKey && TAB_MAP[props.toolKey]) {
    activeTab.value = TAB_MAP[props.toolKey]
  }
})
</script>

<style scoped>
.finance-calculators {
  padding: 4px 0;
}
.finance-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}
.finance-tabs :deep(.el-tabs__content) {
  overflow: visible;
}
</style>
