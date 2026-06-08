<template>
  <div class="sugar-page" v-loading="store.loading">
    <!-- ========== 页面标题 ========== -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">小确幸</h1>
        <el-tag type="success" class="module-tag">快乐储蓄</el-tag>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          自定义记录
        </el-button>
        <el-button @click="refreshAll">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- ========== 统计卡片 ========== -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-icon" style="background: #D1FAE5"><span class="icon-text">💰</span></div>
            <div class="stat-info">
              <div class="stat-value" style="color: #059669">¥{{ formatMoney(poolBalance) }}</div>
              <div class="stat-label">奖励池余额</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-icon" style="background: #FEF3C7"><span class="icon-text">🎉</span></div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalCount }}</div>
              <div class="stat-label">累计获得</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-icon" style="background: #DBEAFE"><span class="icon-text">📊</span></div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.avgHappiness.toFixed(1) }}</div>
              <div class="stat-label">平均快乐</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-icon" style="background: #FCE7F3"><span class="icon-text">🏷️</span></div>
            <div class="stat-info">
              <div class="stat-value">{{ categoryCount }}</div>
              <div class="stat-label">分类数</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ========== 筛选栏 ========== -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-bar">
        <div class="filter-left">
          <el-select v-model="filterYear" placeholder="年份" clearable @change="fetchData" class="filter-select">
            <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
          </el-select>
          <el-select v-model="filterMonth" placeholder="月份" clearable @change="fetchData" class="filter-select">
            <el-option v-for="m in 12" :key="m" :label="`${m}月`" :value="m" />
          </el-select>
          <el-select v-model="filterCategory" placeholder="分类" clearable @change="fetchData" class="filter-select">
            <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="`${c.icon} ${c.label}`" :value="c.value" />
          </el-select>
        </div>
        <div class="filter-right">
          <span class="total-reward">累计奖励+¥{{ formatMoney(stats.totalReward) }}</span>
        </div>
      </div>
    </el-card>

    <!-- ========== 小确幸列表（时间轴卡片） ========== -->
    <div class="sugar-list">
      <template v-if="store.sugarList.length">
        <SugarCard
          v-for="record in store.sugarList"
          :key="record.s_id"
          :record="record"
          @edit="openEdit"
          @delete="handleDelete"
        />
      </template>
      <el-empty v-else description="暂无小确幸，记录你的快乐时刻吧！" :image-size="100" />
    </div>

    <!-- 分页 -->
    <div class="pagination-wrapper" v-if="store.total > store.pageSize">
      <el-pagination
        v-model:current-page="store.currentPage"
        :page-size="store.pageSize"
        :total="store.total"
        layout="prev, pager, next"
        @current-change="store.handlePageChange"
      />
    </div>

    <!-- ========== 新增/编辑小确幸弹窗 ========== -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑小确幸' : '记录小确幸'"
      width="580px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="0" class="sugar-form">
        <el-form-item prop="title">
          <el-input v-model="form.title" placeholder="小确幸标题 *" maxlength="100" show-word-limit />
        </el-form-item>

        <div class="form-section-label">快乐程度 *</div>
        <el-form-item prop="level_of_happiness">
          <HappinessSlider v-model="form.level_of_happiness" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item prop="time">
              <el-date-picker v-model="form.time" type="date" placeholder="发生日期 *" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item prop="category">
              <el-select v-model="form.category" placeholder="分类" clearable style="width: 100%">
                <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="`${c.icon} ${c.label}`" :value="c.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="标签" prop="tags">
          <el-select
            v-model="form.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入标签后回车"
            style="width: 100%"
          >
            <el-option v-for="t in SUGGESTED_TAGS" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>

        <el-form-item label="备注" prop="notes">
          <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="记录你的快乐感受..." maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="store.submitting" @click="handleSubmit">
            保存 — 得{{ expectedReward }}元奖励
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { useSugarStore } from '../stores/sugarStore'
import { CATEGORY_OPTIONS } from '../types/sugarTypes'
import type { SugarRecord } from '../types/sugarTypes'
import SugarCard from '../components/SugarCard.vue'
import HappinessSlider from '../components/HappinessSlider.vue'
import { getRewardPool } from '@/modules/reward/api/rewardApi'

const store = useSugarStore()

// ─── 统计计算 ───
const poolBalance = ref(0)
const stats = computed(() => {
  const summary = store.statsSummary
  return {
    totalCount: summary.total_count,
    totalReward: summary.total_reward,
    avgHappiness: summary.avg_happiness,
  }
})
const categoryCount = computed(() => {
  return store.categories.length
})

// ─── 筛选 ───
const filterYear = ref<number | undefined>()
const filterMonth = ref<number | undefined>()
const filterCategory = ref<string>()

const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return [y, y - 1, y - 2, y - 3]
})

// ─── 弹窗 ───
const dialogVisible = ref(false)
const editingId = ref<number | undefined>()
const formRef = ref<FormInstance>()

