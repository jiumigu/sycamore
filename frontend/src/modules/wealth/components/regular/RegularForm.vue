<template>
  <el-dialog
    :model-value="visible"
    :title="editing ? '编辑定期存款' : '新增定期存款'"
    width="520px"
    @update:model-value="$emit('update:visible', $event)"
    @open="handleOpen"
    :close-on-click-modal="false"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px" size="small">
      <el-form-item label="银行" prop="bankinfo">
        <el-select v-model="form.bankinfo" placeholder="选择银行" filterable allow-create style="width: 100%">
          <el-option v-for="b in banks" :key="b" :label="b" :value="b" />
        </el-select>
      </el-form-item>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="存款金额" prop="value">
            <el-input v-model.number="form.value" type="number" min="0" step="0.01">
              <template #append>元</template>
            </el-input>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="年利率" prop="rate">
            <el-input v-model.number="form.rate" type="number" min="0" step="0.01">
              <template #append>%</template>
            </el-input>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="存入日期" prop="begin_date">
            <el-date-picker v-model="form.begin_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="到期日期" prop="end_date">
            <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="100" show-word-limit />
      </el-form-item>

      <el-form-item label="状态">
        <el-select v-model="form.flag" style="width: 100%">
          <el-option :label="'未到期'" :value="0" />
          <el-option :label="'已到期'" :value="1" />
          <el-option :label="'已取出'" :value="2" />
        </el-select>
      </el-form-item>

      <!-- 利息预览 -->
      <el-card v-if="showInterestPreview" shadow="none" class="preview-card">
        <div class="preview-row">
          <span>预计利息</span>
          <span class="preview-value">{{ previewInterest }} 元</span>
        </div>
        <div class="preview-row">
          <span>本息合计</span>
          <span class="preview-value">{{ previewTotal }} 元</span>
        </div>
      </el-card>
    </el-form>

    <template #footer>
      <el-button size="small" @click="$emit('update:visible', false)">取消</el-button>
      <el-button size="small" type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import type { RegularItem } from '../../types/wealthTypes'

const props = defineProps<{
  visible: boolean
  editing: RegularItem | null
  banks: string[]
  saving: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [data: Record<string, unknown>]
}>()

const formRef = ref<FormInstance>()

const form = reactive({
  bankinfo: '',
  value: null as number | null,
  rate: null as number | null,
  begin_date: '',
  end_date: '',
  remark: '',
  flag: 0,
})

const rules = {
  bankinfo: [{ required: true, message: '请选择银行', trigger: 'change' }],
  value: [{ required: true, message: '请输入存款金额', trigger: 'blur' }],
  begin_date: [{ required: true, message: '请选择存入日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择到期日期', trigger: 'change' }],
}

const showInterestPreview = computed(() =>
  form.value && form.rate && form.begin_date && form.end_date
)

const previewInterest = computed(() => {
  if (!form.value || !form.rate || !form.begin_date || !form.end_date) return '0.00'
  const begin = new Date(form.begin_date)
  const end = new Date(form.end_date)
  const days = (end.getTime() - begin.getTime()) / (1000 * 86400)
  if (days <= 0) return '0.00'
  const interest = form.value * (form.rate / 100) * (days / 365)
  return interest.toFixed(2)
})

const previewTotal = computed(() => {
  if (!form.value) return '0.00'
  return (form.value + parseFloat(previewInterest.value)).toFixed(2)
})

function handleOpen() {
  if (props.editing) {
    form.bankinfo = props.editing.bankinfo || ''
    form.value = props.editing.value
    form.rate = props.editing.rate
    form.begin_date = props.editing.begin_date
    form.end_date = props.editing.end_date
    form.remark = props.editing.remark || ''
    form.flag = props.editing.flag
  } else {
    form.bankinfo = ''
    form.value = null
    form.rate = null
    form.begin_date = ''
    form.end_date = ''
    form.remark = ''
    form.flag = 0
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  emit('save', { ...form })
}
</script>

<style scoped>
.preview-card {
  background: #F0F9FF;
  border: 1px solid #BAE6FD;
  border-radius: 8px;
  margin-top: 8px;
}
.preview-card :deep(.el-card__body) {
  padding: 10px 14px;
}
.preview-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 2px 0;
  color: var(--el-text-color-secondary);
}
.preview-value {
  font-weight: 600;
  color: #059669;
}
</style>
