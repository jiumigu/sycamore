<template>
  <div class="quote-page">
    <div class="back-bar">
      <el-button text @click="$router.push('/toolkit')">
        <el-icon><ArrowLeft /></el-icon> 返回工具集
      </el-button>
    </div>
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

    <!-- 统计卡片：前两张讲「谁上得了首页卡」，是这一页最该先看清的事 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">摘录总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-value">{{ stats.in_pool }}</div>
            <div class="stat-label">会进「每日金句」</div>
            <div class="stat-foot">不超过 {{ stats.pool_max_len }} 字</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-value">{{ stats.out_pool }}</div>
            <div class="stat-label">超长不上卡</div>
            <div class="stat-foot">仍存在、仍能搜到</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_reviews }}</div>
            <div class="stat-label">被推送次数</div>
            <div class="stat-foot">首页卡片的轮转依据</div>
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
        <el-divider direction="vertical" />
        <span class="filter-label">金句池</span>
        <el-radio-group v-model="filterPool" size="small" @change="handleFilterChange">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="in">会进池</el-radio-button>
          <el-radio-button value="out">超长不上卡</el-radio-button>
        </el-radio-group>
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
          <el-tooltip :content="poolTip(q)" placement="top">
            <el-tag size="small" :type="q.in_golden_pool ? 'success' : 'warning'" effect="plain">
              {{ poolTagText(q) }}
            </el-tag>
          </el-tooltip>
          <span class="quote-len">{{ q.content_len }} 字</span>
          <template v-if="q.tags">
            <el-tag v-for="tag in getTags(q)" :key="tag" size="small" type="info" class="tag-item">
              {{ tag }}
            </el-tag>
          </template>
          <span class="review-count">📤 被推 {{ q.review_count }} 次</span>
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
import { ArrowLeft, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { LANGUAGE_OPTIONS } from '../types/quoteTypes'
import type { Quote } from '../types/quoteTypes'
import { getQuoteList, getQuoteStats, deleteQuote } from '../api/quoteApi'
import QuoteForm from '../components/QuoteForm.vue'

const quotes = ref<Quote[]>([])
const loading = ref(false)
const filterLang = ref('')
const filterTag = ref('')
/** 金句池筛选：''=全部 / 'in'=会进池 / 'out'=超长不上卡（后端按同一把尺子筛） */
const filterPool = ref('')

const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const stats = reactive({
  total: 0,
  in_pool: 0,
  out_pool: 0,
  pool_max_len: 0,
  total_reviews: 0,
})

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

/**
 * 池状态标签 —— **只查后端下发的 `in_golden_pool`，不自己比长度**。
 * 前端另算一份迟早会跟池子取数对不上（emoji 等代理对的长度两边计法不同），
 * 而界面上完全看不出来。
 */
function poolTagText(q: Quote) {
  if (q.in_golden_pool === null || q.in_golden_pool === undefined) return '池状态未知'
  return q.in_golden_pool ? '会进池' : '超长不上卡'
}

/** 标签要能解释自己：为什么这条不上卡（恒灰/恒亮的标记最容易被读成「坏了」） */
function poolTip(q: Quote) {
  if (q.in_golden_pool === null || q.in_golden_pool === undefined) {
    return '暂时读不到当前的长度上限'
  }
  return q.in_golden_pool
    ? `不超过 ${stats.pool_max_len} 字，会参与「每日金句」轮转`
    : `超过 ${stats.pool_max_len} 字上限，不会上「每日金句」卡 —— 照样存在、照样能搜到。上限可在「系统管理 → 系统设置 → 摘录金句池」里调`
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
    if (filterPool.value) params.pool = filterPool.value
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
    stats.in_pool = 0
    stats.out_pool = 0
    stats.pool_max_len = 0
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
.stat-foot { font-size: 11px; color: var(--el-text-color-placeholder); }

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
.quote-len { font-size: 12px; color: #9CA3AF; }
.tag-item { margin: 0 2px; }

.quote-actions { margin-left: auto; display: flex; gap: 4px; }
.back-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; flex-wrap: nowrap; }
</style>
