<template>
  <el-dialog
    :model-value="visible"
    :title="dialogTitle"
    width="600px"
    :close-on-click-modal="true"
    @update:model-value="handleClose"
    @close="handleClose"
  >
    <div v-if="loading" class="detail__loading">
      <el-skeleton :rows="8" animated />
    </div>

    <template v-else-if="detail">
      <!-- 日期信息 -->
      <div class="detail__date-info">
        <div class="detail__date-main">{{ dateInfo.main }}</div>
        <div class="detail__date-sub">{{ dateInfo.sub }}</div>
      </div>

      <!-- 当日汇总 -->
      <el-descriptions :column="3" border size="small" class="detail__summary">
        <el-descriptions-item label="总收入">
          <span class="detail__income">+{{ maskAmountByType(detail.income_total, '收入', privacyStore.privacyMode) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="总支出">
          <span class="detail__expense">-{{ maskAmountByType(detail.expense_total, '支出', privacyStore.privacyMode) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="净收入">
          <span :class="detail.net >= 0 ? 'detail__income' : 'detail__expense'">
            ￥{{ fmt(detail.net) }}
          </span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 收入列表 -->
      <div v-if="detail.income_list.length > 0" class="detail__section">
        <div class="detail__section-title detail__section-title--income">
          收入 ({{ detail.income_list.length }}笔)
        </div>
        <div v-for="bill in detail.income_list" :key="bill.id" class="detail__bill-row">
          <span class="detail__bill-cat">{{ bill.category }}</span>
          <span class="detail__bill-note">{{ bill.notes || bill.subcategory || '' }}</span>
          <span class="detail__bill-amount detail__income">+{{ maskAmountByType(bill.amount, '收入', privacyStore.privacyMode) }}</span>
        </div>
      </div>

      <!-- 支出列表 -->
      <div v-if="detail.expense_list.length > 0" class="detail__section">
        <div class="detail__section-title detail__section-title--expense">
          支出 ({{ detail.expense_list.length }}笔)
        </div>
        <div v-for="bill in detail.expense_list" :key="bill.id" class="detail__bill-row">
          <span class="detail__bill-cat">{{ bill.category }}</span>
          <span class="detail__bill-note">{{ bill.notes || bill.subcategory || '' }}</span>
          <span class="detail__bill-amount detail__expense">-{{ maskAmountByType(bill.amount, '支出', privacyStore.privacyMode) }}</span>
        </div>
      </div>

      <!-- 无记录 -->
      <el-empty
        v-if="detail.income_list.length === 0 && detail.expense_list.length === 0"
        description="当日无账单记录"
        :image-size="60"
      />

      <!-- 快速记账 -->
      <el-divider />
      <div class="detail__quick-title">快速记账</div>
      <QuickBillForm
        :default-date="dateStr"
        :submitting="submitting"
        @submit="handleBillSubmit"
        @cancel="() => {}"
      />
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { maskAmountByType } from '@/shared/utils/privacy'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { formatAmount } from '@/shared/utils/format'
import type { DailyDetail, BillCreateData } from '../../types/wealthTypes'
import { getLunarInfo } from '../common/LunarUtil'
import QuickBillForm from '../common/QuickBillForm.vue'

const privacyStore = usePrivacyStore()

const props = defineProps<{
  visible: boolean
  loading: boolean
  detail: DailyDetail | null
  dateStr: string | null
}>()

const emit = defineEmits<{
  close: []
  submitBill: [data: BillCreateData]
}>()

const submitting = ref(false)

const dialogTitle = computed(() => {
  if (!props.dateStr) return '日明细'
  return `账单明细 · ${props.dateStr}`
})

const dateInfo = computed(() => {
  if (!props.dateStr) return { main: '', sub: '' }
  const [y, m, d] = props.dateStr.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekday = weekdays[date.getDay()]
  const lunar = getLunarInfo(date)
  return {
    main: `${y}年${m}月${d}日 ${weekday}`,
    sub: `农历${lunar.lunarYear}年 · ${lunar.display}`,
  }
})

function fmt(val: number): string {
  return formatAmount(val)
}

function handleClose() {
  emit('close')
}

function handleBillSubmit(data: BillCreateData) {
  emit('submitBill', data)
}
</script>

<style scoped lang="scss">
.detail__loading { padding: 20px; }

.detail__date-info {
  text-align: center;
  margin-bottom: 16px;
}

.detail__date-main {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.detail__date-sub {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}

.detail__summary { margin-bottom: 16px; }
.detail__income { color: #389e0d; font-weight: 600; }
.detail__expense { color: #cf1322; font-weight: 600; }

.detail__section { margin-bottom: 12px; }

.detail__section-title {
  font-size: 13px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 6px;

  &--income {
    background: #f0fae8;
    color: #389e0d;
  }

  &--expense {
    background: #fff0f0;
    color: #cf1322;
  }
}

.detail__bill-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  font-size: 13px;
  border-bottom: 1px solid #f5f5f5;

  &:last-child { border-bottom: none; }
}

.detail__bill-cat {
  font-weight: 500;
  color: #333;
  min-width: 60px;
}

.detail__bill-note {
  flex: 1;
  color: #999;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail__bill-amount {
  font-weight: 600;
  white-space: nowrap;
}

.detail__quick-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}
</style>
