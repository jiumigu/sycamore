<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="800px"
    append-to-body
    :close-on-click-modal="true"
    top="5vh"
  >
    <div v-if="loading" class="logseq-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>
    <div v-else-if="error" class="logseq-error">{{ error }}</div>
    <div v-else class="markdown-body" v-html="renderedContent" />
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { marked } from 'marked'
import { Loading } from '@element-plus/icons-vue'
import { openLogseq } from '../api/temporalApi'

const props = defineProps<{
  modelValue: boolean
  title?: string
  filepath?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const error = ref('')
const rawContent = ref('')

const renderedContent = computed(() => {
  if (!rawContent.value) return ''
  return marked(rawContent.value, {
    breaks: true,
    gfm: true,
  })
})

watch(() => props.filepath, async (path) => {
  if (!path) return
  loading.value = true
  error.value = ''
  rawContent.value = ''

  try {
    const res = await openLogseq(path)
    rawContent.value = res.data.content
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } }; message?: string }
    error.value = '加载失败：' + (err.response?.data?.error || err.message || '未知错误')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="scss">
.logseq-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.logseq-error {
  color: var(--el-color-danger);
  text-align: center;
  padding: 40px 0;
  font-size: 14px;
}

.markdown-body {
  padding: 12px 4px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
  word-break: break-all;
  overflow-wrap: break-word;

  :deep(h1) {
    font-size: 24px;
    margin: 16px 0 12px;
    border-bottom: 1px solid var(--el-border-color-light);
    padding-bottom: 8px;
  }
  :deep(h2) { font-size: 20px; margin: 14px 0 10px; }
  :deep(h3) { font-size: 17px; margin: 12px 0 8px; }
  :deep(h4) { font-size: 15px; margin: 10px 0 6px; }

  :deep(ul), :deep(ol) { padding-left: 24px; margin: 8px 0; }
  :deep(li) { margin: 4px 0; }

  :deep(blockquote) {
    border-left: 4px solid var(--el-color-primary);
    padding: 8px 16px;
    margin: 12px 0;
    background: var(--el-fill-color-light);
    color: var(--el-text-color-regular);
  }

  :deep(code) {
    background: var(--el-fill-color);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 13px;
  }

  :deep(pre) {
    background: var(--el-fill-color-light);
    padding: 12px 16px;
    border-radius: 6px;
    overflow-x: auto;

    code {
      background: none;
      padding: 0;
    }
  }

  :deep(p) { margin: 8px 0; }

  :deep(a) { color: var(--el-color-primary); text-decoration: none; &:hover { text-decoration: underline; } }

  :deep(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;

    th, td {
      border: 1px solid var(--el-border-color);
      padding: 8px 12px;
      text-align: left;
    }
    th { background: var(--el-fill-color-light); }
  }
}
</style>
