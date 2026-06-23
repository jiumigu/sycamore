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
        <el-button @click="$router.push('/sugar/joy-types')">
          <el-icon><DataAnalysis /></el-icon>
          偏好图谱
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
      width="520px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="3" placeholder="记录今天的小确幸..." maxlength="100" show-word-limit />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="16">
            <el-form-item label="快乐程度">
              <div class="happiness-slider">
                <el-slider v-model="form.level_of_happiness" :min="5" :max="20" show-stops />
                <span class="happiness-label">{{ form.level_of_happiness }} — {{ happinessText }}</span>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="奖励">
              <span class="reward-display">💰 ¥{{ rewardAmount }}</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="快乐类型" prop="joy_type">
          <el-select v-model="form.joy_type" placeholder="选填" clearable style="width:100%">
            <el-option v-for="j in JOY_TYPE_OPTIONS" :key="j.value" :label="`${j.icon} ${j.label}`" :value="j.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="标签">
          <div class="tags-wrapper">
            <span class="preset-label">常用：</span>
            <el-tag
              v-for="tag in presetTags"
              :key="tag"
              size="small"
              :class="{ selected: form.tagList.includes(tag) }"
              class="preset-tag"
              @click="togglePresetTag(tag)"
            >
              {{ tag }}
            </el-tag>

            <el-tag
              v-for="tag in customTags"
              :key="tag"
              closable
              size="small"
              type="warning"
              @close="removeTag(tag)"
            >
              {{ tag }}
            </el-tag>
            <el-input
              v-if="showTagInput"
              v-model="newTag"
              ref="tagInputRef"
              size="small"
              style="width:80px"
              @keyup.enter="addTag"
              @blur="addTag"
            />
            <el-button v-else size="small" @click="showTagInput = true">+ 自定义</el-button>
          </div>
        </el-form-item>

        <el-form-item label="备注" prop="notes">
          <el-input v-model="form.notes" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="补充说明..." />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="store.submitting" @click="handleSubmit">
            得{{ form.level_of_happiness }}元奖励
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus, Refresh, DataAnalysis } from '@element-plus/icons-vue'
import { useSugarStore } from '../stores/sugarStore'
import { CATEGORY_OPTIONS, JOY_TYPE_OPTIONS } from '../types/sugarTypes'
import type { SugarRecord } from '../types/sugarTypes'
import SugarCard from '../components/SugarCard.vue'
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
  content: '',
  level_of_happiness: 10,
  joy_type: '',
  tagList: [] as string[],
  notes: '',
})

const showTagInput = ref(false)
const newTag = ref('')
const tagInputRef = ref<HTMLInputElement>()

const rules = {
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
  level_of_happiness: [{ required: true, message: '请选择快乐程度', trigger: 'change' }],
}

const presetTags = ['美食', '旅行', '人际关系', '学习成长', '工作成就', '自然', '音乐', '阅读', '运动', '意外惊喜']

const customTags = computed(() => {
  return form.tagList.filter(t => !presetTags.includes(t))
})

const happinessTexts: Record<number, string> = {
  5: '一般般', 6: '还行', 7: '还不错', 8: '挺开心', 9: '很开心', 10: '超开心',
  11: '特别开心', 12: '非常开心', 13: '极度开心', 14: '幸福爆棚', 15: '人生巅峰',
  16: '无与伦比', 17: '心花怒放', 18: '飘飘欲仙', 19: '天堂般', 20: '无可超越',
}

const happinessText = computed(() => {
  return happinessTexts[form.level_of_happiness] || '开心'
})

const rewardAmount = computed(() => form.level_of_happiness)

const SUGGESTED_TAGS = ['惊喜', '感动', '成就', '小确幸', '美食', '友情', '家庭', '自然', '成长', '放松']

const expectedReward = computed(() => {
  const v = form.level_of_happiness
  if (v <= 7) return '1'
  if (v <= 10) return '3'
  if (v <= 13) return '5'
  if (v <= 16) return '8'
  return '10'
})

function resetForm() {
  form.content = ''
  form.level_of_happiness = 10
  form.joy_type = ''
  form.tagList = []
  form.notes = ''
  showTagInput.value = false
  newTag.value = ''
}

function togglePresetTag(tag: string) {
  if (form.tagList.includes(tag)) {
    form.tagList = form.tagList.filter(t => t !== tag)
  } else {
    form.tagList.push(tag)
  }
}

function addTag() {
  const tag = newTag.value.trim()
  if (tag && !form.tagList.includes(tag)) {
    form.tagList.push(tag)
  }
  newTag.value = ''
  showTagInput.value = false
}

function removeTag(tag: string) {
  form.tagList = form.tagList.filter(t => t !== tag)
}

function openCreate() {
  editingId.value = undefined
  resetForm()
  dialogVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

function openEdit(record: SugarRecord) {
  editingId.value = record.s_id
  form.content = record.title
  form.level_of_happiness = Number(record.level_of_happiness) || 10
  form.joy_type = record.joy_type || ''
  form.tagList = record.tags ? record.tags.split(',').map(t => t.trim()).filter(Boolean) : []
  form.notes = record.notes || ''
  dialogVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const data: Record<string, unknown> = {
    title: form.content.trim(),
    level_of_happiness: form.level_of_happiness,
    reward_amount: form.level_of_happiness,
    time: new Date().toISOString().slice(0, 10),
    category: null,
    joy_type: form.joy_type || '',
    tags: form.tagList.length ? form.tagList.join(',') : null,
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

.happiness-slider {
  width: 100%;
  .happiness-label {
    display: block;
    font-size: 13px;
    color: #666;
    margin-top: 4px;
  }
}

.reward-display {
  font-size: 18px;
  font-weight: 700;
  color: #e6a23c;
  line-height: 40px;
}

.tags-wrapper {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.preset-label {
  font-size: 12px;
  color: #999;
  flex-shrink: 0;
}

.preset-tag {
  cursor: pointer;
  transition: all 0.2s;

  &:hover { opacity: 0.8; }

  &.selected {
    background: #ecf5ff;
    border-color: #409eff;
    color: #409eff;
  }
}

.dialog-footer { display: flex; justify-content: flex-end; gap: 12px; }
</style>
