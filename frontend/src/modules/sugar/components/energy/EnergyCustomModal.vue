<template>
  <el-dialog
    v-model="dialogVisible"
    title="⚡ 自定义能量小事"
    width="480px"
    :close-on-click-modal="false"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="0">
      <div class="form-label">内容 *</div>
      <el-form-item prop="content">
        <el-input v-model="form.content" placeholder="做什么会让你开心？" maxlength="200" />
      </el-form-item>

      <div class="form-label">能量值 *</div>
      <el-form-item prop="default_energy">
        <div class="energy-slider">
          <el-slider
            v-model="form.default_energy"
            :min="1"
            :max="5"
            :marks="{ 1: '+1', 2: '+2', 3: '+3', 4: '+4', 5: '+5' }"
            show-stops
          />
        </div>
      </el-form-item>

      <div class="form-label">分类</div>
      <el-form-item prop="category">
        <div class="category-picker">
          <el-tag
            v-for="cat in categoryOptions"
            :key="cat.value"
            :type="form.category === cat.value ? 'primary' : 'info'"
            effect="plain"
            :hit="form.category === cat.value"
            class="category-tag"
            @click="form.category = cat.value"
          >
            {{ cat.icon }} {{ cat.label }}
          </el-tag>
        </div>
      </el-form-item>

      <div class="form-label">预计耗时</div>
      <el-form-item>
        <el-select v-model="estimatedMinutes" style="width: 100%">
          <el-option :value="1" label="不到1分钟" />
          <el-option :value="2" label="约2分钟" />
          <el-option :value="5" label="约5分钟" />
          <el-option :value="10" label="约10分钟" />
          <el-option :value="30" label="约30分钟" />
          <el-option :value="60" label="约1小时" />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { ElForm } from 'element-plus'

const props = defineProps<{
  visible: boolean
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

const categoryOptions = [
  { value: 'daily', label: '日常', icon: '🌱' },
  { value: 'relax', label: '放松', icon: '🧘' },
  { value: 'creative', label: '创意', icon: '✨' },
  { value: 'social', label: '社交', icon: '💬' },
]

const form = ref({
  content: '',
  default_energy: 2,
  category: 'daily',
})

const estimatedMinutes = ref(2)

const rules = {
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
  default_energy: [{ required: true, message: '请选择能量值', trigger: 'change' }],
}

watch(() => props.visible, (val) => {
  if (val) {
    form.value = { content: '', default_energy: 2, category: 'daily' }
    estimatedMinutes.value = 2
  }
})

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    emit('submit', {
      ...form.value,
      estimated_seconds: estimatedMinutes.value * 60,
      icon: categoryOptions.find(c => c.value === form.value.category)?.icon || '✨',
    })
    dialogVisible.value = false
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.form-label {
  font-size: 13px;
  color: #6B7280;
  margin-bottom: 6px;
  font-weight: 500;
}

.energy-slider {
  padding: 0 12px;
}

.category-picker {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;

  .category-tag {
    cursor: pointer;
    font-size: 13px;
    padding: 0 14px;
  }
}
</style>
