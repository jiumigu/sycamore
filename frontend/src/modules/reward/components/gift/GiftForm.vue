<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑礼物' : '添加礼物'"
    width="520px"
    :close-on-click-modal="false"
    @update:model-value="$emit('update:visible', $event)"
    @open="resetForm"
    class="gift-form-dialog"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="90px"
      label-position="left"
      size="default"
    >
      <el-form-item label="礼物名称" prop="name">
        <el-input v-model="form.name" placeholder="输入礼物名称" maxlength="100" />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="参考价格" prop="expected_reward">
            <el-input-number
              v-model="form.expected_reward"
              :min="0"
              :precision="2"
              :step="10"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="分类" prop="category">
            <el-select v-model="form.category" placeholder="选择分类" clearable style="width: 100%">
              <el-option
                v-for="opt in categoryOptions"
                :key="opt.value"
                :label="`${opt.icon} ${opt.label}`"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="优先级" prop="priority">
        <el-slider
          v-model="form.priority"
          :min="0"
          :max="100"
          :step="1"
          show-input
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item label="图片链接" prop="image_url">
        <el-input v-model="form.image_url" placeholder="https://..." clearable />
      </el-form-item>

      <el-form-item label="购买链接" prop="link_url">
        <el-input v-model="form.link_url" placeholder="https://..." clearable />
      </el-form-item>

      <el-form-item label="备注" prop="notes">
        <el-input
          v-model="form.notes"
          type="textarea"
          :rows="3"
          placeholder="为什么想要这个礼物？"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存' : '添加' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { GiftList } from '../../types/rewardTypes'
import { GIFT_CATEGORY_OPTIONS } from '../../types/rewardTypes'

const props = defineProps<{
  visible: boolean
  gift?: GiftList | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: Record<string, unknown>]
}>()

const isEdit = computed(() => !!props.gift?.id)

const categoryOptions = GIFT_CATEGORY_OPTIONS

const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  expected_reward: 0,
  category: null as string | null,
  priority: 50,
  image_url: '',
  link_url: '',
  notes: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入礼物名称', trigger: 'blur' }],
  expected_reward: [{ required: true, message: '请输入参考价格', trigger: 'blur' }],
}

const submitting = ref(false)

function resetForm() {
  if (props.gift) {
    form.name = props.gift.name
    form.expected_reward = props.gift.expected_reward
    form.category = props.gift.category
    form.priority = props.gift.priority
    form.image_url = props.gift.image_url || ''
    form.link_url = props.gift.link_url || ''
    form.notes = props.gift.notes || ''
  } else {
    form.name = ''
    form.expected_reward = 0
    form.category = null
    form.priority = 50
    form.image_url = ''
    form.link_url = ''
    form.notes = ''
  }
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      name: form.name,
      expected_reward: form.expected_reward,
      category: form.category || null,
      priority: form.priority,
      image_url: form.image_url || null,
      link_url: form.link_url || null,
      notes: form.notes || null,
    }
    emit('submit', payload)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.gift-form-dialog {
  :deep(.el-dialog__body) {
    padding-top: 20px;
  }
}
</style>
