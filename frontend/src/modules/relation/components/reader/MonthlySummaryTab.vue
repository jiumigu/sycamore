<template>
  <div class="monthly-summary-tab">
    <!-- 操作栏 -->
    <div class="tab-actions">
      <el-button type="primary" @click="handleAdd">+ 新增复盘</el-button>
      <el-select v-model="filterYear" placeholder="选择年份" clearable style="width: 120px" @change="handleYearChange">
        <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
      </el-select>
    </div>

    <!-- 年度统计卡片 -->
    <el-row :gutter="16" class="stats-row" v-if="store.yearlyStats">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">{{ periodLabel }}新增关注</div>
          <div class="stat-value text-green">{{ signedText(store.yearlyStats.total_new_followers, '+') }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">{{ periodLabel }}取关</div>
          <div class="stat-value text-red">{{ signedText(store.yearlyStats.total_new_unfollowers, '-') }}</div>
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
      <div class="best-month-header">🏆 最佳月份</div>
      <div class="best-month-body">
        <span class="best-month-name">{{ store.yearlyStats.best_month.year }}年{{ store.yearlyStats.best_month.month }}月</span>
        <span class="best-month-stat">新增关注 {{ signedText(store.yearlyStats.best_month.new_followers, '+') }}</span>
        <span v-if="store.yearlyStats.best_month.top_article" class="best-month-article">
          📄 {{ store.yearlyStats.best_month.top_article }}
          <template v-if="store.yearlyStats.best_month.top_article_views !== null">
            · {{ store.yearlyStats.best_month.top_article_views }} 阅读
          </template>
        </span>
        <span class="best-month-stat">{{ periodLabel }}发文 {{ store.yearlyStats.total_published ?? '—' }} 篇</span>
        <span class="best-month-stat">单篇最高阅读 {{ store.yearlyStats.max_article_views ?? '—' }}</span>
      </div>
    </el-card>

    <!-- 复盘列表 -->
    <el-card shadow="hover">
      <template #header>
        <div class="section-header">
          <span>📋 {{ filterYear ? `${filterYear}年` : '全部' }}复盘记录 ({{ store.monthlySummaries.length }})</span>
        </div>
      </template>

      <el-table v-loading="store.loading" :data="store.monthlySummaries" style="width: 100%" empty-text="暂无复盘记录">
        <el-table-column label="年月" width="100">
          <template #default="{ row }">{{ row.year }}.{{ String(row.month).padStart(2, '0') }}</template>
        </el-table-column>
        <!-- 只有一个群体时这一列恒等于「公众号读者」，不占位置 -->
        <el-table-column v-if="store.groups.length > 1" prop="group_name" label="群体" width="100" />
        <el-table-column label="发文" width="80" align="right">
          <template #default="{ row }">
            <span>{{ row.published_count === null ? '—' : row.published_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="新增关注" width="90" align="right">
          <template #default="{ row }"><span class="text-green">{{ signedText(row.new_followers, '+') }}</span></template>
        </el-table-column>
        <el-table-column label="取关" width="70" align="right">
          <template #default="{ row }"><span class="text-red">{{ signedText(row.new_unfollowers, '-') }}</span></template>
        </el-table-column>
        <el-table-column prop="total_followers" label="总关注" width="80" align="right" />
        <el-table-column prop="total_interactions" label="互动" width="60" align="right" />
        <el-table-column label="最佳文章" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="article-link">{{ row.top_article || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最高阅读" width="90" align="right">
          <template #default="{ row }">
            <span>{{ row.top_article_views === null ? '—' : row.top_article_views }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="118" align="center" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button size="small" @click="handleEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑复盘弹窗 -->
    <el-dialog v-model="showDialog" :title="editingId ? '编辑复盘' : '月末复盘'" width="450px" :close-on-click-modal="false">
      <el-form :model="form" label-width="120px" label-position="left">
        <el-form-item label="年月">
          <el-date-picker v-model="form.yearmon" type="month" value-format="YYYY-MM" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="store.groups.length > 1" label="所属群体">
          <el-select v-model="defaultGroupId" placeholder="选择群体" style="width: 100%">
            <el-option v-for="g in store.groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="本月发文篇数">
          <el-input-number v-model="form.published_count" :min="0" :value-on-clear="null" style="width: 100%" />
          <div class="auto-tip">留空 = 本月没盘；0 = 确实一篇没发</div>
        </el-form-item>
        <el-form-item label="本月新增关注">
          <el-input-number v-model="form.new_followers" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="本月取关">
          <el-input-number :model-value="autoCalcUnfollow ?? undefined" :disabled="true" style="width: 100%" />
          <div class="auto-tip">{{ unfollowTip }}</div>
        </el-form-item>
        <el-form-item label="截至本月总关注">
          <el-input-number v-model="form.total_followers" :min="0" :value-on-clear="null" style="width: 100%" />
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
        <el-form-item label="最佳文章阅读数">
          <el-input-number v-model="form.top_article_views" :min="0" :value-on-clear="null" style="width: 100%" />
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
import { apiErrorText } from '@/shared/utils/apiError'
import { todayLocal } from '@/shared/utils/datetime'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref, computed, watch } from 'vue'
import { useReaderStore } from '../../stores/readerStore'
import type { ReaderMonthlySummary } from '../../types/readerTypes'

const store = useReaderStore()

/** 增减量带符号的显示：0 不写成「+0」/「-0」，空值给「—」 */
function signedText(n: number | null | undefined, sign: '+' | '-') {
  if (n === null || n === undefined) return '—'
  return n === 0 ? '0' : `${sign}${n}`
}

const showDialog = ref(false)
const filterYear = ref(new Date().getFullYear())
const editingId = ref<number | null>(null)
const defaultGroupId = ref<number | null>(null)

const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return [y, y - 1, y - 2, y - 3]
})

/** 选了年份才叫「全年」；不选年份看的是全期合计，别让「全年」跨到全期上 */
const periodLabel = computed(() => (filterYear.value ? '全年' : '全期'))

const form = reactive({
  yearmon: '',
  published_count: null as number | null,
  new_followers: 0,
  // 🔴 不默认 0：粉丝数是要手填的（三个数之一），默认 0 忘了改就会把总关注记成断崖
  total_followers: null as number | null,
  total_interactions: 0,
  high_energy_count: 0,
  top_article: '',
  top_article_views: null as number | null,
  notes: '',
})

function resetForm() {
  form.yearmon = ''
  form.published_count = null
  form.new_followers = 0
  form.total_followers = null
  form.total_interactions = 0
  form.high_energy_count = 0
  form.top_article = ''
  form.top_article_views = null
  form.notes = ''
}

function handleAdd() {
  editingId.value = null
  resetForm()
  // 🔴 不能用 `new Date().toISOString().slice(0, 7)`：那是 UTC，晚上 8 点后点「新增」
  //    会把月份填成下个月（月初 0-8 点则填成上个月），而且填出来的值看起来合法、不会报错。
  form.yearmon = todayLocal().slice(0, 7)
  showDialog.value = true
}

function handleEdit(row: ReaderMonthlySummary) {
  editingId.value = row.id
  defaultGroupId.value = row.reader_group
  form.yearmon = `${row.year}-${String(row.month).padStart(2, '0')}`
  form.new_followers = row.new_followers
  form.total_followers = row.total_followers
  form.total_interactions = row.total_interactions
  form.high_energy_count = row.high_energy_count
  form.published_count = row.published_count
  form.top_article = row.top_article || ''
  form.top_article_views = row.top_article_views
  form.notes = row.notes || ''
  showDialog.value = true
}

/** 上月那条复盘记录：算「取关」必须真拿到，拿不到就说拿不到，不当 0 */
const prevRow = ref<ReaderMonthlySummary | null>(null)

watch(
  [() => form.yearmon, defaultGroupId],
  async () => {
    if (!form.yearmon) {
      prevRow.value = null
      return
    }
    const [year, month] = form.yearmon.split('-').map(Number)
    const prevMonth = month === 1 ? 12 : month - 1
    const prevYear = month === 1 ? year - 1 : year
    prevRow.value = await store.findMonthSummary(prevYear, prevMonth, defaultGroupId.value)
  },
  { immediate: true },
)

/** 取关 = 上月总关注 + 本月新增 − 本月总关注；任一端缺失给 null，不静默算成 0 */
const autoCalcUnfollow = computed<number | null>(() => {
  if (!prevRow.value || form.total_followers === null) return null
  return Math.max(0, prevRow.value.total_followers + form.new_followers - form.total_followers)
})

/** 「本月取关」下面那行提示：三种状态各自说清楚，别用一个 0 糊过去 */
const unfollowTip = computed(() => {
  if (!form.yearmon) return '先选年月'
  if (!prevRow.value) return '缺上月复盘记录，取关算不出来（请先补上月）'
  if (form.total_followers === null) return '填完「截至本月总关注」后自动算'
  return `自动计算：${autoCalcUnfollow.value} 人`
})

function handleYearChange() {
  // 清空年份 = 显式不筛（`{}`），不能传 undefined：那在 store 里表示「沿用上次条件」
  const params = filterYear.value ? { year: filterYear.value } : {}
  store.fetchMonthlySummaries(params)
  store.fetchYearlyStats(params)
}

async function saveSummary() {
  if (!form.yearmon) {
    ElMessage.warning('请先选年月')
    return
  }
  if (!defaultGroupId.value) {
    ElMessage.warning('请先选所属群体')
    return
  }
  if (form.total_followers === null) {
    ElMessage.warning('请填「截至本月总关注」')
    return
  }
  if (autoCalcUnfollow.value === null) {
    ElMessage.warning('缺上月复盘记录，取关算不出来，请先补上月那条')
    return
  }
  const [year, month] = form.yearmon.split('-')
  const data = {
    reader_group: defaultGroupId.value,
    year: parseInt(year),
    month: parseInt(month),
    new_followers: form.new_followers,
    new_unfollowers: autoCalcUnfollow.value,
    total_followers: form.total_followers,
    total_interactions: form.total_interactions,
    high_energy_count: form.high_energy_count,
    published_count: form.published_count,
    top_article: form.top_article,
    top_article_views: form.top_article_views,
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
  } catch (err) {
    ElMessage.error(apiErrorText(err, '保存失败'))
  }
}

async function handleDelete(row: { id: number }) {
  try {
    await ElMessageBox.confirm('确定删除这条复盘记录吗？', '确认删除', {
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
  // 群体列表写进 store：表单里「所属群体」和表格里「群体」列都看 store.groups
  await store.fetchGroups()
  // 默认选中"公众号读者"
  const defaultGroup = store.groups.find((g) => g.name === '公众号读者')
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
  /* 一行放不下就换行：这一行现在有五个数（月份 / 新增 / 文章 / 全年发文 / 最高阅读） */
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
  gap: 12px 16px;
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
