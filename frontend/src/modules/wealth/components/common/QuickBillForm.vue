<template>
  <el-form :model="form" label-position="top" size="small" ref="formRef">
    <el-row :gutter="12">
      <el-col :span="12">
        <el-form-item label="交易类型" :rules="[{ required: true, message: '请选择类型' }]">
          <el-radio-group v-model="form.transaction_type">
            <el-radio value="收入">收入</el-radio>
            <el-radio value="支出">支出</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="金额" :rules="[{ required: true, message: '请输入金额' }]">
          <el-input-number
            v-model="form.amount"
            :min="0.01"
            :precision="2"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :span="12">
        <el-form-item label="分类">
          <el-select v-model="form.category" filterable allow-create style="width: 100%">
            <el-option
              v-for="cat in categories"
              :key="cat"
              :label="cat"
              :value="cat"
            />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="子分类">
          <el-input v-model="form.subcategory" placeholder="可选" />
        </el-form-item>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-form-item label="账户">
          <el-input v-model="form.account" placeholder="可选" />
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item label="商家">
          <el-input v-model="form.merchant" placeholder="可选" />
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item label="项目">
          <el-input v-model="form.project" placeholder="可选" />
        </el-form-item>
      </el-col>
    </el-row>

    <el-form-item label="备注">
      <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="可选" />
    </el-form-item>

    <div class="quick-bill__actions">
      <el-button @click="$emit('cancel')">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        保存
      </el-button>
    </div>
  </el-form>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { BillCreateData } from '../../types/wealthTypes'

const emit = defineEmits<{
  submit: [data: BillCreateData]
  cancel: []
}>()

const props = withDefaults(defineProps<{
  defaultDate?: string | null
  submitting?: boolean
}>(), {
  submitting: false,
})

const categories = [
  '餐饮', '交通', '购物', '居住', '娱乐',
  '医疗', '教育', '人情', '服饰', '日用品',
  '通讯', '金融', '工资', '兼职', '投资',
  '礼金', '其他',
]

const form = reactive<BillCreateData>({
  transaction_type: '支出',
  amount: 0,
  category: '',
  subcategory: '',
  project: '',
  account: '',
  merchant: '',
  notes: '',
  date: props.defaultDate || new Date().toISOString().slice(0, 10),
})

function handleSubmit() {
  if (!form.transaction_type) return
  if (form.amount <= 0) return
  emit('submit', { ...form })
}
</script>

<style scoped lang="scss">
.quick-bill__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
