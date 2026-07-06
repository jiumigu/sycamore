<template>
  <div class="language-trainer">
    <div class="back-bar">
      <el-button text @click="$router.push('/toolkit')">
        <el-icon><ArrowLeft /></el-icon> 返回工具集
      </el-button>
    </div>

    <el-tabs v-model="activeType" @tab-change="handleTypeChange">
      <el-tab-pane v-for="tab in trainTabs" :key="tab.value" :label="tab.label" :name="tab.value" />

      <el-dialog v-model="formVisible" :title="editingId ? '编辑训练' : '新建训练'" width="650px" @closed="resetForm">
        <el-form :model="form" label-position="top" size="small">
          <el-form-item label="训练日期" required>
            <el-date-picker v-model="form.train_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
          </el-form-item>

          <!-- 词汇颗粒度 -->
          <template v-if="activeType === 'granularity'">
            <el-form-item label="粗糙词汇">
              <el-input v-model="form.rough_word" placeholder="想要替换的粗糙词汇" />
            </el-form-item>
            <el-form-item label="拆分后的词汇">
              <el-input v-model="form.refined_words" type="textarea" :rows="4" placeholder="更精确/优雅的替代词汇，每行一个" />
            </el-form-item>
          </template>

          <!-- 场景描述 -->
          <template v-if="activeType === 'describe'">
            <el-form-item label="总结性描述">
              <el-input v-model="form.summary" placeholder="一句话描述场景" />
            </el-form-item>
            <el-form-item label="场景还原">
              <el-input v-model="form.scene" type="textarea" :rows="5" placeholder="还原场景的详细描述" />
            </el-form-item>
          </template>

          <!-- 语言素材 -->
          <template v-if="activeType === 'material'">
            <el-form-item label="来源">
              <el-input v-model="form.source" placeholder="书籍/文章/影视等出处" />
            </el-form-item>
            <el-form-item label="原句">
              <el-input v-model="form.quote_text" type="textarea" :rows="4" placeholder="摘录原文" />
            </el-form-item>
            <el-form-item label="为什么觉得好">
              <el-input v-model="form.why_good" type="textarea" :rows="3" placeholder="打动你的原因" />
            </el-form-item>
          </template>

          <!-- 逼近修订 -->
          <template v-if="activeType === 'revision'">
            <el-form-item label="第一版">
              <el-input v-model="form.first_draft" type="textarea" :rows="4" placeholder="最初的版本" />
            </el-form-item>
            <el-form-item label="修订过程">
              <div v-for="(rev, idx) in form.revisions" :key="idx" class="revision-item">
                <el-input v-model="rev.text" type="textarea" :rows="2" :placeholder="`修订 ${idx + 1}`" />
                <el-button size="small" text type="danger" @click="removeRevision(idx)">删除</el-button>
              </div>
              <el-button size="small" @click="addRevision">+ 添加修订版本</el-button>
            </el-form-item>
            <el-form-item label="最终版">
              <el-input v-model="form.final_version" type="textarea" :rows="4" placeholder="最终版本" />
            </el-form-item>
          </template>

          <el-form-item label="备注">
            <el-input v-model="form.notes" :rows="2" placeholder="选填" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button size="small" @click="formVisible = false">取消</el-button>
          <el-button size="small" type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </template>
      </el-dialog>
    </el-tabs>

    <div v-loading="loading" class="content-area">
      <div class="toolbar">
        <span class="record-count">共 {{ total }} 条记录</span>
        <el-button type="primary" size="small" @click="openCreate">+ 新建训练</el-button>
      </div>

      <div v-if="!records.length" class="empty-state">
        <el-empty description="暂无记录" :image-size="50" />
      </div>
      <div v-else class="record-list">
        <el-card v-for="r in records" :key="r.id" shadow="hover" class="record-card">
          <div class="record-header">
            <span class="record-date">{{ r.train_date }}</span>
            <div class="record-actions">
              <el-button size="small" text @click="openEdit(r)">编辑</el-button>
              <el-button size="small" text type="danger" @click="handleDelete(r)">删除</el-button>
            </div>
          </div>

          <!-- 词汇颗粒度摘要 -->
          <template v-if="r.train_type === 'granularity'">
            <div v-if="r.rough_word" class="preview-section">
              <span class="preview-label">粗糙词汇：</span>
              <span class="preview-text">{{ r.rough_word }}</span>
            </div>
            <div v-if="r.refined_words" class="preview-section">
              <span class="preview-label">替换：</span>
              <span class="preview-text">{{ truncate(r.refined_words, 100) }}</span>
            </div>
          </template>

          <!-- 场景描述摘要 -->
          <template v-if="r.train_type === 'describe'">
            <div v-if="r.summary" class="preview-section">
              <span class="preview-label">描述：</span>
              <span class="preview-text">{{ r.summary }}</span>
            </div>
            <div v-if="r.scene" class="preview-section">
              <span class="preview-text">{{ truncate(r.scene, 80) }}</span>
            </div>
          </template>

          <!-- 语言素材摘要 -->
          <template v-if="r.train_type === 'material'">
            <div v-if="r.source" class="preview-section">
              <span class="preview-label">来源：</span>
              <span class="preview-text">{{ r.source }}</span>
            </div>
            <div v-if="r.quote_text" class="preview-section">
              <span class="preview-text">{{ truncate(r.quote_text, 100) }}</span>
            </div>
          </template>

          <!-- 逼近修订摘要 -->
          <template v-if="r.train_type === 'revision'">
            <div v-if="r.first_draft" class="preview-section">
              <span class="preview-label">初版：</span>
              <span class="preview-text">{{ truncate(r.first_draft, 80) }}</span>
            </div>
            <div v-if="r.final_version" class="preview-section">
              <span class="preview-label">终版：</span>
              <span class="preview-text">{{ truncate(r.final_version, 80) }}</span>
            </div>
          </template>
        </el-card>
      </div>

      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        small
        style="margin-top:16px;justify-content:center"
        @current-change="fetchRecords"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getLanguageTrainingList, createLanguageTraining, updateLanguageTraining, deleteLanguageTraining } from '../../api/toolkitApi'

