<template>
  <div class="snapshot-form">
    <div class="snapshot-form__header">
      <h3>资产盘点录入</h3>
      <div class="snapshot-form__actions">
        <el-button size="small" @click="handleCopy" :loading="copyLoading">复制上月</el-button>
      </div>
    </div>

    <el-form :model="form" label-width="80px" size="small">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="年月">
            <el-input v-model="form.yearmon" placeholder="YYYY-MM" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="盘点日期">
            <el-date-picker v-model="form.btime" type="date" value-format="YYYY-MM-DD" style="width:100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="支付宝">
            <el-input-number v-model="form.zplay" :precision="2" :min="0" :step="1000" style="width:100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="微信">
            <el-input-number v-model="form.wechat" :precision="2" :min="0" :step="1000" style="width:100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="现金">
            <el-input-number v-model="form.cash" :precision="2" :min="0" :step="500" style="width:100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="建行">
            <el-input-number v-model="form.jianbank" :precision="2" :min="0" :step="10000" style="width:100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="工行">
            <el-input-number v-model="form.gongbank" :precision="2" :min="0" :step="10000" style="width:100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="中国银行">
            <el-input-number v-model="form.zhongbank" :precision="2" :min="0" :step="10000" style="width:100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="农信社">
            <el-input-number v-model="form.nongbank" :precision="2" :min="0" :step="10000" style="width:100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="公积金">
            <el-input-number v-model="form.accumulationfund" :precision="2" :min="0" :step="10000" style="width:100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="负债">
            <el-input-number v-model="form.borrow" :precision="2" :min="0" :step="10000" style="width:100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="借出">
            <el-input-number v-model="form.lend" :precision="2" :min="0" :step="10000" style="width:100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="24">
          <el-form-item label="备注">
            <el-input v-model="form.remarks" placeholder="可选" type="textarea" :rows="2" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <div class="snapshot-form__submit">
      <el-button type="primary" :loading="saving" @click="handleSave">
        {{ editing ? '更新' : '保存' }}盘点
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

const props = withDefaults(defineProps<{
  saving?: boolean
  copyLoading?: boolean
  editing?: boolean
  initialData?: {
    yearmon?: string
    btime?: string | null
    zplay?: number
    wechat?: number
    cash?: number
    jianbank?: number
    gongbank?: number
    zhongbank?: number
    nongbank?: number
    accumulationfund?: number
    lend?: number
    borrow?: number
    remarks?: string
  } | null
}>(), {
  saving: false, copyLoading: false, editing: false,
})

const emit = defineEmits<{
  save: [data: Record<string, unknown>]
  copy: []
}>()

const form = reactive({
  yearmon: '',
  btime: '',
  zplay: 0,
  wechat: 0,
  cash: 0,
  jianbank: 0,
  gongbank: 0,
  zhongbank: 0,
  nongbank: 0,
  accumulationfund: 0,
  lend: 0,
  borrow: 0,
  remarks: '',
})

watch(() => props.initialData, (val) => {
  if (val) {
    Object.assign(form, {
      yearmon: val.yearmon ?? '',
      btime: val.btime ?? '',
      zplay: val.zplay ?? 0,
      wechat: val.wechat ?? 0,
      cash: val.cash ?? 0,
      jianbank: val.jianbank ?? 0,
      gongbank: val.gongbank ?? 0,
      zhongbank: val.zhongbank ?? 0,
      nongbank: val.nongbank ?? 0,
      accumulationfund: val.accumulationfund ?? 0,
      lend: val.lend ?? 0,
      borrow: val.borrow ?? 0,
      remarks: val.remarks ?? '',
    })
  }
}, { immediate: true })

function handleSave() {
  emit('save', { ...form })
}

function handleCopy() {
  emit('copy')
}
</script>

<style scoped>
.snapshot-form__header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;
}
.snapshot-form__header h3 {
  margin: 0; font-size: 16px; font-weight: 600;
}
.snapshot-form__submit {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
