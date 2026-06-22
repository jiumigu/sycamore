<template>
  <div class="quote-page">
    <div class="page-header">
      <div class="header-left">
        <h2>💬 摘录管理</h2>
        <el-tag size="small" type="info" effect="plain">名言 · 段落 · 书摘</el-tag>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 添加摘录
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">共收藏</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-value">{{ stats.paragraphs }}</div>
            <div class="stat-label">段落</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-value">{{ stats.shorts }}</div>
            <div class="stat-label">短句</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_reviews }}</div>
            <div class="stat-label">累计回顾</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选区 -->
    <el-card shadow="hover" class="filter-card">
      <div class="filter-row">
        <span class="filter-label">语言</span>
        <el-radio-group v-model="filterLang" size="small" @change="handleFilterChange">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button v-for="l in LANGUAGE_OPTIONS" :key="l.value" :value="l.value">
            {{ l.label }}
          </el-radio-button>
        </el-radio-group>
        <el-divider direction="vertical" />
        <span class="filter-label">标签</span>
        <el-select v-model="filterTag" placeholder="按标签筛选" clearable size="small" style="width:130px" @change="handleFilterChange">
          <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
        </el-select>
      </div>
    </el-card>

    <!-- 摘录列表 -->
    <div v-if="loading" class="loading-state" v-loading="loading" />
    <div v-else-if="!quotes.length" class="empty-state">
      <el-empty description="暂无摘录" :image-size="60" />
    </div>
    <div v-else class="quote-list">
      <div v-for="q in quotes" :key="q.id" class="quote-item">
        <div class="quote-text">{{ q.content }}</div>
        <div class="quote-bottom">
          <span v-if="q.author" class="quote-author">— {{ q.author }}</span>
          <el-tag size="small">{{ q.language }}</el-tag>
          <template v-if="q.tags">
            <el-tag v-for="tag in getTags(q)" :key="tag" size="small" type="info" class="tag-item">
              {{ tag }}
            </el-tag>
          </template>
          <span class="review-count">👁️ {{ q.review_count }} 次回顾</span>
          <div class="quote-actions">
            <el-button size="small" text @click="openEdit(q)">✏️ 编辑</el-button>
            <el-button size="small" text type="danger" @click="handleDelete(q)">🗑️ 删除</el-button>
          </div>
        </div>
      </div>
    </div>

    <el-pagination
      v-if="total > pageSize"
      v-model:current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      small
      style="margin-top:16px;justify-content:center"
      @current-change="fetchQuotes"
    />

    <QuoteForm
      :visible="formVisible"
      :quote="editingQuote"
      @update:visible="formVisible = $event"
      @saved="handleSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { LANGUAGE_OPTIONS } from '../types/quoteTypes'
import type { Quote } from '../types/quoteTypes'
import { getQuoteList, getQuoteStats, deleteQuote } from '../api/quoteApi'
import QuoteForm from '../components/QuoteForm.vue'

const quotes = ref<Quote[]>([])
const loading = ref(false)
const filterLang = ref('')
const filterTag = ref('')

const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const stats = reactive({ total: 0, paragraphs: 0, shorts: 0, total_reviews: 0 })

const formVisible = ref(false)
const editingQuote = ref<Quote | null>(null)

const allTags = computed(() => {
  const tags = new Set<string>()
  quotes.value.forEach(q => {
    if (q.tags) q.tags.split(',').forEach(t => tags.add(t.trim()))
  })
  return Array.from(tags).sort()
})

function getTags(q: Quote) {
  return q.tags ? q.tags.split(',').filter(Boolean) : []
}

function handleFilterChange() {
  currentPage.value = 1
  fetchQuotes()
}

function openCreate() {
  editingQuote.value = null
  formVisible.value = true
}

function openEdit(q: Quote) {
  editingQuote.value = q
  formVisible.value = true
}

async function fetchQuotes() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (filterLang.value) params.language = filterLang.value
    if (filterTag.value) params.tags = filterTag.value
    const res = await getQuoteList(params)
    quotes.value = (res.data?.results || []) as Quote[]
    total.value = res.data?.count ?? 0
  } catch {
    quotes.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await getQuoteStats()
    Object.assign(stats, res.data || {})
  } catch {
    stats.total = 0
    stats.paragraphs = 0
    stats.shorts = 0
    stats.total_reviews = 0
  }
}

async function handleDelete(q: Quote) {
  try {
    await ElMessageBox.confirm(`确定删除「${q.content.slice(0, 30)}...」？`, '删除摘录', { type: 'warning' })
    await deleteQuote(q.id)
    ElMessage.success('已删除')
    fetchQuotes()
  } catch { /* cancelled */ }
}

function handleSaved() {
  fetchQuotes()
}

onMounted(() => { fetchStats(); fetchQuotes() })
</script>

<style scoped>
.quote-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-left h2 { margin: 0; font-size: 20px; font-weight: 600; }
.header-actions { display: flex; gap: 8px; }

.stats-row { margin-bottom: 16px; }
.stat-card { border: none; border-radius: 10px; }
.stat-card :deep(.el-card__body) { padding: 16px; }
.stat-body { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.stat-value { font-size: 24px; font-weight: 700; color: var(--el-text-color-primary); }
.stat-label { font-size: 12px; color: var(--el-text-color-secondary); }

.filter-card { border: none; border-radius: 10px; margin-bottom: 16px; }
.filter-card :deep(.el-card__body) { padding: 12px 16px; }
.filter-row { display: flex; align-items: center; gap: 12px; }
.filter-label { font-size: 13px; color: #606266; flex-shrink: 0; }

.loading-state { min-height: 200px; }
.empty-state { padding: 60px 0; }

.quote-list { display: flex; flex-direction: column; gap: 8px; }
.quote-item {
  padding: 16px; background: #fff; border: 1px solid #E5E7EB; border-radius: 10px;
  transition: box-shadow 0.2s;
}
.quote-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }

.quote-text { font-size: 14px; color: #1F2937; line-height: 1.6; white-space: pre-wrap; }

.quote-bottom {
  display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 13px; color: #666;
}
.quote-author { font-style: italic; }
.review-count { font-size: 12px; color: #9CA3AF; }
.tag-item { margin: 0 2px; }

.quote-actions { margin-left: auto; display: flex; gap: 4px; }
</style>
