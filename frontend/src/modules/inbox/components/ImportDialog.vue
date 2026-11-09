<template>
  <el-dialog title="📥 批量导入待办" v-model="visible" width="520px" @close="handleClose">
    <div class="import-content">
      <div class="import-hint">
        <p><strong>支持格式：</strong></p>
        <ul>
          <li><strong>CSV</strong>：content / category / due_date / status / priority / tags 列（兼容 title、target_date、note 与中文列名）。category 写类别（待办/想法/学习…），备考阶段另写「阶段」列；两列都会进标签</li>
          <li><strong>Markdown</strong>：任务列表 <code>- [ ] 任务名</code>，行尾 <code>(2026-09-01)</code> 识别为截止日期</li>
          <li><strong>纯文本</strong>：每行一个任务</li>
        </ul>
        <el-button text type="primary" @click="downloadTemplate">📄 下载 CSV 模板</el-button>
      </div>

      <el-upload
        ref="uploadRef"
        action="#"
        :auto-upload="false"
        :on-change="handleFileChange"
        :on-remove="handleRemove"
        :file-list="fileList"
        drag
        accept=".csv,.md,.txt"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">拖拽文件到此处，或点击上传</div>
        <div class="upload-hint">支持 .csv / .md / .txt</div>
      </el-upload>

      <div v-if="previewItems.length > 0" class="preview">
        <div class="preview-header">
          <span>📋 预览 ({{ previewItems.length }} 项)</span>
          <el-tag size="small" type="success">可导入</el-tag>
        </div>
        <div class="preview-list">
          <div v-for="(item, idx) in previewItems.slice(0, 10)" :key="idx" class="preview-item">
            <span class="preview-index">{{ idx + 1 }}</span>
            <span class="preview-title">{{ item.content }}</span>
            <span v-if="item.due_date" class="preview-date">{{ item.due_date }}</span>
          </div>
          <div v-if="previewItems.length > 10" class="preview-more">
            还有 {{ previewItems.length - 10 }} 项...
          </div>
        </div>
      </div>

      <!-- 失败清单：行号 + 原因。只说「失败 2 条」用户无法定位是哪两行 -->
      <div v-if="failedRows.length > 0" class="fail-list">
        <div class="fail-header">
          {{ failedRows.length }} 行未导入
        </div>
        <div v-for="(f, idx) in failedRows.slice(0, 20)" :key="idx" class="fail-item">
          <span class="fail-row">第 {{ f.row ?? '—' }} 行</span>
          <span class="fail-content">{{ f.content || '（空行）' }}</span>
          <span class="fail-reason">{{ f.reason || f.error }}</span>
        </div>
        <div v-if="failedRows.length > 20" class="fail-more">
          还有 {{ failedRows.length - 20 }} 行…
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        type="primary"
        @click="confirmImport"
        :loading="importing"
        :disabled="previewItems.length === 0"
      >
        确认导入 ({{ previewItems.length }} 项)
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { importInboxItems } from '../api/inboxApi'
import type { ImportFailure } from '../types/inboxTypes'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success', count: number): void
}>()

interface PreviewItem {
  content: string
  due_date: string | null
}

const visible = ref(false)
const importing = ref(false)
const fileList = ref<Array<{ name: string; raw?: File }>>([])
const previewItems = ref<PreviewItem[]>([])
const uploadedFile = ref<File | null>(null)
/** 上一次导入里没进来的行（解析跳过 + 入库失败），带行号 */
const failedRows = ref<ImportFailure[]>([])

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  },
)

const handleClose = () => {
  emit('update:modelValue', false)
  resetForm()
}

const resetForm = () => {
  fileList.value = []
  previewItems.value = []
  failedRows.value = []
  uploadedFile.value = null
}

const handleFileChange = (file: { name: string; raw?: File }) => {
  if (file.raw) {
    uploadedFile.value = file.raw
    parsePreview(file.raw)
  }
}

const handleRemove = () => {
  resetForm()
}

