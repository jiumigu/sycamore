<template>
  <div class="free-spending">
    <div class="back-bar">
      <el-button text @click="$router.push('/toolkit')">
        <el-icon><ArrowLeft /></el-icon> 返回工具集
      </el-button>
    </div>
    <el-card class="calc-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">💰 自由支配额度计算器</span>
          <el-tag size="small" type="warning" effect="plain">每次消费不超过这个数，就不用纠结</el-tag>
        </div>
      </template>

      <p class="subtitle">精力花在决策上就是浪费。这个数字以下的东西，直接买，不用想。</p>

      <el-form :model="form" label-width="150px" size="small">
        <el-form-item label="可支配流动资产">
          <el-input-number v-model="form.liquid_assets" :min="0" :precision="2" style="width:100%" placeholder="存款+股票+基金等" />
          <div class="hint">存款、股票、基金等能迅速变现的资产（不含房子、车子）</div>
        </el-form-item>

        <el-form-item label="年稳定收入">
          <el-input-number v-model="form.annual_income" :min="0" :precision="2" style="width:100%" placeholder="税后年收入" />
          <div class="hint">税后年收入。收入不稳定可保守估算</div>
        </el-form-item>

        <el-form-item label="固定债务">
          <el-input-number v-model="form.debt" :min="0" :precision="2" style="width:100%" placeholder="房贷、车贷等" />
          <div class="hint">房贷、车贷等固定负债（选填）</div>
        </el-form-item>

        <el-form-item label="预计工作年限">
          <el-input-number v-model="form.work_years" :min="1" :max="40" style="width:150px" />
          <span class="suffix">年（默认20年）</span>
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="form.notes" placeholder="选填，记录计算时的想法" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleCalculate">计算</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 计算结果 -->
    <el-card v-if="result !== null" shadow="hover" class="result-card">
      <template #header><span class="card-title">📊 计算结果</span></template>
      <div class="formula">
        (¥{{ fmt(form.liquid_assets) }} + ¥{{ fmt(form.annual_income) }} × {{ form.work_years }}) ÷ 10000
      </div>
      <div v-if="form.debt > 0" class="formula-small">
        扣除债务：(¥{{ fmt(form.liquid_assets) }} − ¥{{ fmt(form.debt) }} + ¥{{ fmt(form.annual_income) }} × {{ form.work_years }}) ÷ 10000
      </div>
      <div class="result-value">¥{{ result }}</div>
      <div class="result-desc">每次消费 ≤ ¥{{ result }}，无需纠结，自由支配。</div>
      <el-alert type="info" :closable="false" class="result-tip">
        超过这个金额才需要谨慎考虑。把省下来的精力投入到能提升收入的大事上。
      </el-alert>
    </el-card>

    <!-- 历史记录 -->
    <el-card class="history-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📋 计算历史</span>
          <el-tag size="small">{{ history.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="history" v-loading="loading" stripe size="small" style="width:100%">
        <el-table-column prop="created_at" label="日期" width="90">
          <template #default="{ row }">{{ row.created_at?.slice(0, 10) }}</template>
        </el-table-column>
        <el-table-column label="资产" width="120">
          <template #default="{ row }">¥{{ fmt(row.liquid_assets) }}</template>
        </el-table-column>
        <el-table-column label="年收入" width="100">
          <template #default="{ row }">¥{{ fmt(row.annual_income) }}</template>
        </el-table-column>
        <el-table-column label="债务" width="90">
          <template #default="{ row }">¥{{ fmt(row.debt) }}</template>
        </el-table-column>
        <el-table-column label="额度" width="100">
          <template #default="{ row }">¥{{ row.free_amount }}</template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="100" show-overflow-tooltip />
        <el-table-column label="操作" width="60" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && history.length === 0" description="暂无计算记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getFreeSpendingList, createFreeSpending, deleteFreeSpending } from '../../api/toolkitApi'
import type { FreeSpendingRecord } from '../../types/toolkitTypes'

const form = reactive({
  liquid_assets: 0,
  annual_income: 0,
  debt: 0,
  work_years: 20,
  notes: '',
})

const result = ref<number | null>(null)
const saving = ref(false)
const loading = ref(false)
const history = ref<FreeSpendingRecord[]>([])

function fmt(val: number | string) {
  const n = typeof val === 'string' ? parseFloat(val) : val
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function fetchHistory() {
  loading.value = true
  try {
    const res = await getFreeSpendingList()
    history.value = (res.data?.results || []) as FreeSpendingRecord[]
  } catch {
    history.value = []
  } finally {
    loading.value = false
  }
}

async function handleCalculate() {
  saving.value = true
  try {
    const netAssets = form.liquid_assets - form.debt
    const total = netAssets + form.annual_income * form.work_years
    const amount = Math.round(total / 10000)

    result.value = amount
    const payload = { ...form, free_amount: amount }
    await createFreeSpending(payload)
    ElMessage.success('已保存')
    await fetchHistory()
  } catch {
    ElMessage.error('计算保存失败')
  } finally {
    saving.value = false
  }
}

function resetForm() {
  form.liquid_assets = 0
  form.annual_income = 0
  form.debt = 0
  form.work_years = 20
  form.notes = ''
  result.value = null
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除这条记录？', '确认删除', { type: 'warning' })
    await deleteFreeSpending(id)
    ElMessage.success('已删除')
    await fetchHistory()
  } catch { /* cancelled */ }
}

onMounted(fetchHistory)
</script>

<style scoped>
.free-spending { margin: 0 auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; align-items: center; gap: 10px; }
.card-title { font-size: 14px; font-weight: 600; }
.subtitle { font-size: 13px; color: var(--el-text-color-secondary); margin: -8px 0 4px; }
.hint { font-size: 11px; color: var(--el-text-color-secondary); line-height: 1.4; margin-top: 2px; }
.suffix { font-size: 12px; color: var(--el-text-color-secondary); margin-left: 8px; }
.calc-card :deep(.el-card__body) { padding: 16px 20px; }
.result-card { border: 1px solid var(--el-color-primary-light-5); }
.result-card :deep(.el-card__body) { padding: 20px; text-align: center; }
.formula { font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 4px; font-family: monospace; }
.formula-small { font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; font-family: monospace; }
.result-value { font-size: 48px; font-weight: 800; color: var(--el-color-primary); margin: 12px 0 8px; line-height: 1.1; }
.result-desc { font-size: 14px; color: var(--el-text-color-primary); margin-bottom: 4px; }
.result-tip { text-align: left; }
.history-card :deep(.el-card__body) { padding: 12px 16px 16px; }
.back-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; flex-wrap: nowrap; }
</style>
