<template>
  <div class="decision-log">
    <div class="back-bar">
      <el-button text @click="$router.push('/toolkit')">
        <el-icon><ArrowLeft /></el-icon> 返回工具集
      </el-button>
    </div>
    <div class="page-header">
      <div class="header-left">
        <h2>📋 决策日志</h2>
        <el-tag size="small" type="warning">记录重大决策，分析决策偏误</el-tag>
      </div>
      <el-button type="primary" @click="showAddDialog = true">+ 新增决策</el-button>
    </div>

    <!-- 偏误洞察卡片 -->
    <el-card v-if="store.decisions.length > 0" shadow="hover" class="bias-card">
      <template #header>
        <span class="card-title">🔍 决策偏误洞察</span>
      </template>
      <el-row :gutter="16">
        <el-col :span="6" v-for="bias in biasAnalysis" :key="bias.name">
          <div class="bias-item" :class="{ highlight: bias.count > 0 }">
            <div class="bias-name">{{ bias.name }}</div>
            <div class="bias-count">{{ bias.count }}次</div>
            <div class="bias-desc">{{ bias.desc }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="filterYear" size="small" style="width: 100px" placeholder="年份">
        <el-option v-for="y in availableYears" :key="y" :label="`${y}年`" :value="y" />
      </el-select>
      <el-select v-model="filterCategory" size="small" style="width: 120px" placeholder="分类" clearable>
        <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
      </el-select>
      <span class="filter-count">共 {{ filteredDecisions.length }} 条记录</span>
    </div>

    <!-- 决策列表 -->
    <el-table :data="filteredDecisions" stripe size="small" style="width: 100%" @row-click="openReview">
      <el-table-column label="日期" width="90" prop="decision_date" />
      <el-table-column label="标题" min-width="160" prop="title" show-overflow-tooltip />
      <el-table-column label="分类" width="70">
        <template #default="{ row }">
          <el-tag size="small">{{ row.category }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="选择" min-width="120" prop="chosen" show-overflow-tooltip />
      <el-table-column label="恐惧" width="60" align="center">
        <template #default="{ row }">
          <span :style="{ color: row.fear_factor >= 7 ? '#f5222d' : row.fear_factor >= 4 ? '#faad14' : '#52c41a' }">
            {{ row.fear_factor }}/10
          </span>
        </template>
      </el-table-column>
      <el-table-column label="偏误" width="80" prop="bias_found" />
      <el-table-column label="结果" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.was_right === true" size="small" type="success">正确</el-tag>
          <el-tag v-else-if="row.was_right === false" size="small" type="danger">错误</el-tag>
          <el-tag v-else size="small" type="info">待回顾</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" @click.stop="openReview(row)">回顾</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="filteredDecisions.length === 0" description="暂无决策记录" :image-size="60" />

    <!-- 新增决策弹窗 -->
    <el-dialog v-model="showAddDialog" title="记录决策" width="680px" :close-on-click-modal="false">
      <el-form :model="form" label-position="top" size="small">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="决策标题">
              <el-input v-model="form.title" placeholder="给这个决策起个名字" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="日期">
              <el-date-picker v-model="form.decision_date" type="date" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="分类">
              <el-select v-model="form.category" style="width:100%">
                <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="背景/情境">
          <el-input v-model="form.background" type="textarea" :rows="2" placeholder="发生了什么？" />
        </el-form-item>

        <el-form-item label="选项">
          <div v-for="(opt, i) in form.options" :key="i" class="option-item">
            <div class="option-header">
              <span class="option-label">选项 {{ i + 1 }}</span>
              <el-button text type="danger" size="small" @click="removeOption(i)">删除</el-button>
            </div>
            <el-input v-model="opt.name" placeholder="选项名称" class="option-name" />
            <el-input v-model="opt.pros" placeholder="优点" class="option-detail" />
            <el-input v-model="opt.cons" placeholder="缺点" class="option-detail" />
          </div>
          <el-button size="small" @click="addOption">+ 添加选项</el-button>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="最终选择">
              <el-select v-model="form.chosen" style="width:100%" placeholder="选择一项">
                <el-option v-for="opt in form.options" :key="opt.name" :label="opt.name" :value="opt.name" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="恐惧指数">
              <el-rate v-model="form.fear_factor" :max="10" show-score style="padding:4px 0" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="选择理由">
          <el-input v-model="form.reason" type="textarea" :rows="2" placeholder="为什么选这个？" />
        </el-form-item>
        <el-form-item label="预期结果">
          <el-input v-model="form.expected_outcome" type="textarea" :rows="2" placeholder="希望发生什么？" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 回顾弹窗 -->
    <el-dialog v-model="showReviewDialog" title="决策回顾" width="600px">
      <template v-if="reviewItem">
        <div class="review-section">
          <div class="review-label">决策</div>
          <div class="review-value">{{ reviewItem.title }}（{{ reviewItem.decision_date }}）</div>
        </div>
        <div class="review-section">
          <div class="review-label">背景</div>
          <div class="review-value">{{ reviewItem.background }}</div>
        </div>
        <div class="review-section">
          <div class="review-label">选择</div>
          <div class="review-value">{{ reviewItem.chosen }}</div>
        </div>
        <div class="review-section">
          <div class="review-label">预期结果</div>
          <div class="review-value">{{ reviewItem.expected_outcome }}</div>
        </div>
        <el-form label-position="top" size="small">
          <el-form-item label="实际结果">
            <el-input v-model="reviewForm.actual_outcome" type="textarea" :rows="2" />
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="决策是否正确？">
                <el-radio-group v-model="reviewForm.was_right">
                  <el-radio :value="true">✓ 正确</el-radio>
                  <el-radio :value="false">✗ 错误</el-radio>
                  <el-radio :value="null">不确定</el-radio>
                </el-radio-group>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="发现的偏误">
                <el-select v-model="reviewForm.bias_found" style="width:100%" clearable placeholder="选择偏误类型">
                  <el-option v-for="b in COMMON_BIASES" :key="b" :label="b" :value="b" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="学到的经验">
            <el-input v-model="reviewForm.learned" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="showReviewDialog = false">取消</el-button>
        <el-button type="primary" @click="handleReview">保存回顾</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import {
  getDecisionLogs, createDecisionLog, updateDecisionLog,
  type DecisionLog,
} from '../../api/decisionLogApi'

const CATEGORIES = ['职业', '关系', '财务', '健康', '居住', '学习', '其他']
const COMMON_BIASES = ['过度准备', '损失厌恶', '从众效应', '确认偏误', '锚定效应', '过度自信', '短视']

interface Store {
  decisions: DecisionLog[]
  loading: boolean
}

const store = ref<Store>({ decisions: [], loading: true })
const filterYear = ref(new Date().getFullYear())
const filterCategory = ref('')
const showAddDialog = ref(false)
const showReviewDialog = ref(false)
const reviewItem = ref<DecisionLog | null>(null)

const availableYears = computed(() => {
  const years = new Set<number>()
  const current = new Date().getFullYear()
  store.value.decisions.forEach(d => {
    if (d.decision_date) years.add(new Date(d.decision_date).getFullYear())
  })
  years.add(current)
  return Array.from(years).sort((a, b) => b - a)
})

const filteredDecisions = computed(() => {
  let list = store.value.decisions
  if (filterYear.value) {
    list = list.filter(d => d.decision_date && new Date(d.decision_date).getFullYear() === filterYear.value)
  }
  if (filterCategory.value) {
    list = list.filter(d => d.category === filterCategory.value)
  }
  return list
})

const biasAnalysis = computed(() => {
  const map = new Map<string, number>()
  store.value.decisions.forEach(d => {
    if (d.bias_found) {
      map.set(d.bias_found, (map.get(d.bias_found) || 0) + 1)
    }
  })
  return COMMON_BIASES.map(name => ({
    name,
    count: map.get(name) || 0,
    desc: getBiasDesc(name),
  }))
})

function getBiasDesc(name: string): string {
  const descs: Record<string, string> = {
    '过度准备': '总觉得还没准备好，迟迟不行动',
    '损失厌恶': '害怕失去远大于渴望获得',
    '从众效应': '跟随多数人的选择',
    '确认偏误': '只看到支持自己观点的信息',
    '锚定效应': '过度依赖第一个信息',
    '过度自信': '高估自己的判断能力',
    '短视': '只看眼前利益，忽视长期',
  }
  return descs[name] || ''
}

const form = ref<DecisionLog>({
  title: '',
  decision_date: new Date().toISOString().slice(0, 10),
  category: '其他',
  background: '',
  options: [{ name: '', pros: '', cons: '' }],
  chosen: '',
  reason: '',
  expected_outcome: '',
  fear_factor: 5,
  actual_outcome: '',
  was_right: null,
  learned: '',
  bias_found: '',
  review_date: null,
})

const reviewForm = ref({
  actual_outcome: '',
  was_right: null as boolean | null,
  bias_found: '',
  learned: '',
})

function addOption() {
  form.value.options.push({ name: '', pros: '', cons: '' })
}

function removeOption(i: number) {
  form.value.options.splice(i, 1)
}

async function handleSave() {
  if (!form.value.title) return
  try {
    await createDecisionLog({
      ...form.value,
      review_date: calcReviewDate(form.value.decision_date),
    })
    showAddDialog.value = false
    resetForm()
    await fetchData()
  } catch (e) {
    console.error('保存失败', e)
  }
}

function calcReviewDate(dateStr: string): string {
  const d = new Date(dateStr)
  d.setMonth(d.getMonth() + 6)
  return d.toISOString().slice(0, 10)
}

function resetForm() {
  form.value = {
    title: '',
    decision_date: new Date().toISOString().slice(0, 10),
    category: '其他',
    background: '',
    options: [{ name: '', pros: '', cons: '' }],
    chosen: '',
    reason: '',
    expected_outcome: '',
    fear_factor: 5,
    actual_outcome: '',
    was_right: null,
    learned: '',
    bias_found: '',
    review_date: null,
  }
}

function openReview(row: DecisionLog) {
  reviewItem.value = row
  reviewForm.value = {
    actual_outcome: row.actual_outcome || '',
    was_right: row.was_right,
    bias_found: row.bias_found || '',
    learned: row.learned || '',
  }
  showReviewDialog.value = true
}

async function handleReview() {
  if (!reviewItem.value?.id) return
  try {
    await updateDecisionLog(reviewItem.value.id, {
      actual_outcome: reviewForm.value.actual_outcome,
      was_right: reviewForm.value.was_right,
      bias_found: reviewForm.value.bias_found,
      learned: reviewForm.value.learned,
    })
    showReviewDialog.value = false
    await fetchData()
  } catch (e) {
    console.error('保存回顾失败', e)
  }
}

async function fetchData() {
  store.value.loading = true
  try {
    const res = await getDecisionLogs()
    store.value.decisions = res.data?.results ?? []
  } catch {
    store.value.decisions = []
  } finally {
    store.value.loading = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.decision-log {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-left h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.bias-card {
  margin-bottom: 16px;
  border: none;
  border-radius: 10px;
}

.bias-item {
  padding: 12px;
  border-radius: 8px;
  background: #F9FAFB;
  text-align: center;
  transition: all 0.2s;
}
.bias-item.highlight {
  background: #FEF3C7;
}
.bias-name {
  font-size: 14px;
  font-weight: 600;
  color: #1F2937;
}
.bias-count {
  font-size: 24px;
  font-weight: 700;
  color: #7C3AED;
  margin: 4px 0;
}
.bias-desc {
  font-size: 11px;
  color: #9CA3AF;
}

.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.filter-count {
  font-size: 12px;
  color: #9CA3AF;
}

.option-item {
  background: #F9FAFB;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
}
.option-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.option-label {
  font-size: 13px;
  font-weight: 600;
}
.option-name {
  margin-bottom: 6px;
}
.option-detail {
  margin-bottom: 4px;
}
:deep(.option-detail .el-input__inner) {
  font-size: 12px;
}

.review-section {
  margin-bottom: 12px;
}
.review-label {
  font-size: 12px;
  color: #9CA3AF;
  margin-bottom: 2px;
}
.review-value {
  font-size: 14px;
  color: #1F2937;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
}
.back-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; flex-wrap: nowrap; }
</style>
