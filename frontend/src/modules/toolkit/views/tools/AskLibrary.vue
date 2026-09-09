<template>
  <div class="ask-library">
    <!-- 顶栏 -->
    <div class="page-header">
      <div class="header-info">
        <h1 class="page-title">🤖 AI 问答库</h1>
        <p class="page-desc">完整存档 AI 问答（问题原文 + 各 AI 回答 + 会话背景），支持检索 / 打标 / 多 AI 对照 / 导出 md</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadTagPresets">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" plain :disabled="!selectedRows.length" @click="exportSelected">
          <el-icon><Download /></el-icon>
          导出所选（{{ selectedRows.length }}）
        </el-button>
        <el-button type="primary" @click="openTopicDialog()">
          <el-icon><Plus /></el-icon>
          新建主题
        </el-button>
      </div>
    </div>

    <!-- 筛选工具条 -->
    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-input
          v-model="query.search"
          placeholder="搜索问题 / 回答 / AI / 会话背景"
          clearable
          style="width: 300px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.ai" placeholder="回答的 AI" clearable style="width: 160px" @change="handleSearch">
          <el-option v-for="ai in AI_OPTIONS" :key="ai" :label="ai" :value="ai" />
        </el-select>
        <el-select v-model="query.tag" placeholder="标签" clearable style="width: 160px" @change="handleSearch">
          <el-option v-for="t in tagOptions" :key="t" :label="t" :value="t" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="起始时间"
          end-placeholder="结束时间"
          style="width: 260px"
          @change="handleSearch"
        />
        <el-button @click="resetQuery">重置</el-button>
        <span class="filter-hint">标签在「系统预设管理」中维护 · 提问原文永不丢失</span>
      </div>
    </el-card>

    <!-- 主题表格 -->
    <el-card shadow="never">
      <el-table
        v-loading="loading"
        :data="topics"
        stripe
        size="default"
        row-key="id"
        @selection-change="selectedRows = $event"
        @row-click="openDetail"
        class="topic-table"
      >
        <el-table-column type="selection" width="42" />
        <el-table-column label="主题 / 问题" min-width="300">
          <template #default="{ row }">
            <div class="topic-title">{{ row.title || truncate(row.question, 60) }}</div>
            <div v-if="row.title" class="topic-question">{{ truncate(row.question, 90) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="回答" width="110" align="center">
          <template #default="{ row }">
            <span class="ans-count">{{ row.answer_count ?? 0 }} 条</span>
            <el-tag v-if="row.accepted_count" size="small" type="success" class="accepted-tag">采纳 {{ row.accepted_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近提问" width="160">
          <template #default="{ row }">{{ formatDateTime(row.latest_asked_at) || '-' }}</template>
        </el-table-column>
        <el-table-column label="标签" min-width="160">
          <template #default="{ row }">
            <template v-if="row.tags?.length">
              <el-tag v-for="t in row.tags.slice(0, 4)" :key="t" size="small" type="warning" class="tag-chip">{{ t }}</el-tag>
              <el-tag v-if="row.tags.length > 4" size="small" type="info">+{{ row.tags.length - 4 }}</el-tag>
            </template>
            <span v-else class="no-tag">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="danger" @click.stop="handleDeleteTopic(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有问答记录，点右上角「新建主题」开始存档" :image-size="90" />
        </template>
      </el-table>

      <div class="table-footer">
        <span class="footer-hint">共 {{ total }} 个主题 · 同一问题问多个 AI / 隔段时间重问，都聚在同一主题下对照</span>
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          small
          @current-change="fetchTopics"
        />
      </div>
    </el-card>

    <!-- 新建 / 编辑主题 -->
    <el-dialog v-model="topicDialogVisible" :title="topicForm.id ? '编辑主题' : '新建主题'" width="600px">
      <el-form :model="topicForm" label-width="86px">
        <el-form-item label="主题标题">
          <el-input v-model="topicForm.title" placeholder="留空则自动取问题前 30 字" maxlength="200" />
        </el-form-item>
        <el-form-item label="完整提问" required>
          <el-input
            v-model="topicForm.question"
            type="textarea"
            :rows="5"
            placeholder="粘贴你当时发给 AI 的完整提示词（问题原文会永久保留，方便日后重问）"
          />
        </el-form-item>
        <el-form-item label="提问背景">
          <el-input
            v-model="topicForm.background"
            type="textarea"
            :rows="2"
            placeholder="选填：当时为什么问 / 正在做什么决策（区分同一 AI 不同对话背景时也写这里）"
          />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="topicForm.tags" multiple clearable placeholder="来自系统预设管理（ask_tags）" style="width: 100%">
            <el-option v-for="t in tagOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="topicDialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="topicSaving" @click="saveTopic">保存</el-button>
      </template>
    </el-dialog>

    <!-- 主题详情：问题 + 多 AI 回答对照 -->
    <el-drawer v-model="drawerVisible" :title="currentTopic?.title || '问答详情'" size="68%" destroy-on-close>
      <template v-if="currentTopic">
        <div class="detail-head">
          <div class="detail-question">
            <span class="sec-label">完整提问</span>
            <p class="question-text">{{ currentTopic.question }}</p>
            <p v-if="currentTopic.background" class="background-text">📌 背景：{{ currentTopic.background }}</p>
            <div class="meta-line">
              <span>创建 {{ formatDateTime(currentTopic.created_at) }}</span>
              <el-tag v-for="t in currentTopic.tags || []" :key="t" size="small" type="warning" class="tag-chip">{{ t }}</el-tag>
            </div>
          </div>
          <div class="head-actions">
            <el-button size="small" type="primary" plain @click="exportTopic(currentTopic)">
              <el-icon><Download /></el-icon>
              导出 .md
            </el-button>
            <el-button size="small" @click="openTopicDialog(currentTopic)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="handleDeleteTopic(currentTopic)">删除</el-button>
          </div>
        </div>

        <el-divider content-position="left">AI 回答对照（{{ answers.length }}）</el-divider>

        <div class="answers-area" v-loading="detailLoading">
          <el-card v-for="ans in answers" :key="ans.id" shadow="never" class="answer-card">
            <div class="answer-head">
              <span class="ai-badge">{{ ans.ai }}</span>
              <el-tag v-if="ans.session" size="small" type="info" class="session-tag">{{ ans.session }}</el-tag>
              <span class="asked-time">{{ formatDateTime(ans.asked_at) }}</span>
              <el-select
                :model-value="ans.verdict || ''"
                placeholder="采纳?"
                size="small"
                class="verdict-select"
                @change="(v: string) => changeVerdict(ans, v)"
              >
                <el-option label="未标记" value="" />
                <el-option label="✅ 采纳" value="采纳" />
                <el-option label="📎 备用" value="备用" />
                <el-option label="✖ 不采用" value="不采用" />
              </el-select>
              <span class="head-spacer" />
              <el-button size="small" link @click="openAnswerDialog(ans)">编辑</el-button>
              <el-button size="small" link type="danger" @click="handleDeleteAnswer(ans)">删除</el-button>
            </div>
            <p v-if="ans.note" class="answer-note">{{ ans.note }}</p>
            <div class="answer-body" :class="{ collapsed: !expandedIds.has(ans.id) }">
              {{ ans.answer }}
            </div>
            <div v-if="ans.answer.length > 220" class="expand-btn">
              <el-button size="small" link type="primary" @click="toggleExpand(ans.id)">
                {{ expandedIds.has(ans.id) ? '收起' : '展开全文' }}
              </el-button>
            </div>
          </el-card>
          <el-empty v-if="!answers.length" description="还没有记录任何 AI 回答 —— 点下方按钮添加第一条" :image-size="80" />
        </div>

        <div class="drawer-footer">
          <el-button type="primary" @click="openAnswerDialog()">
            <el-icon><Plus /></el-icon>
            添加回答（记一次 AI 对话）
          </el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 添加 / 编辑回答 -->
    <el-dialog v-model="answerDialogVisible" :title="answerForm.id ? '编辑回答' : '添加回答'" width="620px" top="6vh">
      <el-form :model="answerForm" label-width="86px">
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="回答的 AI" required>
              <el-select v-model="answerForm.ai" filterable allow-create default-first-option style="width: 100%">
                <el-option v-for="ai in AI_OPTIONS" :key="ai" :label="ai" :value="ai" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="提问时间">
              <el-date-picker v-model="answerForm.asked_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="会话背景">
          <el-input
            v-model="answerForm.session"
            placeholder="选填：这次是在哪个对话里问的？如「6月职业规划深聊」——同一 AI 不同对话背景靠它区分"
            maxlength="100"
          />
        </el-form-item>
        <el-form-item label="回答全文" required>
          <el-input
            v-model="answerForm.answer"
            type="textarea"
            :rows="9"
            placeholder="粘贴该 AI 的完整回答（markdown 原样保存）"
          />
        </el-form-item>
        <el-form-item label="采纳标记">
          <el-radio-group v-model="answerForm.verdict">
            <el-radio value="">未标记</el-radio>
            <el-radio value="采纳">采纳</el-radio>
            <el-radio value="备用">备用</el-radio>
            <el-radio value="不采用">不采用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="answerDialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="answerSaving" @click="saveAnswer">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search, Download } from '@element-plus/icons-vue'
import {
  getAskTopics, getAskTopic, createAskTopic, updateAskTopic, deleteAskTopic,
  createAskAnswer, updateAskAnswer, deleteAskAnswer, fetchAskTagPresets,
} from '../../api/askLibraryApi'
import type { AskTopicItem, AskAnswerItem } from '../../api/askLibraryApi'

const AI_OPTIONS = ['WorkBuddy', 'Claude Code', 'ChatGPT', 'Gemini', 'Kimi', '豆包', 'DeepSeek', '通义千问']
const VERDICT_MARK: Record<string, string> = { 采纳: '✅ 采纳', 备用: '📎 备用', 不采用: '✖ 不采用' }

const loading = ref(false)
const topics = ref<AskTopicItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(15)
const selectedRows = ref<AskTopicItem[]>([])
const tagOptions = ref<string[]>([])
const dateRange = ref<[string, string] | null>(null)
const query = reactive<{ search: string; ai: string; tag: string }>({ search: '', ai: '', tag: '' })

function truncate(s: string, n: number): string {
  return (s || '').length > n ? `${(s || '').slice(0, n)}…` : s || ''
}
function formatDateTime(iso?: string | null): string {
  if (!iso) return ''
  return iso.slice(0, 16).replace('T', ' ')
}

// ─── 列表 ───
async function fetchTopics() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (query.search.trim()) params.search = query.search.trim()
    if (query.ai) params.ai = query.ai
    if (query.tag) params.tag = query.tag
    if (dateRange.value?.length === 2) {
      params.date_from = dateRange.value[0]
      params.date_to = dateRange.value[1]
    }
    const res = await getAskTopics(params)
    const data = res.data
    topics.value = (data.results || []) as AskTopicItem[]
    total.value = data.count ?? topics.value.length
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function loadTagPresets() {
  tagOptions.value = await fetchAskTagPresets()
}

function handleSearch() {
  page.value = 1
  fetchTopics()
}
function resetQuery() {
  query.search = ''
  query.ai = ''
  query.tag = ''
  dateRange.value = null
  handleSearch()
}

// ─── 新建 / 编辑主题 ───
const topicDialogVisible = ref(false)
const topicSaving = ref(false)
const topicForm = reactive<{ id: number | null; title: string; question: string; background: string; tags: string[] }>({
  id: null, title: '', question: '', background: '', tags: [],
})

function openTopicDialog(topic?: AskTopicItem) {
  topicForm.id = topic?.id ?? null
  topicForm.title = topic?.title ?? ''
  topicForm.question = topic?.question ?? ''
  topicForm.background = topic?.background ?? ''
  topicForm.tags = [...(topic?.tags || [])]
  topicDialogVisible.value = true
}

async function saveTopic() {
  if (!topicForm.question.trim()) {
    ElMessage.warning('请填写完整提问（问题原文是档案的根）')
    return
  }
  topicSaving.value = true
  try {
    const payload = {
      title: topicForm.title.trim() || (topicForm.question.trim().length > 30 ? `${topicForm.question.trim().slice(0, 30)}…` : topicForm.question.trim()),
      question: topicForm.question,
      background: topicForm.background,
      tags: topicForm.tags,
    }
    if (topicForm.id) await updateAskTopic(topicForm.id, payload)
    else await createAskTopic(payload)
    ElMessage.success('保存成功')
    topicDialogVisible.value = false
    fetchTopics()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    topicSaving.value = false
  }
}

async function handleDeleteTopic(row: AskTopicItem) {
  try {
    await ElMessageBox.confirm(`确认删除主题「${row.title || truncate(row.question, 30)}」及其全部回答？`, '删除确认', { type: 'warning' })
    await deleteAskTopic(row.id)
    ElMessage.success('已删除')
    drawerVisible.value = false
    fetchTopics()
  } catch { /* 取消 */ }
}

// ─── 详情（问题 + 回答对照）───
const drawerVisible = ref(false)
const detailLoading = ref(false)
const currentTopic = ref<AskTopicItem | null>(null)
const answers = computed<AskAnswerItem[]>(() => currentTopic.value?.answers || [])
const expandedIds = ref<Set<number>>(new Set())

async function openDetail(row: AskTopicItem) {
  detailLoading.value = true
  drawerVisible.value = true
  expandedIds.value = new Set()
  try {
    const res = await getAskTopic(row.id)
    currentTopic.value = res.data as AskTopicItem
  } catch {
    ElMessage.error('加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

function toggleExpand(id: number) {
  const next = new Set(expandedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
}

async function reloadDetail() {
  if (!currentTopic.value) return
  const res = await getAskTopic(currentTopic.value.id)
  currentTopic.value = res.data as AskTopicItem
}

// ─── 回答 CRUD ───
const answerDialogVisible = ref(false)
const answerSaving = ref(false)
const answerForm = reactive<{ id: number | null; topic: number | null; ai: string; session: string; asked_at: string; answer: string; verdict: '' | '采纳' | '备用' | '不采用'; note: string }>({
  id: null, topic: null, ai: 'WorkBuddy', session: '', asked_at: '', answer: '', verdict: '', note: '',
})

function openAnswerDialog(ans?: AskAnswerItem) {
  answerForm.id = ans?.id ?? null
  answerForm.topic = currentTopic.value?.id ?? null
  answerForm.ai = ans?.ai ?? 'WorkBuddy'
  answerForm.session = ans?.session ?? ''
  answerForm.asked_at = ans?.asked_at ? ans.asked_at.slice(0, 19).replace('T', ' ') : new Date().toISOString().slice(0, 19).replace('T', ' ')
  answerForm.answer = ans?.answer ?? ''
  answerForm.verdict = (ans?.verdict as '' | '采纳' | '备用' | '不采用') ?? ''
  answerForm.note = ans?.note ?? ''
  answerDialogVisible.value = true
}

async function saveAnswer() {
  if (!answerForm.topic) return
  if (!answerForm.answer.trim()) {
    ElMessage.warning('请粘贴回答全文')
    return
  }
  answerSaving.value = true
  try {
    const payload = {
      topic: answerForm.topic,
      ai: answerForm.ai,
      session: answerForm.session.trim(),
      asked_at: answerForm.asked_at || new Date().toISOString().slice(0, 19).replace('T', ' '),
      answer: answerForm.answer,
      verdict: answerForm.verdict,
      note: answerForm.note,
    }
    if (answerForm.id) await updateAskAnswer(answerForm.id, payload)
    else await createAskAnswer(payload)
    ElMessage.success('已保存')
    answerDialogVisible.value = false
    await reloadDetail()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    answerSaving.value = false
  }
}

async function changeVerdict(ans: AskAnswerItem, verdict: string) {
  try {
    await updateAskAnswer(ans.id, { verdict: verdict as AskAnswerItem['verdict'] })
    ans.verdict = verdict as AskAnswerItem['verdict']
    await reloadDetail()
    ElMessage.success(VERDICT_MARK[verdict] ? `已标记：${VERDICT_MARK[verdict]}` : '已取消标记')
  } catch {
    ElMessage.error('标记失败')
  }
}

async function handleDeleteAnswer(ans: AskAnswerItem) {
  try {
    await ElMessageBox.confirm(`删除 ${ans.ai}（${formatDateTime(ans.asked_at)}）这条回答？`, '删除确认', { type: 'warning' })
    await deleteAskAnswer(ans.id)
    ElMessage.success('已删除')
    await reloadDetail()
  } catch { /* 取消 */ }
}

// ─── 导出 .md ───
function safeFilename(title: string): string {
  return title.replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 60) || 'ask_topic'
}

function buildMarkdown(topic: AskTopicItem): string {
  const title = topic.title || truncate(topic.question, 40)
  const lines: string[] = []
  lines.push('---')
  lines.push(`title: ${title}`)
  lines.push(`created_at: ${(topic.created_at || '').slice(0, 10)}`)
  lines.push(`tags: [${(topic.tags || []).join(', ')}]`)
  lines.push(`exported_at: ${new Date().toISOString().slice(0, 10)}`)
  lines.push('---')
  lines.push('')
  lines.push(`# ${title}`)
  lines.push('')
  lines.push(`> 完整提问：${topic.question}`)
  if (topic.background) lines.push(`>\n> 📌 背景：${topic.background}`)
  lines.push('')
  lines.push(`提问时间：${formatDateTime(topic.created_at)} ｜ 共 ${(topic.answers || []).length} 次回答`)
  lines.push('')
  for (const ans of topic.answers || []) {
    lines.push(`## 🤖 ${ans.ai}${ans.session ? `（会话：${ans.session}）` : ''} · ${formatDateTime(ans.asked_at)}${ans.verdict ? ` · ${VERDICT_MARK[ans.verdict]}` : ''}`)
    lines.push('')
    if (ans.note) lines.push(`> ${ans.note}\n`)
    lines.push(ans.answer.trim())
    lines.push('')
  }
  return lines.join('\n')
}

function downloadMd(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function exportTopic(topic: AskTopicItem) {
  const full = topic.answers?.length ? topic : ((await getAskTopic(topic.id)).data as AskTopicItem)
  downloadMd(buildMarkdown(full), `${safeFilename(full.title || full.question)}.md`)
  ElMessage.success('已导出 .md（可粘入 Logseq / Obsidian）')
}

async function exportSelected() {
  if (!selectedRows.value.length) return
  const exporting = [...selectedRows.value]
  for (const row of exporting) {
    const full = (await getAskTopic(row.id)).data as AskTopicItem
    downloadMd(buildMarkdown(full), `${safeFilename(full.title || full.question)}.md`)
  }
  ElMessage.success(`已导出 ${exporting.length} 个主题`)
}

onMounted(() => {
  fetchTopics()
  loadTagPresets()
})
</script>

<style scoped lang="scss">
.ask-library {
  padding: 20px;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;

    .page-title { margin: 0 0 4px; font-size: 22px; font-weight: 600; }
    .page-desc { margin: 0; font-size: 13px; color: var(--el-text-color-secondary); }
    .header-actions { display: flex; gap: 8px; flex-shrink: 0; }
  }

  .filter-card { margin-bottom: 16px;
    .filter-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
      .filter-hint { margin-left: auto; font-size: 12px; color: var(--el-text-color-placeholder); }
    }
  }

  .topic-table { cursor: pointer;
    .topic-title { font-weight: 600; color: var(--el-text-color-primary); }
    .topic-question { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
    .ans-count { font-weight: 600; margin-right: 4px; }
    .accepted-tag { margin-top: 4px; }
    .tag-chip { margin: 2px 4px 2px 0; }
    .no-tag { color: var(--el-text-color-placeholder); }
  }

  .table-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 14px;
    .footer-hint { font-size: 12px; color: var(--el-text-color-placeholder); }
  }

  .detail-head { display: flex; gap: 16px; justify-content: space-between;
    .detail-question { flex: 1; min-width: 0;
      .sec-label { font-size: 12px; font-weight: 600; color: var(--el-color-primary); background: var(--el-color-primary-light-9); padding: 2px 8px; border-radius: 4px; }
      .question-text { font-size: 15px; line-height: 1.7; margin: 10px 0 6px; white-space: pre-wrap; word-break: break-word; }
      .background-text { font-size: 13px; color: var(--el-text-color-secondary); margin: 6px 0; }
      .meta-line { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--el-text-color-placeholder); flex-wrap: wrap; }
    }
    .head-actions { display: flex; gap: 6px; flex-shrink: 0; }
  }

  .answers-area { display: flex; flex-direction: column; gap: 12px; min-height: 120px;
    .answer-card {
      .answer-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;
        .ai-badge { font-size: 13px; font-weight: 600; color: var(--el-color-primary); }
        .session-tag { max-width: 220px; }
        .asked-time { font-size: 12px; color: var(--el-text-color-placeholder); }
        .verdict-select { width: 110px; }
        .head-spacer { flex: 1; }
      }
      .answer-note { font-size: 12px; color: var(--el-color-warning); background: var(--el-color-warning-light-9); padding: 4px 8px; border-radius: 4px; margin: 0 0 6px; }
      .answer-body { font-size: 13px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; color: var(--el-text-color-regular);
        &.collapsed { max-height: 180px; overflow: hidden; position: relative;
          &::after { content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 40px; background: linear-gradient(transparent, var(--el-bg-color)); }
        }
      }
      .expand-btn { margin-top: 2px; }
    }
  }

  .drawer-footer { margin-top: 16px; display: flex; justify-content: center; }
}
</style>