/** 前端简单解析用于预览，实际导入以后端解析为准 */
const parsePreview = async (file: File) => {
  const text = await file.text()
  const name = file.name.toLowerCase()

  if (name.endsWith('.md')) {
    const items: PreviewItem[] = []
    for (const line of text.split('\n')) {
      const match = line.match(/^\s*-\s*\[[ xX]\]\s*(.+)$/)
      if (!match) continue
      let title = match[1].trim()
      const dateMatch = title.match(/\((\d{4}-\d{2}-\d{2})\)\s*$/)
      let due: string | null = null
      if (dateMatch) {
        due = dateMatch[1]
        title = title.slice(0, dateMatch.index).trim()
      }
      if (title) items.push({ content: title, due_date: due })
    }
    previewItems.value = items
  } else if (name.endsWith('.csv')) {
    // 简单取首列（兼容 content/title 列名）
    const items: PreviewItem[] = []
    const lines = text.split('\n')
    lines.forEach((line, idx) => {
      if (idx === 0) return
      const first = line.split(',')[0]?.trim()
      if (first) items.push({ content: first, due_date: null })
    })
    previewItems.value = items
  } else {
    previewItems.value = text
      .split('\n')
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith('#') && !l.startsWith('---'))
      .map((l) => ({ content: l, due_date: null }))
  }
}

const downloadTemplate = () => {
  const blob = new Blob(
    ['content,category,due_date,status,priority,tags,阶段\n软件工程基础,学习,2026-08-25,待处理,高,备考,基础期\n'],
    { type: 'text/csv' },
  )
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'inbox_import_template.csv'
  a.click()
  URL.revokeObjectURL(url)
}

const confirmImport = async () => {
  if (!uploadedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadedFile.value)

    const res = await importInboxItems(formData)
    const data = res.data
    failedRows.value = data.failed ?? []
    if (data.success) {
      ElMessage.success(`成功导入 ${data.success_count} 项待办`)
      emit('success', data.success_count)
      visible.value = false
      resetForm()
    } else {
      // 部分成功也要刷新列表：已经入库的那几条不能等到下次进页面才出现
      if (data.success_count > 0) emit('success', data.success_count)
      ElMessage.warning(
        `成功 ${data.success_count} 项，${data.failed_count} 行未导入（明细见下方清单）`,
      )
    }
  } catch {
    ElMessage.error('导入失败，请检查文件格式')
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.import-content {
  .import-hint {
    padding: 12px 16px;
    background: var(--el-fill-color-light);
    border-radius: 6px;
    margin-bottom: 16px;

    p {
      margin: 0 0 4px;
    }

    ul {
      margin: 4px 0 8px 20px;
      font-size: 13px;
      color: var(--el-text-color-secondary);

      code {
        background: var(--el-bg-color);
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 12px;
      }
    }
  }

  .upload-icon {
    font-size: 40px;
    color: var(--el-text-color-secondary);
  }

  .upload-text {
    font-size: 14px;
    color: var(--el-text-color-primary);
    margin-top: 8px;
  }

  .upload-hint {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .preview {
    margin-top: 16px;
    border: 1px solid var(--el-border-color-light);
    border-radius: 6px;
    overflow: hidden;

    .preview-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      background: var(--el-fill-color-light);
      font-size: 13px;
    }

    .preview-list {
      max-height: 200px;
      overflow-y: auto;
      padding: 4px 12px;

      .preview-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 0;
        font-size: 13px;
        border-bottom: 1px solid var(--el-border-color-light);

        .preview-index {
          color: var(--el-text-color-secondary);
          font-size: 12px;
          min-width: 24px;
        }

        .preview-title {
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .preview-date {
          font-size: 12px;
          color: var(--el-text-color-secondary);
        }
      }

      .preview-more {
        padding: 8px 0;
        color: var(--el-text-color-secondary);
        font-size: 13px;
        text-align: center;
      }
    }
  }

  .fail-list {
    margin-top: 12px;
    border: 1px solid var(--el-color-warning-light-5);
    border-radius: 6px;
    overflow: hidden;

    .fail-header {
      padding: 8px 12px;
      background: var(--el-color-warning-light-9);
      color: var(--el-color-warning-dark-2);
      font-size: 13px;
    }

    .fail-item {
      display: flex;
      gap: 8px;
      padding: 4px 12px;
      font-size: 12px;
      border-top: 1px solid var(--el-border-color-lighter);

      .fail-row {
        color: var(--el-text-color-secondary);
        min-width: 56px;
      }

      .fail-content {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .fail-reason {
        color: var(--el-color-danger);
        max-width: 180px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .fail-more {
      padding: 6px 12px;
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }
}
</style>
