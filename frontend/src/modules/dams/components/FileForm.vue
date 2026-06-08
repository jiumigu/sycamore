<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑文件' : '新增文件'"
    width="600px"
    :close-on-click-modal="false"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="文件名" prop="name">
        <el-input v-model="form.name" placeholder="输入文件名" />
      </el-form-item>
      <el-form-item label="路径" prop="path">
        <el-input v-model="form.path" placeholder="输入完整路径" />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="分类" prop="file_category">
            <el-select v-model="form.file_category" placeholder="选择分类" style="width: 100%">
              <el-option
                v-for="opt in FILE_CATEGORY_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="大小(MB)" prop="file_size_mb">
            <el-input-number v-model="form.file_size_mb" :min="0" :precision="2" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="存储位置" prop="storage_location">
            <el-input v-model="form.storage_location" placeholder="如：本地磁盘/外置硬盘" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="父文件夹" prop="parent_folder">
            <el-input v-model="form.parent_folder" placeholder="父文件夹路径" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="标记">
        <el-checkbox v-model="form.is_duplicate">重复文件</el-checkbox>
        <el-checkbox v-model="form.is_organized" style="margin-left: 16px">已整理</el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存' : '新增' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { ElForm } from 'element-plus'
import { FILE_CATEGORY_OPTIONS } from '../types/damsTypes'
import type { DamsFileResourceList } from '../types/damsTypes'

const props = defineProps<{
  visible: boolean
  file: Partial<DamsFileResourceList> | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'submit', data: Record<string, unknown>): void
}>()

const formRef = ref<InstanceType<typeof ElForm>>()
const submitting = ref(false)

const dialogVisible = computed({
  get: () => props.visible,
  set: (val: boolean) => emit('update:visible', val),
})

const isEdit = computed(() => !!props.file?.id)

const form = ref({
  name: '',
  path: '',
  storage_location: '',
  file_category: '',
  file_size_mb: 0,
  parent_folder: '',
  is_duplicate: false,
  is_organized: false,
})

const rules = {
  name: [{ required: true, message: '请输入文件名', trigger: 'blur' }],
  path: [{ required: true, message: '请输入路径', trigger: 'blur' }],
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      if (props.file) {
        form.value = {
          name: props.file.name || '',
          path: props.file.path || '',
          storage_location: '',
          file_category: props.file.file_category || '',
          file_size_mb: props.file.file_size_mb || 0,
          parent_folder: '',
          is_duplicate: props.file.is_duplicate || false,
          is_organized: props.file.is_organized || false,
        }
      } else {
        form.value = {
          name: '', path: '', storage_location: '', file_category: '',
          file_size_mb: 0, parent_folder: '', is_duplicate: false, is_organized: false,
        }
      }
    }
  },
)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    emit('submit', { ...form.value })
    dialogVisible.value = false
  } finally {
    submitting.value = false
  }
}
</script>
