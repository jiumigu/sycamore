<template>
  <div class="contrib-page">
    <div class="page-header">
      <div class="header-left">
        <el-button size="small" @click="$router.push('/temporal')">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <h2 class="page-title">{{ title }}</h2>
        <el-select v-model="metric" size="small" style="width:130px" @change="load(true)">
          <el-option v-for="m in METRICS" :key="m.value" :label="m.label" :value="m.value" />
        </el-select>
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
      :title="`${detailDate} 时间任务`"
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
import { getTaskDailyDetail } from '@/modules/temporal/api/temporalApi'
import * as temporalApi from '@/modules/temporal/api/temporalApi'

const title = '时间贡献图'
const unitLabel = '小时'
const posNeg = false
const graphData = ref<Array<{ date: string; value: number }>>([])
const minYear = ref(2020)
const maxYear = ref(new Date().getFullYear())
const loading = ref(false)

const METRICS = [
  { value: 'record_count', label: '记录数', unit: '次' },
  { value: 'hours', label: '小时', unit: '小时' },
  { value: 'toward', label: '投向小时', unit: '小时' },
  { value: 'deepwork', label: '深度工作小时', unit: '小时' },
  { value: 'sleep', label: '睡眠小时', unit: '小时' },
]
const metric = ref('record_count')

// ─── 每日明细弹窗 ───
const detailVisible = ref(false)
const detailDate = ref('')
const detailItems = ref<any[]>([])
const detailLoading = ref(false)
const detailSummary = ref('')
const detailColumns = [
  { prop: 'start_time', label: '开始', width: 130, formatter: (v: string) => v ? v.slice(0, 16) : '' },
  { prop: 'task_name', label: '任务（L3）', minWidth: 200 },
  { prop: 'attribution', label: 'L1 归因', width: 90 },
  { prop: 'activity_type', label: 'L2 类型', width: 100 },
  { prop: 'duration_hours', label: '时长(小时)', width: 90, align: 'right' as const },
  { prop: 'notes', label: '备注', minWidth: 120 },
]

async function onCellClick(date: string) {
  detailDate.value = date
  detailVisible.value = true
  detailItems.value = []
  detailSummary.value = ''
  detailLoading.value = true
  try {
    const res = await getTaskDailyDetail({ date })
    const data: any = res.data
    detailItems.value = data.items || []
    detailSummary.value = data.items?.length ? `共 ${data.items.length} 项，总时长 ${data.total} 小时` : ''
  } catch {
    ElMessage.error('获取明细失败')
  } finally {
    detailLoading.value = false
  }
}

const CACHE_KEY = 'contrib_cache_TemporalContribView'

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
    const res = await temporalApi.getTaskContrib({ metric: metric.value })
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
