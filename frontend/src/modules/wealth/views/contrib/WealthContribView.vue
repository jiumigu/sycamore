<template>
  <div class="contrib-page">
    <div class="page-header">
      <div class="header-left">
        <el-button size="small" @click="$router.push('/wealth')">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <h2 class="page-title">{{ title }}</h2>
        <el-tag size="small" type="info">单日收支净值（绿=收入多 / 红=支出多）</el-tag>
      </div>
      <el-button size="small" @click="load(true)">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <el-card v-loading="loading">
      <ContributionGraph
        v-if="graphData.length"
        :data="graphData"
        :min-year="minYear"
        :max-year="maxYear"
        :title="title"
        :unit-label="unitLabel"
        :positive-negative="posNeg"
        @cell-click="onCellClick"
      />
      <el-empty v-else-if="!loading" description="暂无数据" />
    </el-card>

    <DailyDetailDialog
      v-model:visible="detailVisible"
      :title="`${detailDate} 账单`"
      :data="detailItems"
      :columns="detailColumns"
      :loading="detailLoading"
      :summary="detailSummary"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import ContributionGraph from '@/shared/components/ContributionGraph.vue'
import DailyDetailDialog from '@/shared/components/DailyDetailDialog.vue'
import { getBillDailyDetail } from '@/modules/wealth/api/wealthApi'
import * as wealthApi from '@/modules/wealth/api/wealthApi'

const title = '财富贡献图'
const unitLabel = '元'
const posNeg = true
const graphData = ref<Array<{ date: string; value: number }>>([])
const minYear = ref(2020)
const maxYear = ref(new Date().getFullYear())
const loading = ref(false)

// ─── 每日明细弹窗 ───
const detailVisible = ref(false)
const detailDate = ref('')
const detailItems = ref<any[]>([])
const detailLoading = ref(false)
const detailSummary = ref('')
const detailColumns = [
  { prop: 'time', label: '时间', width: 130, formatter: (v: string) => v ? v.slice(0, 16) : '' },
  { prop: 'transaction_type', label: '收支', width: 70 },
  { prop: 'category', label: '分类', width: 100 },
  { prop: 'merchant', label: '商户', minWidth: 120 },
  { prop: 'amount', label: '金额', width: 100, align: 'right' as const },
  { prop: 'notes', label: '备注', minWidth: 120 },
]

async function onCellClick(date: string) {
  detailDate.value = date
  detailVisible.value = true
  detailItems.value = []
  detailSummary.value = ''
  detailLoading.value = true
  try {
    const res = await getBillDailyDetail({ date })
    const data: any = res.data
    detailItems.value = data.items || []
    detailSummary.value = data.items?.length ? `收入 ¥${data.income} · 支出 ¥${data.expense}` : ''
  } catch {
    ElMessage.error('获取明细失败')
  } finally {
    detailLoading.value = false
  }
}

const CACHE_KEY = 'contrib_cache_WealthContribView'

async function load(force = false) {
  loading.value = true
  try {
    if (!force) {
      const cached = localStorage.getItem(CACHE_KEY)
      if (cached) {
        const parsed = JSON.parse(cached)
        if (Date.now() - parsed.ts < 30 * 60 * 1000) {
          applyData(parsed.body)
          loading.value = false
          return
        }
      }
    }
    const res = await wealthApi.getBillContrib()
    applyData(res.data)
    localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), body: res.data }))
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function applyData(body: any) {
  graphData.value = body.data || []
  minYear.value = body.min_year || minYear.value
  maxYear.value = body.max_year || maxYear.value
}

onMounted(() => load())
</script>

<style scoped>
.contrib-page { padding: 16px; }
.page-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.page-title { margin: 0; font-size: 18px; font-weight: 600; }
</style>
