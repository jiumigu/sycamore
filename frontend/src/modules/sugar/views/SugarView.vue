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
              <div class="stat-value" style="color: #059669">¥{{ formatAmount(poolBalance) }}</div>
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
          <span class="total-reward">累计奖励+¥{{ formatAmount(stats.totalReward) }}</span>
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
                <el-slider v-model="form.level_of_happiness" :min="happinessMin" :max="happinessMax" show-stops />
                <span class="happiness-label">{{ happinessPreview }}</span>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="奖励">
              <span class="reward-display">💰 ¥{{ rewardAmount }}</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="发生日期">
          <div class="date-row">
            <el-date-picker
              v-model="form.event_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="默认当天"
              class="date-picker"
            />
            <el-button link type="primary" size="small" @click="form.event_date = todayStr">
              回到今天
            </el-button>
          </div>
        </el-form-item>

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
import { CATEGORY_OPTIONS, JOY_TYPE_OPTIONS, happinessLabelOf } from '../types/sugarTypes'
import type { SugarRecord } from '../types/sugarTypes'
import SugarCard from '../components/SugarCard.vue'
import { getRewardPool } from '@/modules/reward/api/rewardApi'
import { getPresetByType } from '@/shared/api/coreApi'
import { formatAmount } from '@/shared/utils/format'

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
  event_date: '',
})

// ─── 「今天」只此一把尺子 ───
//
// 🔴 必须用**本地**日期（getFullYear/getMonth/getDate 都是本地时区，项目 Asia/Shanghai）。
//    曾经用的是 `new Date().toISOString().slice(0, 10)` —— 那是 **UTC**，
//    在东八区 00:00–08:00 之间会算出「昨天」⇒ 凌晨打开弹窗，默认值比当天少一天。
//    现在录入默认值与提交兜底**共用这一份**，不再有第二把尺子。
const todayStr = computed(() => {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
})

const showTagInput = ref(false)
const newTag = ref('')
const tagInputRef = ref<HTMLInputElement>()

const rules = {
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
  level_of_happiness: [{ required: true, message: '请选择快乐程度', trigger: 'change' }],
}

const presetTags = ref<string[]>([])
const customTags = computed(() => {
  return form.tagList.filter(t => !presetTags.value.includes(t))
})

async function loadPresetTags() {
  try {
    const res = await getPresetByType('sugar_tags')
    presetTags.value = res.data.values || []
  } catch {
    presetTags.value = []
  }
}

// ─── 快乐程度：档位词与区间一律取自后端下发的表（前端零副本） ───
//
// 这里曾经有一张 16 个词的 `happinessTexts`（12 → 「非常开心」），
// 而列表卡片显示的是后端 `reward_label`（12 → 「很高兴」）——
// 同一个分数在弹窗与列表说两个词。现在两处都读 `happiness_bands`。
//
// ⚠️ 下面两个 `?? 5 / ?? 20` 只是「表还没到」时的占位（挂载即拉，毫秒级）；
//    真正的区间由后端下发，以后改区间不必动前端。
const happinessMin = computed(() => store.happinessBands?.min ?? 5)
const happinessMax = computed(() => store.happinessBands?.max ?? 20)

const happinessPreview = computed(() => {
  const level = form.level_of_happiness
  const label = happinessLabelOf(store.happinessBands, level)
  return label ? `${level} — ${label}` : String(level)
})

const rewardAmount = computed(() => form.level_of_happiness)

const SUGGESTED_TAGS = ['惊喜', '感动', '成就', '小确幸', '美食', '友情', '家庭', '自然', '成长', '放松']

function resetForm() {
  form.content = ''
  form.level_of_happiness = 10
  form.joy_type = ''
  form.tagList = []
  form.notes = ''
  form.event_date = todayStr.value
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
  form.event_date = record.time?.slice(0, 10) || ''
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
    time: form.event_date || todayStr.value,
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
      // 奖励金额 = 快乐程度（后端 `perform_create` 的口径，与按钮上的「得 N 元奖励」同源）。
      // 这里曾经写的是另一套「1/3/5/8/10」的分档映射 —— 那句提示会说谎
      // （选 12 分时提示「+5 元」，实际入库 +12）。
      ElMessage.success(`已记录 +${form.level_of_happiness} 元奖励`)
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
      `确定删除"${record.title}"吗？将扣回 ${formatAmount(record.reward_amount)} 元奖励。`,
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
  loadPresetTags()
  // 档位表（录入弹窗的实时预览用）；取不到只影响那一个词，不影响列表
  store.fetchHappinessBands()
})
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

.date-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;

  .date-picker { flex: 1; }
}

.dialog-footer { display: flex; justify-content: flex-end; gap: 12px; }
</style>
