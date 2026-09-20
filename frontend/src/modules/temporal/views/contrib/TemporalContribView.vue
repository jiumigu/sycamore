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
        :mode="mode"
        :palette="mode === 'attribution' ? ATTRIBUTION_COLOR_MAP : undefined"
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import ContributionGraph from '@/shared/components/ContributionGraph.vue'
import DailyDetailDialog from '@/shared/components/DailyDetailDialog.vue'
import { getTaskDailyDetail } from '@/modules/temporal/api/temporalApi'
import * as temporalApi from '@/modules/temporal/api/temporalApi'
import { ATTRIBUTION_COLOR_MAP } from '@/modules/temporal/types/temporalTypes'

const title = '时间贡献图'
const posNeg = false
const graphData = ref<Array<{ date: string; value: number; attr?: string | null; breakdown?: Record<string, number> }>>([])
const minYear = ref(2020)
const maxYear = ref(new Date().getFullYear())
const loading = ref(false)

// ─── 视图口径 ───
// value       = 量值热度（题面：记录数 / 小时 / 成长小时 / 深度工作 / 牛马工作）
// attribution = 每天取 L1 归因中时长最多者，用该归因的固定语义色着色
const METRICS = [
  { value: 'dominant_attr', label: '主导归因', unit: '小时' },
  { value: 'record_count', label: '记录数', unit: '次' },
  { value: 'hours', label: '小时', unit: '小时' },
  { value: 'toward', label: '成长小时', unit: '小时' },
  { value: 'deepwork', label: '深度工作小时', unit: '小时' },
  { value: 'work', label: '牛马工作', unit: '小时' },
]
const metric = ref('dominant_attr')

const currentMetric = computed(() => METRICS.find((m) => m.value === metric.value) ?? METRICS[0])
const mode = computed<'value' | 'attribution'>(() =>
  metric.value === 'dominant_attr' ? 'attribution' : 'value'
)
const unitLabel = computed(() => currentMetric.value.unit)

// ─── 每日明细弹窗 ───
const detailVisible = ref(false)
const detailDate = ref('')
const detailItems = ref<any[]>([])
const detailLoading = ref(false)
const detailSummary = ref('')
const detailColumns = [
  { prop: 'start_time', label: '开始', width: 130, formatter: (v: string) => v ? v.slice(0, 16) : '' },
  { prop: 'end_time', label: '结束', width: 70, formatter: (v: string) => v ? v.slice(11, 16) : '' },
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

// 缓存按 metric 分键：不同口径的数据结构不同（归因模式多 attr/breakdown），混用会串味
const CACHE_KEY = 'contrib_cache_TemporalContribView'
const cacheKey = () => `${CACHE_KEY}_${metric.value}`

async function load(force = false) {
  loading.value = true
  try {
    if (!force) {
      const cached = localStorage.getItem(cacheKey())
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
    localStorage.setItem(cacheKey(), JSON.stringify({ ts: Date.now(), body: res.data }))
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
