<template>
  <el-dialog
    :model-value="visible"
    title="⏰ 到期处理"
    width="480px"
    @update:model-value="$emit('update:visible', $event)"
  >
    <template v-if="item">
      <!-- 存款信息 -->
      <el-descriptions :column="2" size="small" border class="info-table">
        <el-descriptions-item label="银行">{{ item.bankinfo || '未知' }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ formatMoney(item.value) }}</el-descriptions-item>
        <el-descriptions-item label="利率">{{ item.rate ?? '-' }}%</el-descriptions-item>
        <el-descriptions-item label="利息">{{ formatMoney(item.interest) }}</el-descriptions-item>
        <el-descriptions-item label="存入">{{ item.begin_date }}</el-descriptions-item>
        <el-descriptions-item label="到期">{{ item.end_date }}</el-descriptions-item>
      </el-descriptions>

      <div class="section-label">处理方式</div>
      <el-radio-group v-model="action" class="action-group">
        <el-radio value="withdraw">取出（本金+利息转活期）</el-radio>
        <el-radio value="renew">续存（本金续存，利息取出）</el-radio>
        <el-radio value="renew_all">本息续存（本金+利息一起续存）</el-radio>
      </el-radio-group>

      <!-- 续存信息 -->
      <el-card v-if="action !== 'withdraw'" shadow="none" class="renew-card">
        <template #header><span class="renew-title">续存信息</span></template>
        <el-form :model="renewForm" label-width="80px" size="small">
          <el-form-item label="新利率">
            <el-input v-model.number="renewForm.new_rate" type="number" step="0.01" min="0">
              <template #append>%</template>
            </el-input>
          </el-form-item>
          <el-form-item label="新到期日">
            <el-date-picker
              v-model="renewForm.new_end_date"
              type="date"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </el-form-item>
        </el-form>
      </el-card>
    </template>

    <template #footer>
      <el-button size="small" @click="$emit('update:visible', false)">取消</el-button>
      <el-button size="small" type="primary" :loading="saving" @click="handleSubmit">确认处理</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import type { RegularItem } from '../../types/wealthTypes'

const props = defineProps<{
  visible: boolean
  item: RegularItem | null
  saving: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [data: Record<string, unknown>]
}>()

const action = ref('withdraw')
const renewForm = reactive({
  new_rate: null as number | null,
  new_end_date: '',
})

function formatMoney(v: number | null | undefined): string {
  if (v == null) return '¥0'
  const n = Math.round(v)
  if (n >= 10000) return '¥' + (n / 10000).toFixed(1) + '万'
  return '¥' + n.toLocaleString()
}

function handleSubmit() {
  const data: Record<string, unknown> = { action: action.value }
  if (action.value !== 'withdraw') {
    if (renewForm.new_rate) data.new_rate = renewForm.new_rate
    if (renewForm.new_end_date) data.new_end_date = renewForm.new_end_date
  }
  emit('save', data)
}
</script>

<style scoped>
.info-table {
  margin-bottom: 16px;
}
.section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 10px;
}
.action-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
.renew-card {
  border: 1px solid #E5E7EB;
  background: #FAFAFA;
  border-radius: 8px;
}
.renew-card :deep(.el-card__header) {
  padding: 10px 14px;
  border-bottom: 1px solid #F3F4F6;
}
.renew-title {
  font-size: 13px;
  font-weight: 600;
}
</style>
