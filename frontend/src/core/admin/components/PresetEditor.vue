<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="560px"
    destroy-on-close
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="preset-editor">
      <div class="preset-values">
        <el-tag
          v-for="(item, idx) in localValues"
          :key="`${item}-${idx}`"
          closable
          size="small"
          :type="tagType"
          @close="removeValue(idx)"
        >
          {{ item }}
        </el-tag>
        <span v-if="!localValues.length" class="empty">暂无内容，请在下方添加</span>
      </div>

      <div class="add-row">
        <el-input
          v-model="newValue"
          size="small"
          :placeholder="placeholder"
          style="width: 220px"
          maxlength="30"
          @keyup.enter="addValue"
        />
        <el-button size="small" type="primary" plain @click="addValue">添加</el-button>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { savePresetByType } from '@/shared/api/coreApi'

const props = defineProps<{
  visible: boolean
  presetType: string
  values: string[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'saved'): void
}>()

const localValues = ref<string[]>([])
const newValue = ref('')
const saving = ref(false)

const isPhrases = computed(() => props.presetType === 'quick_phrases')
const title = computed(() => (isPhrases.value ? '编辑快捷短语' : '编辑预设标签'))
const placeholder = computed(() => (isPhrases.value ? '输入一条短语...' : '输入一个标签...'))
const tagType = computed(() => (isPhrases.value ? 'primary' : 'warning'))

watch(() => props.visible, (v) => {
  if (v) {
    localValues.value = [...props.values]
    newValue.value = ''
  }
})

function addValue() {
  const t = newValue.value.trim()
  if (!t) return
  if (!localValues.value.includes(t)) {
    localValues.value.push(t)
  }
  newValue.value = ''
}

function removeValue(idx: number) {
  localValues.value.splice(idx, 1)
}

async function handleSave() {
  const cleaned = localValues.value.map(t => t.trim()).filter(Boolean)
  if (!cleaned.length) {
    ElMessage.warning('至少保留一项')
    return
  }
  saving.value = true
  try {
    await savePresetByType({ preset_type: props.presetType, values: cleaned })
    ElMessage.success('已保存')
    emit('saved')
    emit('update:visible', false)
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.preset-editor {
  .preset-values {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px;
    min-height: 64px;
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
    margin-bottom: 12px;

    .empty {
      font-size: 13px;
      color: var(--el-text-color-placeholder);
      line-height: 40px;
    }
  }

  .add-row {
    display: flex;
    gap: 8px;
  }
}
</style>
