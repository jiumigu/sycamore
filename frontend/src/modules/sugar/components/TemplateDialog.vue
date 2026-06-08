<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑小确幸模板' : '添加小确幸模板'"
    width="480px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="0">
      <div class="form-label">分类</div>
      <el-form-item prop="category">
        <el-select v-model="form.category" style="width: 100%">
          <el-option v-for="c in categoryOptions" :key="c.value" :label="`${c.icon} ${c.label}`" :value="c.value" />
        </el-select>
      </el-form-item>

      <div class="form-label">图标</div>
      <el-form-item prop="icon">
        <div class="icon-picker">
          <el-input v-model="form.icon" maxlength="4" style="width: 80px" />
          <span class="icon-preview">{{ form.icon }}</span>
          <span class="icon-hint">输入 emoji 或字符</span>
        </div>
      </el-form-item>

      <div class="form-label">名称 *</div>
      <el-form-item prop="name">
        <el-input v-model="form.name" placeholder="给绿植浇水" maxlength="100" show-word-limit />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <div class="form-label">积分</div>
          <el-form-item prop="points">
            <el-input-number v-model="form.points" :min="1" :max="10" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <div class="form-label">时长</div>
          <el-form-item prop="duration">
            <el-select v-model="form.duration" style="width: 100%">
              <el-option value="1分钟" label="1分钟" />
              <el-option value="3分钟" label="3分钟" />
              <el-option value="5分钟" label="5分钟" />
              <el-option value="10分钟" label="10分钟" />
              <el-option value="15分钟" label="15分钟" />
              <el-option value="30分钟" label="30分钟" />
              <el-option value="1小时" label="1小时" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import { SUGAR_TEMPLATE_CATEGORIES } from '../types/sugarTypes'
import type { SugarTemplate } from '../types/sugarTypes'

const props = defineProps<{
  visible: boolean
  template?: SugarTemplate | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'submit', data: Record<string, unknown>): void
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const isEdit = computed(() => !!props.template)

const dialogVisible = computed({
  get: () => props.visible,
  set: (val: boolean) => emit('update:visible', val),
})

const categoryOptions = computed(() =>
  Object.entries(SUGAR_TEMPLATE_CATEGORIES).map(([value, cfg]) => ({
    value,
    label: cfg.label,
    icon: cfg.icon,
  })),
)

const form = reactive({
  category: 'daily',
  icon: '🌱',
  name: '',
  points: 1,
  duration: '1分钟',
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

watch(() => props.visible, (val) => {
  if (val && props.template) {
    form.category = props.template.category
    form.icon = props.template.icon
    form.name = props.template.name
    form.points = props.template.points
    form.duration = props.template.duration
  } else if (val) {
    form.category = 'daily'
    form.icon = '🌱'
    form.name = ''
    form.points = 1
    form.duration = '1分钟'
  }
})

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    emit('submit', { ...form })
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

.icon-picker {
  display: flex;
  align-items: center;
  gap: 12px;

  .icon-preview {
    font-size: 24px;
    line-height: 1;
  }

  .icon-hint {
    font-size: 12px;
    color: #9CA3AF;
  }
}
</style>
