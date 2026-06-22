<template>
  <el-dialog v-model="dialogVisible" :title="editing ? '编辑摘录' : '添加摘录'" width="560px" :close-on-click-modal="false" @closed="handleClose">
    <el-form :model="form" label-width="100px">
      <el-form-item label="类型">
        <el-radio-group v-model="form.is_paragraph">
          <el-radio :value="false">短句</el-radio>
          <el-radio :value="true">段落</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="内容" required>
        <el-input v-model="form.content" type="textarea" :rows="4" placeholder="名言/段落内容" />
      </el-form-item>

      <el-form-item v-if="form.is_paragraph" label="缩减标题">
        <el-input v-model="form.short_title" placeholder="段落太长时显示此标题，点击展开全文" maxlength="100" show-word-limit />
        <span class="hint">仪表盘卡片中显示此标题</span>
      </el-form-item>

      <el-form-item label="作者/出处">
        <el-input v-model="form.author" placeholder="鲁迅 / 《活着》/ 佚名" />
      </el-form-item>

      <el-form-item label="语言">
        <el-select v-model="form.language" style="width:100%">
          <el-option v-for="l in LANGUAGE_OPTIONS" :key="l.value" :label="l.label" :value="l.value" />
        </el-select>
      </el-form-item>

      <el-form-item label="来源">
        <el-input v-model="form.source" placeholder="书/电影/播客/偶然看到" />
      </el-form-item>

      <el-form-item label="标签">
        <div class="tags-wrapper">
          <span class="preset-label">常用标签：</span>
          <el-tag
            v-for="tag in presetTags" :key="tag"
            :class="{ selected: tagList.includes(tag) }"
            class="preset-tag"
            @click="togglePresetTag(tag)"
            size="small"
          >
            {{ tag }}
          </el-tag>
          <div class="custom-tags">
            <el-tag
              v-for="tag in tagList.filter(t => !presetTags.includes(t))" :key="tag"
              closable @close="removeTag(tag)"
              size="small" type="warning"
            >
              {{ tag }}
            </el-tag>
            <el-input v-if="showTagInput" ref="tagInputRef" v-model="newTag" size="small" style="width:80px" @keyup.enter="addTag" @blur="addTag" />
            <el-button v-else size="small" @click="showTagInput = true">+ 自定义</el-button>
          </div>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { LANGUAGE_OPTIONS } from '../types/quoteTypes'
import type { Quote, QuoteFormData } from '../types/quoteTypes'
import { createQuote, updateQuote } from '../api/quoteApi'

const props = defineProps<{
  visible: boolean
  quote: Quote | null
}>()

const emit = defineEmits<{
  'update:visible': [v: boolean]
  saved: []
}>()

const dialogVisible = ref(false)
const submitting = ref(false)
const editing = ref(false)

const presetTags = ['励志', '人生感悟', '写作', '成长', '情感', '职场', '哲思', '幽默', '治愈', '自律']
const tagList = ref<string[]>([])
const showTagInput = ref(false)
const newTag = ref('')
const tagInputRef = ref()

const form = reactive<QuoteFormData>({
  content: '',
  author: '',
  language: '中文',
  category: '',
  is_paragraph: false,
  short_title: '',
  source: '',
  tags: '',
})

function togglePresetTag(tag: string) {
  const idx = tagList.value.indexOf(tag)
  if (idx > -1) {
    tagList.value.splice(idx, 1)
  } else {
    tagList.value.push(tag)
  }
}

function removeTag(tag: string) {
  tagList.value = tagList.value.filter(t => t !== tag)
}

function addTag() {
  const t = newTag.value.trim()
  if (t && !tagList.value.includes(t)) {
    tagList.value.push(t)
  }
  newTag.value = ''
  showTagInput.value = false
}

watch(() => props.visible, (v) => {
  dialogVisible.value = v
  if (v) {
    editing.value = !!props.quote
    if (props.quote) {
      form.content = props.quote.content
      form.author = props.quote.author
      form.language = props.quote.language
      form.category = props.quote.category
      form.is_paragraph = props.quote.is_paragraph
      form.short_title = props.quote.short_title
      form.source = props.quote.source
      form.tags = props.quote.tags
      tagList.value = props.quote.tags ? props.quote.tags.split(',').filter(Boolean) : []
    } else {
      handleClose()
    }
  }
})

watch(dialogVisible, (v) => emit('update:visible', v))

function handleClose() {
  form.content = ''
  form.author = ''
  form.language = '中文'
  form.category = ''
  form.is_paragraph = false
  form.short_title = ''
  form.source = ''
  form.tags = ''
  tagList.value = []
  showTagInput.value = false
  newTag.value = ''
}

async function handleSubmit() {
  if (!form.content.trim()) {
    ElMessage.warning('请输入内容')
    return
  }
  submitting.value = true
  form.tags = tagList.value.join(',')
  try {
    if (editing.value && props.quote) {
      await updateQuote(props.quote.id, form)
    } else {
      await createQuote(form)
    }
    ElMessage.success(editing.value ? '摘录已更新' : '摘录已添加')
    dialogVisible.value = false
    emit('saved')
  } catch {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.hint { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 4px; display: block; }
.tags-wrapper {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
}
.preset-label { font-size: 12px; color: #999; }
.preset-tag { cursor: pointer; transition: all 0.2s; }
.preset-tag:hover { opacity: 0.8; }
.preset-tag.selected { background: #ecf5ff; border-color: #409eff; color: #409eff; }
.custom-tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
</style>
