<template>
  <div class="conflict-tracker">
    <h2 class="page-title">🌱 成长记录</h2>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-label">累计事件</div>
            <div class="stat-value">{{ stats?.total_count ?? 0 }} 次</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-label">累计损失</div>
            <div class="stat-value text-danger">¥{{ stats?.total_loss ?? 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-label">平均愤怒</div>
            <div class="stat-value">{{ avgEmotion }}/5</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-label">未解决</div>
            <div class="stat-value text-warning">{{ unresolvedCount }} 件</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作栏 -->
    <el-card shadow="hover" class="action-card">
      <el-button type="danger" @click="showAddDialog = true">
        + 记录事件
      </el-button>
      <el-select
        v-model="filterType"
        placeholder="按类型筛选"
        clearable
        class="filter-select"
        @change="handleFilter"
      >
        <el-option v-for="opt in EVENT_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
    </el-card>

    <!-- 事件列表 -->
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>📋 事件记录 ({{ events.length }})</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="events" style="width: 100%" empty-text="暂无记录">
        <el-table-column prop="event_date" label="日期" width="100" />
        <el-table-column label="关联人" width="80">
          <template #default="{ row }">
            {{ privacyStore.privacyMode ? maskName(row.contact_name, true) : row.contact_name }}
          </template>
        </el-table-column>
        <el-table-column prop="title" label="事件" min-width="150" show-overflow-tooltip />
        <el-table-column prop="event_type" label="类型" width="80" />
        <el-table-column label="愤怒" width="130">
          <template #default="{ row }">
            <span class="emotion-bar">
              <span v-for="i in 5" :key="i" class="emotion-dot" :class="{ active: i <= row.emotion_level }" />
            </span>
          </template>
        </el-table-column>
        <el-table-column label="损失" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.loss_amount" class="text-danger">¥{{ row.loss_amount }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_resolved" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_resolved ? 'success' : 'danger'" size="small">
              {{ row.is_resolved ? '已解决' : '未解决' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="解决方式" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.is_resolved && row.resolution_note" class="resolution-preview">
              ✅ {{ row.resolution_note }}
            </span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="showAddDialog" :title="editingEvent ? '编辑记录' : '新增记录'" width="520px" :close-on-click-modal="false">
      <el-form :model="form" label-width="90px" label-position="left">
        <el-form-item label="关联人">
          <el-select
            v-model="form.contact_id"
            placeholder="搜索或选择联系人"
            filterable
            remote
            :remote-method="searchContacts"
            :loading="contactLoading"
            clearable
            style="width: 100%"
          >
            <el-option v-for="c in filteredContacts" :key="c.id" :label="privacyStore.privacyMode ? maskName(c.name, true) : c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="事件标题">
          <el-input v-model="form.title" placeholder="如：把我杯子摔碎了" />
        </el-form-item>
        <el-form-item label="事件类型">
          <el-select v-model="form.event_type" style="width: 100%">
            <el-option v-for="opt in EVENT_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="愤怒指数">
          <el-rate v-model="form.emotion_level" :max="5" show-text :texts="['轻微不爽', '有点生气', '很生气', '非常愤怒', '极度愤怒']" />
        </el-form-item>
        <el-form-item label="经济损失">
          <el-input-number v-model="form.loss_amount" :min="0" :precision="2" style="width: 200px" />
        </el-form-item>
        <el-form-item label="事件描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="详细描述事件经过" />
        </el-form-item>
        <el-form-item label="发生日期">
          <el-date-picker v-model="form.event_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="逗号分隔，如：猫咪,败家" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="saveEvent">{{ editingEvent ? '保存' : '记录' }}</el-button>
      </template>
    </el-dialog>

    <!-- 编辑弹窗（解析状态） -->
    <el-dialog v-model="showEditDialog" :title="'解析 · ' + editingEvent?.title" width="500px">
      <el-form :model="editForm" label-width="90px" label-position="left">
        <el-form-item label="是否已解决">
          <el-switch v-model="editForm.is_resolved" active-text="已解决" inactive-text="未解决" />
        </el-form-item>
        <el-form-item v-if="editForm.is_resolved" label="解决备注">
          <el-input v-model="editForm.resolution_note" type="textarea" :rows="3" placeholder="如何解决的？自己的反思？" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="updateResolution">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { EVENT_TYPE_OPTIONS, type ConflictEvent } from '../types/conflictTypes'
import { useConflictStore } from '../stores/conflictStore'
import * as conflictApi from '../api/conflictApi'
import { getRelationshipList } from '../api/relationshipApi'
import type { Relationship } from '../types/relationshipTypes'
import { maskName } from '@/shared/utils/privacy'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'

const privacyStore = usePrivacyStore()
const store = useConflictStore()

const loading = computed(() => store.loading)
const events = computed(() => store.events)
const stats = computed(() => store.stats)
const filterType = ref('')

const avgEmotion = computed(() => (stats.value?.avg_emotion ?? 0).toFixed(1))
const unresolvedCount = computed(() => events.value.filter(e => !e.is_resolved).length)

const showAddDialog = ref(false)
const showEditDialog = ref(false)
const submitting = ref(false)
const editingEvent = ref<ConflictEvent | null>(null)

const contactLoading = ref(false)
const filteredContacts = ref<Relationship[]>([])

const form = reactive({
  contact_id: null as number | null,
  title: '',
  event_type: '其他',
  emotion_level: 1,
  loss_amount: null as number | null,
  description: '',
  event_date: '',
  tags: '',
})

const editForm = reactive({
  is_resolved: false,
  resolution_note: '',
})

function resetForm() {
  form.contact_id = null
  form.title = ''
  form.event_type = '其他'
  form.emotion_level = 1
  form.loss_amount = null
  form.description = ''
  form.event_date = ''
  form.tags = ''
}

function handleFilter() {
  store.fetchEvents(filterType.value ? { type: filterType.value } : undefined)
}

function handleEdit(row: ConflictEvent) {
  editingEvent.value = row
  editForm.is_resolved = row.is_resolved
  editForm.resolution_note = row.resolution_note || ''
  showEditDialog.value = true
}

async function saveEvent() {
  if (!form.contact_id || !form.title || !form.event_date) return
  submitting.value = true
  try {
    const data = {
      contact: form.contact_id,
      title: form.title,
      event_type: form.event_type,
      emotion_level: form.emotion_level,
      loss_amount: form.loss_amount ?? null,
      description: form.description,
      event_date: form.event_date,
      tags: form.tags,
    }
    if (editingEvent.value) {
      await conflictApi.updateConflict(editingEvent.value.id, data)
    } else {
      await conflictApi.createConflict(data)
    }
    showAddDialog.value = false
    resetForm()
    await store.fetchAll()
  } finally {
    submitting.value = false
  }
}

async function updateResolution() {
  if (!editingEvent.value) return
  submitting.value = true
  try {
    await conflictApi.updateConflict(editingEvent.value.id, {
      is_resolved: editForm.is_resolved,
      resolution_note: editForm.resolution_note,
    })
    showEditDialog.value = false
    await store.fetchAll()
  } finally {
    submitting.value = false
  }
}

async function searchContacts(query: string) {
  if (!query) {
    filteredContacts.value = []
    return
  }
  contactLoading.value = true
  try {
    const res = await getRelationshipList({ search: query, page_size: 20 })
    filteredContacts.value = res.data.results || []
  } finally {
    contactLoading.value = false
  }
}

onMounted(() => {
  store.fetchAll()
})
</script>

<style scoped lang="scss">
.conflict-tracker {
  padding: 16px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
}

.stats-row { margin-bottom: 16px; }

.stat-card {
  border: none;
  border-radius: 10px;
  :deep(.el-card__body) { padding: 16px; }
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.action-card {
  margin-bottom: 16px;
  :deep(.el-card__body) {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.filter-select { width: 200px; }

.card-header {
  font-weight: 600;
  font-size: 14px;
}

.emotion-bar {
  display: inline-flex;
  gap: 3px;
}

.emotion-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #e0e0e0;
  transition: background 0.2s;

  &.active {
    background: #f56c6c;
  }
}

.text-danger { color: #f56c6c; }
.text-warning { color: #e6a23c; }
.text-muted { color: #c0c4cc; }
</style>
