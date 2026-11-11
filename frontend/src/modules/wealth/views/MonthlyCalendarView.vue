<template>
  <div class="monthly">
    <div class="monthly__toolbar">
      <el-button size="small" @click="showImportDialog = true">
        <el-icon><Upload /></el-icon>
        导入CSV
      </el-button>
    </div>

    <CalendarHeader
      :year="store.currentYear"
      :month="store.currentMonth"
      @navigate="store.navigateMonth"
      @today="store.goToToday"
      @update:year="store.goToYearMonth($event, store.currentMonth)"
      @update:month="store.goToYearMonth(store.currentYear, $event)"
    />

    <div v-if="store.monthlyLoading" class="monthly__loading">
      <el-skeleton :rows="6" animated />
    </div>

    <template v-else>
      <CalendarGrid
        :days="store.monthlyDays"
        :year="store.currentYear"
        :month="store.currentMonth"
        :selected-date="store.selectedDate"
        @select="handleDaySelect"
      />
    </template>

    <StatsFooter :summary="store.monthlySummary" />

    <!-- 账单清单（原「月视图/宏观热力图」切换位：随日历年月联动） -->
    <el-card shadow="never" class="bill-section">
      <template #header>
        <div class="bill-section__header">
          <span>📋 账单清单</span>
          <span class="bill-section__hint">支出可按 必要 / 可选 / 冲动 标记（行内或批量），便于消费复盘</span>
        </div>
      </template>
      <BillListView :year="store.currentYear" :month="store.currentMonth" />
    </el-card>

    <!-- 单日明细弹窗 -->
    <DayDetailModal
      :visible="detailVisible"
      :loading="store.dailyDetailLoading"
      :detail="store.currentDailyDetail"
      :date-str="store.selectedDate"
      @close="handleDetailClose"
      @submit-bill="handleBillSubmit"
    />

    <!-- CSV 导入弹窗：选文件即预演 → 看列映射与问题行 → 确认才落库 -->
    <BillImportDialog
      v-model="showImportDialog"
      @success="handleImportSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Upload } from '@element-plus/icons-vue'
import { useWealthStore } from '../stores/wealthStore'
import CalendarHeader from '../components/monthly/CalendarHeader.vue'
import CalendarGrid from '../components/monthly/CalendarGrid.vue'
import StatsFooter from '../components/monthly/StatsFooter.vue'
import DayDetailModal from '../components/monthly/DayDetailModal.vue'
import BillImportDialog from '../components/monthly/BillImportDialog.vue'
import BillListView from '../components/BillListView.vue'
import type { BillCreateData } from '../types/wealthTypes'

const store = useWealthStore()
const detailVisible = ref(false)
const showImportDialog = ref(false)

async function handleDaySelect(dateStr: string) {
  await store.selectDate(dateStr)
  detailVisible.value = true
}

function handleDetailClose() {
  detailVisible.value = false
}

async function handleBillSubmit(data: BillCreateData) {
  await store.createBill(data)
}

/** 导入成功后刷新当月日历与汇总 —— 新账必须立刻出现在格子里 */
function handleImportSuccess() {
  store.fetchMonthlyData()
}

onMounted(() => {
  if (store.monthlyDays.length === 0) {
    store.fetchMonthlyData()
  }
})
</script>

<style scoped lang="scss">
.monthly {
  padding: 24px;
  max-width: 1200px;

  &__toolbar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 8px;
  }

  &__loading {
    padding: 24px;
    background: #fff;
    border-radius: 8px;
  }
}

.bill-section {
  margin-top: 16px;
  :deep(.el-card__body) {
    padding: 16px 20px 20px;
  }

  &__header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  &__hint {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}
</style>
