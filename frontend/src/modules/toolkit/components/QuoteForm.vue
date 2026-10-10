<template>
  <el-dialog v-model="dialogVisible" :title="editing ? '编辑摘录' : '添加摘录'" width="560px" :close-on-click-modal="false" @closed="handleClose">
    <el-form :model="form" label-width="100px">
      <el-form-item label="类型">
        <el-radio-group v-model="form.is_paragraph">
          <el-radio :value="false">短句</el-radio>
          <el-radio :value="true">段落</el-radio>
        </el-radio-group>
        <span class="hint">
          仅作分类标注 —— 「每日金句」卡按<b>长度</b>判定能不能上卡，与类型无关
        </span>
      </el-form-item>

      <el-form-item label="内容" required>
        <el-input v-model="form.content" type="textarea" :rows="4" placeholder="名言/段落内容" />
        <div class="length-hint" :class="{ 'is-over': isOverPoolLimit }">{{ poolHint }}</div>
      </el-form-item>

      <el-form-item v-if="form.is_paragraph" label="缩减标题">
        <el-input v-model="form.short_title" placeholder="给自己的检索标注（可留空）" maxlength="100" show-word-limit />
        <span class="hint">
          仅作你自己的标注 —— 首页金句卡现在显示全文，不再用它做折叠标题
        </span>
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
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { LANGUAGE_OPTIONS } from '../types/quoteTypes'
import type { Quote, QuoteFormData } from '../types/quoteTypes'
import { createQuote, updateQuote } from '../api/quoteApi'
import { getPresetByType } from '@/shared/api/coreApi'
import { getProfile } from '@/core/privacy/api/privacyApi'

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

const presetTags = ref<string[]>([])
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

// ─── 金句池长度提示（v3.60.12）───
// 上限来自「系统管理 → 系统设置」里的配置。`null` = 还没读到 ⇒ **不提示长短**，
// 而不是拿一个写死的数字冒充当前配置。
const poolMaxLen = ref<number | null>(null)

/** 与后端池子同口径：MySQL `CHAR_LENGTH(content)` == Python `len(content)` == 这里的 .length */
const contentLen = computed(() => form.content.length)

const isOverPoolLimit = computed(
  () => poolMaxLen.value !== null && contentLen.value > poolMaxLen.value,
)

/**
 * 长度提示：**只提示，不阻止保存**。
 *
 * 用户原话是「长度应该在录入时进行提示」—— 门槛本身没问题，问题是以前它
 * 既不显示也不能改，写的时候根本不知道这条摘录将来会不会被首页卡片抽到。
 */
const poolHint = computed(() => {
  if (poolMaxLen.value === null) return `共 ${contentLen.value} 字`
  const limit = poolMaxLen.value
  if (contentLen.value === 0) return `共 0 字 · 上限 ${limit} 字`
  if (isOverPoolLimit.value) {
    return `共 ${contentLen.value} 字 · 超过上限 ${limit} 字，不会出现在「每日金句」卡上（仍会存进摘录）`
  }
  return `共 ${contentLen.value} 字 · 在「每日金句」的取句范围内（上限 ${limit} 字）`
})

async function loadPoolConfig() {
  try {
    const res = await getProfile()
    const v = res.data.quote_pool_max_len
    poolMaxLen.value = typeof v === 'number' ? v : null
  } catch {
    poolMaxLen.value = null // 读不到就不提示，别编一个数字
  }
}

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
    loadPoolConfig()
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

async function loadPresetTags() {
  try {
    const res = await getPresetByType('tags')
    presetTags.value = res.data.values || []
  } catch {
    presetTags.value = []
  }
}

onMounted(loadPresetTags)

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
.length-hint { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; line-height: 1.5; }
/* 超限用暖色提醒，但**不标红** —— 这不是错误，只是不会有首页卡片的机会 */
.length-hint.is-over { color: #E6A23C; }
.tags-wrapper {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
}
.preset-label { font-size: 12px; color: #999; }
.preset-tag { cursor: pointer; transition: all 0.2s; }
.preset-tag:hover { opacity: 0.8; }
.preset-tag.selected { background: #ecf5ff; border-color: #409eff; color: #409eff; }
.custom-tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
</style>
