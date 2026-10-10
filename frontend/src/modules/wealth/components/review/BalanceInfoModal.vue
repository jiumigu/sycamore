<template>
  <el-dialog
    :model-value="visible"
    :title="isCreate ? '手动录入月度数据' : '编辑复盘数据'"
    width="480px"
    @update:model-value="$emit('close')"
  >
    <el-form v-if="form" label-position="top" size="small">
      <el-form-item label="年月">
        <el-date-picker
          v-if="isCreate"
          v-model="form.yearmon"
          type="month"
          value-format="YYYY-MM"
          placeholder="选择月份"
          style="width:100%"
        />
        <el-input v-else :model-value="form.yearmon" disabled />
      </el-form-item>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="收入">
            <el-input-number v-model="form.income" :min="0" :precision="2" style="width:100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="支出">
            <el-input-number v-model="form.expense" :min="0" :precision="2" style="width:100%" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="每月余额">
        <el-input-number v-model="form.balance" :precision="2" style="width:100%" />
        <div style="font-size:12px;line-height:1.5;margin-top:4px;color:var(--el-text-color-secondary)">
          一般等于「收入 − 支出」。留空按 0 记。
        </div>
      </el-form-item>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="存款余额不在这里录"
        description="已统一到「资产盘点」：按科目盘一次，复盘列表就会自动引到那一期的净资产。"
      />
      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

const props = withDefaults(defineProps<{
  visible: boolean
  isCreate?: boolean
  data: {
    yearmon: string
    income?: number
    expense?: number
    balance?: number | null
    notes?: string
  } | null
  saving?: boolean
}>(), { saving: false, isCreate: false })

const emit = defineEmits<{
  close: []
  save: [data: {
    yearmon: string
    income: number
    expense: number
    balance: number | null
    notes: string
  }]
}>()

// 🔴 刻意**没有** `deposit`：「存款余额」已收口到「资产盘点」，
//    这里再开一个输入框就等于恢复第二个录入口（2026-10-03 退役，见决策稿）。
const form = reactive({
  yearmon: '',
  income: 0,
  expense: 0,
  balance: null as number | null,
  notes: '',
})

watch(() => props.data, (val) => {
  if (val) {
    form.yearmon = val.yearmon
    form.income = val.income ?? 0
    form.expense = val.expense ?? 0
    form.balance = val.balance ?? null
    form.notes = val.notes ?? ''
  }
}, { immediate: true })

function handleSave() {
  emit('save', { ...form })
}
</script>
