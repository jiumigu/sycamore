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
      <el-skeleton :rows="5" animated />
    </div>

    <template v-else-if="data">
      <!-- 周概要信息 -->
      <div class="detail__dates">{{ data.week_start_date }} ~ {{ data.week_end_date }}</div>

      <el-descriptions :column="3" border size="small" class="detail__summary">
        <el-descriptions-item label="总收入">
          <span class="detail__income">+{{ maskAmountByType(data.income, '收入', privacyStore.privacyMode) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="总支出">
          <span class="detail__expense">-{{ maskAmountByType(data.expense, '支出', privacyStore.privacyMode) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="净结余">
          <span :class="data.net >= 0 ? 'detail__income' : 'detail__expense'">
            ¥{{ fmt(data.net) }}
          </span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 账单列表 -->
      <div class="detail__section-title">账单明细</div>

      <!-- 🔴 「取不到」与「这一周没有账单」必须分开说。
           上面那三个数是周历表聚合出来的（已经在库里），下面是明细没取到 ——
           以前失败被静默当成空数组，于是上面写着 +12,754.00、下面写着「无账单记录」。 -->
      <div v-if="error" class="detail__error">
        <el-alert :title="error" type="warning" :closable="false" show-icon>
          <template #default>
            <div class="detail__error-body">
              <span>上方收支数字来自周历聚合，与明细是两条取数链路；本次是明细没取到。</span>
              <el-button link type="primary" size="small" @click="emit('retry')">重试</el-button>
            </div>
          </template>
        </el-alert>
      </div>

      <el-table v-else-if="bills.length > 0" :data="bills" size="small" stripe max-height="360px">
        <el-table-column label="日期" width="100">
          <template #default="{ row }">{{ fmtDay(row.date) }}</template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="80" />
        <el-table-column prop="subcategory" label="子分类" width="80" />
        <el-table-column label="类型" width="60">
          <template #default="{ row }">
            <el-tag :type="row.transaction_type === '收入' ? 'success' : 'danger'" size="small">
              {{ row.transaction_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="100" align="right">
          <template #default="{ row }">
            <span :class="row.transaction_type === '收入' ? 'detail__income' : 'detail__expense'">
              {{ maskAmountByType(row.amount, row.transaction_type, privacyStore.privacyMode) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="100" show-overflow-tooltip />
      </el-table>

      <el-empty v-else description="本周无账单记录" :image-size="80" />
    </template>

    <template v-else>
      <el-empty description="暂无数据" :image-size="80" />
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { maskAmountByType } from '@/shared/utils/privacy'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { formatAmount } from '@/shared/utils/format'
import type { WeekCalendarEntry, BillItem } from '../types/wealthTypes'

const privacyStore = usePrivacyStore()

const emit = defineEmits<{
  close: []
  retry: []
}>()

const props = defineProps<{
  visible: boolean
  data: WeekCalendarEntry | null
  bills: BillItem[]
  loading: boolean
  /** 明细加载失败的提示；null = 正常（此时 `bills` 为空才表示「这一周真的没有账单」） */
  error?: string | null
}>()

const dialogTitle = computed(() => {
  if (!props.data) return '周明细'
  return `第${props.data.global_week_index}周 (${props.data.age_year}岁 第${props.data.week_number}周)`
})

function fmt(val: number): string {
  return formatAmount(val)
}

/**
 * 明细里的 `date` 是**带时分秒的 datetime**（`2026-09-21T07:57:02`），
 * 而这一列（100px）只放得下日期。
 * ⚠️ 用字符串切片、不 `new Date()` —— 后者是第二把尺子（时区一改就静默差几小时）；
 * 格式不符就返回空串，不显示切坏的乱码。
 */
function fmtDay(val: string | null): string {
  return typeof val === 'string' && val.length >= 10 ? val.slice(0, 10) : ''
}

function handleClose() {
  emit('close')
}
</script>

<style scoped lang="scss">
.detail__loading {
  padding: 20px;
}

.detail__dates {
  text-align: center;
  color: #999;
  font-size: 13px;
  margin-bottom: 16px;
}

.detail__summary {
  margin-bottom: 20px;
}

.detail__income {
  color: #67c23a;
  font-weight: 600;
}

.detail__expense {
  color: #f56c6c;
  font-weight: 600;
}

.detail__section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #eee;
}

.detail__error-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
</style>