const form = reactive({
  title: '',
  level_of_happiness: 7,
  time: new Date().toISOString().slice(0, 10),
  category: '',
  tags: [] as string[],
  notes: '',
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  level_of_happiness: [{ required: true, message: '请选择快乐程度', trigger: 'change' }],
  time: [{ required: true, message: '请选择日期', trigger: 'change' }],
}

const SUGGESTED_TAGS = ['惊喜', '感动', '成就', '小确幸', '美食', '友情', '家庭', '自然', '成长', '放松']

const expectedReward = computed(() => {
  const v = form.level_of_happiness
  if (v <= 3) return '1'
  if (v <= 5) return '3'
  if (v <= 7) return '5'
  if (v <= 8.5) return '8'
  return '10'
})

function resetForm() {
  form.title = ''
  form.level_of_happiness = 7
  form.time = new Date().toISOString().slice(0, 10)
  form.category = ''
  form.tags = []
  form.notes = ''
}

function openCreate() {
  editingId.value = undefined
  resetForm()
  dialogVisible.value = true
}

function openEdit(record: SugarRecord) {
  editingId.value = record.s_id
  form.title = record.title
  form.level_of_happiness = Number(record.level_of_happiness) || 7
  form.time = record.time?.slice(0, 10) || ''
  form.category = record.category || ''
  form.tags = record.tags ? record.tags.split(',').map(t => t.trim()).filter(Boolean) : []
  form.notes = record.notes || ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const data: Record<string, unknown> = {
    title: form.title.trim(),
    level_of_happiness: form.level_of_happiness,
    time: form.time,
    category: form.category || null,
    tags: form.tags.length ? form.tags.join(',') : null,
    notes: form.notes?.trim() || null,
  }

  try {
    if (editingId.value) {
      await store.updateExistingSugar(editingId.value, data)
      ElMessage.success('更新成功')
    } else {
      await store.createNewSugar(data)
      ElMessage.success(`已记录 +${expectedReward.value} 元奖励`)
    }
    dialogVisible.value = false
    await refreshAll()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(record: SugarRecord) {
  try {
    await ElMessageBox.confirm(
      `确定删除"${record.title}"吗？将扣回 ${record.reward_amount} 元奖励。`,
      '提示',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await store.deleteExistingSugar(record.s_id)
    ElMessage.success('已删除')
    await refreshAll()
  } catch { /* 取消 */ }
}

function getFilters(): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  if (filterYear.value) params.year = filterYear.value
  if (filterMonth.value) params.month = filterMonth.value
  if (filterCategory.value) params.category = filterCategory.value
  return params
}

async function fetchData() {
  store.currentPage = 1
  const params = getFilters()
  await store.fetchSugarList(params)
}

async function refreshAll() {
  try {
    const poolRes = await getRewardPool()
    poolBalance.value = poolRes.data?.balance || 0
  } catch { /* ignore */ }
  const filters = getFilters()
  await Promise.all([
    store.fetchSugarList(filters),
    store.fetchCategories(filters),
  ])
}

onMounted(() => {
  refreshAll()
})

function formatMoney(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return isNaN(n) ? '0.00' : n.toFixed(2)
}
</script>

<style scoped lang="scss">
.sugar-page {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;
}

// ========== 页面标题 ==========
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    .module-tag { font-size: 12px; }
  }
  .header-actions { display: flex; gap: 8px; }
}

// ========== 统计卡片 ==========
.stats-row { margin-bottom: 20px; }

.stat-card {
  border: 1px solid #E5E7EB;
  border-radius: 16px;

  :deep(.el-card__body) { padding: 20px; }

  .stat-content {
    display: flex;
    align-items: center;
    gap: 14px;

    .stat-icon {
      width: 44px;
      height: 44px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      flex-shrink: 0;
    }

    .stat-info {
      .stat-value { font-size: 22px; font-weight: 700; line-height: 1; margin-bottom: 4px; }
      .stat-label { font-size: 13px; color: #6B7280; }
    }
  }
}

// ========== 筛选栏 ==========
.filter-card {
  margin-bottom: 20px;
  border: 1px solid #E5E7EB;
  border-radius: 16px;

  :deep(.el-card__body) { padding: 16px 20px; }

  .filter-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;

    .filter-left { display: flex; gap: 10px; flex-wrap: wrap; }
    .filter-select { width: 130px; }

    .filter-right {
      .total-reward {
        font-size: 13px;
        color: #10B981;
        font-weight: 600;
        padding: 6px 14px;
        background: #D1FAE5;
        border-radius: 8px;
      }
    }
  }
}

// ========== 小确幸列表 ==========
.sugar-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

// ========== 分页 ==========
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 24px;
  padding: 16px 0;
}

// ========== 弹窗 ==========
.sugar-form {
  .form-section-label {
    font-size: 13px;
    color: #6B7280;
    margin-bottom: 6px;
    font-weight: 500;
  }
}

.dialog-footer { display: flex; justify-content: flex-end; gap: 12px; }
</style>
