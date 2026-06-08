<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑美食记录' : '添加美食记录'"
    width="680px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      label-position="left"
      size="default"
    >
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="美食名称" prop="name">
            <el-input v-model="form.name" placeholder="请输入店铺名称" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="城市" prop="city">
            <el-input v-model="form.city" placeholder="市" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="省份" prop="province">
            <el-input v-model="form.province" placeholder="省" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="美味等级" prop="taste_level">
            <el-radio-group v-model="form.taste_level">
              <el-radio-button
                v-for="item in tasteLevels"
                :key="item.value"
                :value="item.value"
                :style="{ color: item.color }"
              >
                {{ item.icon }} {{ item.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="美食分类" prop="category">
            <el-select v-model="form.category" placeholder="选择分类" style="width: 100%">
              <el-option
                v-for="item in CATEGORY_OPTIONS"
                :key="item.value"
                :label="`${item.icon} ${item.label}`"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="菜品名称" prop="dish_name">
            <el-input v-model="form.dish_name" placeholder="选填" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="具体位置" prop="location">
        <el-input v-model="form.location" placeholder="详细地址（选填）" />
      </el-form-item>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="食用日期" prop="eat_date">
            <el-date-picker
              v-model="form.eat_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="评分" prop="rating">
            <el-rate v-model="form.rating" :max="5" allow-half />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="花费" prop="price">
            <el-input-number v-model="form.price" :min="0" :precision="2" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="还想再去" prop="want_visit_again">
            <el-switch v-model="form.want_visit_again" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="标签" prop="tags">
        <el-input v-model="form.tags" placeholder="逗号分隔，如：火锅, 辣, 推荐" />
      </el-form-item>

      <el-form-item label="备注" prop="notes">
        <el-input
          v-model="form.notes"
          type="textarea"
          :rows="2"
          placeholder="补充说明..."
          maxlength="500"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="图片">
        <el-upload
          ref="uploadRef"
          :action="uploadAction"
          :headers="uploadHeaders"
          :on-success="handleUploadSuccess"
          :on-remove="handleUploadRemove"
          :file-list="fileList"
          :multiple="true"
          :limit="9"
          list-type="picture-card"
          accept="image/*"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存修改' : '添加记录' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import type { FormInstance, UploadUserFile } from 'element-plus'
import {
  CATEGORY_OPTIONS, TASTE_LEVELS,
} from '../types/foodTypes'
import type { FoodFormData, FoodRecord } from '../types/foodTypes'
// import { getToken } from '@/shared/utils/auth'

const props = defineProps<{
  modelValue: boolean
  record?: FoodRecord | null
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [data: FoodFormData]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const isEdit = computed(() => !!props.record)

const formRef = ref<FormInstance>()
const uploadRef = ref()

const tasteLevels = Object.entries(TASTE_LEVELS).map(([value, config]) => ({
  value,
  ...config,
}))

const form = ref<FoodFormData>({
  name: '',
  dish_name: '',
  category: '',
  province: '',
  city: '',
  location: '',
  taste_level: 'good',
  eat_date: '',
  rating: undefined,
  price: undefined,
  notes: '',
  tags: '',
  want_visit_again: false,
  images: [],
})

const fileList = ref<UploadUserFile[]>([])

const uploadAction = `${import.meta.env.VITE_API_BASE_URL || ''}/api/food/upload/`
const uploadHeaders = { 'Accept': 'application/json' }

const rules = {
  name: [{ required: true, message: '请输入美食名称', trigger: 'blur' }],
  city: [{ required: true, message: '请输入城市', trigger: 'blur' }],
  taste_level: [{ required: true, message: '请选择美味等级', trigger: 'change' }],
}

function resetForm() {
  form.value = {
    name: '',
    dish_name: '',
    category: '',
    province: '',
    city: '',
    location: '',
    taste_level: 'good',
    eat_date: '',
    rating: undefined,
    price: undefined,
    notes: '',
    tags: '',
    want_visit_again: false,
    images: [],
  }
  fileList.value = []
}

watch(() => props.record, (record) => {
  if (record) {
    form.value = {
      name: record.name,
      dish_name: record.dish_name || '',
      category: record.category || '',
      province: record.province || '',
      city: record.city || '',
      location: record.location || '',
      taste_level: record.taste_level || 'good',
      eat_date: record.eat_date || '',
      rating: record.rating ?? undefined,
      price: record.price ?? undefined,
      notes: record.notes || '',
      tags: record.tags || '',
      want_visit_again: record.want_visit_again ?? false,
      images: record.images || [],
    }
    fileList.value = (record.images || []).map((url: string, i: number) => ({
      name: `image-${i}`,
      url,
    }))
  } else {
    resetForm()
  }
}, { immediate: true })

function handleUploadSuccess(response: { url: string }) {
  if (response.url) {
    if (!form.value.images) form.value.images = []
    form.value.images.push(response.url)
  }
}

function handleUploadRemove(_file: UploadUserFile, fileList_: UploadUserFile[]) {
  form.value.images = fileList_.map(f => f.url).filter(Boolean) as string[]
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  emit('submit', { ...form.value })
}

function handleClose() {
  formRef.value?.resetFields()
  resetForm()
}
</script>

<style scoped lang="scss">
.el-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;

  :deep(.el-radio-button) {
    .el-radio-button__inner {
      border: 1px solid #E5E7EB;
      border-radius: 6px !important;
      padding: 6px 12px;
      font-size: 13px;
      white-space: nowrap;
    }

    &.is-active .el-radio-button__inner {
      border-color: currentColor;
      box-shadow: none;
    }
  }
}
</style>