const trainTabs = [
  { value: 'granularity', label: '词汇颗粒度' },
  { value: 'describe', label: '场景描述' },
  { value: 'material', label: '语言素材' },
  { value: 'revision', label: '逼近修订' },
]

const activeType = ref('granularity')
const records = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const formVisible = ref(false)
const editingId = ref<number | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const form = reactive({
  train_type: 'granularity',
  train_date: '',
  rough_word: '',
  refined_words: '',
  summary: '',
  scene: '',
  source: '',
  quote_text: '',
  why_good: '',
  first_draft: '',
  revisions: [] as { text: string }[],
  final_version: '',
  notes: '',
})

function resetForm() {
  editingId.value = null
  form.train_type = activeType.value
  form.train_date = ''
  form.rough_word = ''
  form.refined_words = ''
  form.summary = ''
  form.scene = ''
  form.source = ''
  form.quote_text = ''
  form.why_good = ''
  form.first_draft = ''
  form.revisions = []
  form.final_version = ''
  form.notes = ''
}

function fillForm(r: any) {
  form.train_type = r.train_type
  form.train_date = r.train_date
  form.rough_word = r.rough_word || ''
  form.refined_words = r.refined_words || ''
  form.summary = r.summary || ''
  form.scene = r.scene || ''
  form.source = r.source || ''
  form.quote_text = r.quote_text || ''
  form.why_good = r.why_good || ''
  form.first_draft = r.first_draft || ''
  form.revisions = Array.isArray(r.revisions) ? [...r.revisions] : []
  form.final_version = r.final_version || ''
  form.notes = r.notes || ''
}

function addRevision() {
  form.revisions.push({ text: '' })
}

function removeRevision(idx: number) {
  form.revisions.splice(idx, 1)
}

function openCreate() {
  resetForm()
  form.train_type = activeType.value
  formVisible.value = true
}

function openEdit(r: any) {
  editingId.value = r.id
  fillForm(r)
  formVisible.value = true
}

async function fetchRecords() {
  loading.value = true
  try {
    const res = await getLanguageTrainingList({
      train_type: activeType.value,
    })
    const data = res.data
    records.value = (Array.isArray(data) ? data : data?.results || []) as any[]
    total.value = Array.isArray(data) ? data.length : (data?.count ?? 0)
  } catch {
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!form.train_date) {
    ElMessage.warning('请选择训练日期')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, user_id: 1 }
    if (editingId.value) {
      await updateLanguageTraining(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await createLanguageTraining(payload)
      ElMessage.success('已创建')
    }
    formVisible.value = false
    fetchRecords()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(r: any) {
  try {
    await ElMessageBox.confirm(`确定删除 ${r.train_date} 的训练记录？`, '确认删除', { type: 'warning' })
    await deleteLanguageTraining(r.id)
    ElMessage.success('已删除')
    fetchRecords()
  } catch { /* cancelled */ }
}

function handleTypeChange() {
  currentPage.value = 1
  fetchRecords()
}

function truncate(text: string, len: number) {
  return text && text.length > len ? text.slice(0, len) + '...' : text
}

onMounted(fetchRecords)
</script>

<style scoped>
.language-trainer { padding: 20px; background: var(--el-bg-color-page); min-height: 100vh; }
.back-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; }
.content-area { margin-top: 16px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.record-count { font-size: 13px; color: var(--el-text-color-secondary); }
.empty-state { padding: 60px 0; }
.record-list { display: flex; flex-direction: column; gap: 8px; }
.record-card { border: none; border-radius: 8px; }
.record-card :deep(.el-card__body) { padding: 14px 16px; }
.record-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.record-date { font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); }
.record-actions { display: flex; gap: 4px; }
.preview-section { font-size: 13px; line-height: 1.5; margin-top: 4px; }
.preview-label { font-weight: 500; color: var(--el-text-color-secondary); }
.preview-text { color: var(--el-text-color-regular); white-space: pre-wrap; }
.revision-item { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 8px; }
.revision-item .el-input { flex: 1; }
</style>
