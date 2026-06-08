<template>
  <div class="monthly-summary-tab">
    <!-- 操作栏 -->
    <div class="tab-actions">
      <el-button type="primary" @click="handleAdd">+ 新增盘点</el-button>
      <el-select v-model="filterYear" placeholder="选择年份" clearable style="width: 120px" @change="handleYearChange">
        <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
      </el-select>
    </div>

    <!-- 年度统计卡片 -->
    <el-row :gutter="16" class="stats-row" v-if="store.yearlyStats">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">全年新增关注</div>
          <div class="stat-value text-green">+{{ store.yearlyStats.total_new_followers }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">全年取关</div>
          <div class="stat-value text-red">-{{ store.yearlyStats.total_new_unfollowers }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">净增长</div>
          <div class="stat-value" :class="store.yearlyStats.net_growth >= 0 ? 'text-green' : 'text-red'">
            {{ store.yearlyStats.net_growth >= 0 ? '+' : '' }}{{ store.yearlyStats.net_growth }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">月均互动</div>
          <div class="stat-value">{{ store.yearlyStats.avg_monthly_interactions }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最佳月份 -->
    <el-card v-if="store.yearlyStats?.best_month" shadow="hover" class="best-month-card">
      <div class="best-month-header">🏆 年度最佳月份</div>
      <div class="best-month-body">
        <span class="best-month-name">{{ store.yearlyStats.best_month.month }}月</span>
        <span class="best-month-stat">互动 {{ store.yearlyStats.best_month.total_interactions }} 次</span>
        <span v-if="store.yearlyStats.best_month.top_article" class="best-month-article">
          📄 {{ store.yearlyStats.best_month.top_article }}
        </span>
      </div>
    </el-card>

    <!-- 盘点列表 -->
    <el-card shadow="hover">
      <template #header>
        <div class="section-header">
          <span>📋 {{ filterYear || '全部' }}年盘点记录 ({{ store.monthlySummaries.length }})</span>
        </div>
      </template>

      <el-table v-loading="store.loading" :data="store.monthlySummaries" style="width: 100%" empty-text="暂无盘点记录">
        <el-table-column label="年月" width="100">
          <template #default="{ row }">{{ row.year }}.{{ String(row.month).padStart(2, '0') }}</template>
        </el-table-column>
        <el-table-column prop="group_name" label="群体" width="100" />
        <el-table-column label="新增关注" width="100" align="right">
          <template #default="{ row }"><span class="text-green">+{{ row.new_followers }}</span></template>
        </el-table-column>
        <el-table-column label="取关" width="80" align="right">
          <template #default="{ row }"><span class="text-red">-{{ row.new_unfollowers }}</span></template>
        </el-table-column>
        <el-table-column prop="total_followers" label="总关注" width="80" align="right" />
        <el-table-column prop="total_interactions" label="互动" width="70" align="right" />
        <el-table-column label="最佳文章" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="article-link">{{ row.top_article || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="center" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button size="small" @click="handleEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑盘点弹窗 -->
    <el-dialog v-model="showDialog" :title="editingId ? '编辑盘点' : '月末盘点'" width="450px" :close-on-click-modal="false">
      <el-form :model="form" label-width="120px" label-position="left">
        <el-form-item label="年月">
          <el-date-picker v-model="form.yearmon" type="month" value-format="YYYY-MM" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="store.groups.length > 1" label="所属群体">
          <el-select v-model="defaultGroupId" placeholder="选择群体" style="width: 100%">
            <el-option v-for="g in store.groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="本月新增关注">
          <el-input-number v-model="form.new_followers" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="本月取关">
          <el-input-number v-model="form.new_unfollowers" :min="0" :disabled="true" style="width: 100%" />
          <div class="auto-tip">自动计算：{{ autoCalcUnfollow }}人</div>
        </el-form-item>
        <el-form-item label="截至本月总关注">
          <el-input-number v-model="form.total_followers" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="本月互动总量">
          <el-input-number v-model="form.total_interactions" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="高能量互动数">
          <el-input-number v-model="form.high_energy_count" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="本月最佳文章">
          <el-input v-model="form.top_article" placeholder="如：《如何搭建个人系统》" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="store.saving" @click="saveSummary">{{ editingId ? '保存' : '保存' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref, computed } from 'vue'
import { useReaderStore } from '../../stores/readerStore'
import * as readerApi from '../../api/readerApi'

const store = useReaderStore()

const showDialog = ref(false)
const filterYear = ref(new Date().getFullYear())
const editingId = ref<number | null>(null)
const defaultGroupId = ref<number | null>(null)

const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return [y, y - 1, y - 2, y - 3]
})

const form = reactive({
  yearmon: '',
  new_followers: 0,
  new_unfollowers: 0,
  total_followers: 0,
  total_interactions: 0,
  high_energy_count: 0,
  top_article: '',
  notes: '',
})

function resetForm() {
  form.yearmon = ''
  form.new_followers = 0
  form.new_unfollowers = 0
  form.total_followers = 0
  form.total_interactions = 0
  form.high_energy_count = 0
  form.top_article = ''
  form.notes = ''
}

function handleAdd() {
  editingId.value = null
  resetForm()
  form.yearmon = new Date().toISOString().slice(0, 7)
  showDialog.value = true
}

function handleEdit(row: typeof store.monthlySummaries.value[number]) {
  editingId.value = row.id
  defaultGroupId.value = row.reader_group
  form.yearmon = `${row.year}-${String(row.month).padStart(2, '0')}`
  form.new_followers = row.new_followers
  form.new_unfollowers = row.new_unfollowers
  form.total_followers = row.total_followers
  form.total_interactions = row.total_interactions
  form.high_energy_count = row.high_energy_count
  form.top_article = row.top_article || ''
  form.notes = row.notes || ''
  showDialog.value = true
}

/** 取关 = 上月总关注 + 本月新增 - 本月总关注 */
const autoCalcUnfollow = computed(() => {
  if (!form.yearmon) return 0
  const [year, month] = form.yearmon.split('-').map(Number)
  const prevMonth = month === 1 ? 12 : month - 1
  const prevYear = month === 1 ? year - 1 : year

  const prev = store.monthlySummaries.find(
    s => s.year === prevYear && s.month === prevMonth && s.reader_group === defaultGroupId.value,
  )
  const prevTotal = prev?.total_followers ?? 0
  if (!prevTotal && !form.new_followers) return 0

  const result = prevTotal + form.new_followers - form.total_followers
  return Math.max(0, result)
})

function handleYearChange() {
  store.fetchMonthlySummaries(filterYear.value ? { year: filterYear.value } : undefined)
  store.fetchYearlyStats(filterYear.value ? { year: filterYear.value } : undefined)
}

async function saveSummary() {
  if (!form.yearmon) return
  const [year, month] = form.yearmon.split('-')
  const data = {
    reader_group: defaultGroupId.value!,
    year: parseInt(year),
    month: parseInt(month),
    new_followers: form.new_followers,
    new_unfollowers: autoCalcUnfollow.value,
    total_followers: form.total_followers,
    total_interactions: form.total_interactions,
    high_energy_count: form.high_energy_count,
    top_article: form.top_article,
    notes: form.notes,
  }

  try {
    const isEdit = !!editingId.value
    if (isEdit) {
      await store.updateMonthlySummary(editingId.value!, data)
    } else {
      await store.createMonthlySummary(data)
    }
    showDialog.value = false
    editingId.value = null
    resetForm()
    ElMessage.success(isEdit ? '已更新' : '已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}

async function handleDelete(row: { id: number }) {
  try {
    await ElMessageBox.confirm('确定删除这条盘点记录吗？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await store.deleteMonthlySummary(row.id)
  } catch {
    // cancelled
  }
}

onMounted(async () => {
  // 默认选中"公众号读者"
  const res = await readerApi.getReaderGroups()
  const groups = Array.isArray(res.data) ? res.data : (res.data.results || [])
  const defaultGroup = groups.find((g: { name: string }) => g.name === '公众号读者')
  if (defaultGroup) {
    defaultGroupId.value = defaultGroup.id
  }

  store.fetchMonthlySummaries({ year: filterYear.value })
  store.fetchYearlyStats({ year: filterYear.value })
})
</script>

<style scoped lang="scss">
.monthly-summary-tab {
  max-width: 1100px;
}

.tab-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.stats-row { margin-bottom: 16px; }

.stat-card {
  border: none;
  border-radius: 10px;
  :deep(.el-card__body) { padding: 16px; }
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
}

.text-green { color: #389e0d; }
.text-red { color: #cf1322; }

.best-month-card {
  margin-bottom: 16px;
  border: none;
  border-radius: 10px;
  :deep(.el-card__body) {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 20px;
  }
}

.best-month-header {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

.best-month-body {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
}

.best-month-name {
  font-weight: 600;
  color: #d97706;
}

.best-month-stat {
  color: var(--el-text-color-secondary);
}

.best-month-article {
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.section-header {
  font-weight: 600;
  font-size: 14px;
}

.auto-tip {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.action-btns {
  display: flex;
  gap: 4px;
  flex-wrap: nowrap;
  white-space: nowrap;
  justify-content: center;

  :deep(.el-button) {
    padding: 4px 8px;
    font-size: 12px;
  }
}
</style>
