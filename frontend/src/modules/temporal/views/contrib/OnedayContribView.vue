<template>
  <div class="contrib-page">
    <div class="page-header">
      <div class="header-left">
        <el-button size="small" @click="$router.push('/temporal/daily')">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <h2 class="page-title">{{ title }}</h2>
        <el-tag size="small" type="info">单日总字数</el-tag>
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
      :title="`${detailDate} 日记`"
      :data="detailItems"
      :columns="detailColumns"
      :loading="detailLoading"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import ContributionGraph from '@/shared/components/ContributionGraph.vue'
import DailyDetailDialog from '@/shared/components/DailyDetailDialog.vue'
import { getOnedayDailyDetail } from '@/modules/temporal/api/temporalApi'
import * as temporalApi from '@/modules/temporal/api/temporalApi'

const title = '日记流贡献图'
const unitLabel = '字'
const posNeg = false
const graphData = ref<Array<{ date: string; value: number }>>([])
const minYear = ref(2020)
const maxYear = ref(new Date().getFullYear())
const loading = ref(false)

// ─── 每日明细弹窗 ───
const detailVisible = ref(false)
const detailDate = ref('')
const detailItems = ref<any[]>([])
const detailLoading = ref(false)
const detailColumns = [
  { prop: 'title', label: '主题', minWidth: 200 },
  { prop: 'otype', label: '类型', width: 100 },
  { prop: 'total', label: '总字数', width: 100, align: 'right' as const },
  { prop: 'flag', label: '标签', minWidth: 100 },
  { prop: 'remark', label: '备注', minWidth: 180 },
]

async function onCellClick(date: string) {
  detailDate.value = date
  detailVisible.value = true
  detailItems.value = []
  detailLoading.value = true
  try {
    const res = await getOnedayDailyDetail({ date })
    const data: any = res.data
    detailItems.value = data.items || []
  } catch {
    ElMessage.error('获取明细失败')
  } finally {
    detailLoading.value = false
  }
}

const CACHE_KEY = 'contrib_cache_OnedayContribView'

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
    const res = await temporalApi.getOnedayContrib()
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
