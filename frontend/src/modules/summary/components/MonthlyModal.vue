<template>
  <el-dialog
    :model-value="visible"
    :title="`${year}年${month}月 进度详情`"
    width="520px"
    @update:model-value="$emit('update:visible', $event)"
    @open="loadData"
  >
    <div v-loading="loading" class="monthly-modal-body">
      <!-- 总进度 -->
      <div class="total-card">
        <div class="total-title">本月总进度</div>
        <div class="total-value">
          <span class="num">{{ detail?.total_points ?? '--' }}</span>
          <span class="sep">/</span>
          <span class="target">{{ detail?.month_target ?? '--' }}</span>
          <span class="unit">点</span>
        </div>
        <div class="total-bar">
          <div
            class="total-fill"
            :style="{ width: Math.min((detail?.target_percent ?? 0), 100) + '%' }"
          ></div>
        </div>
        <div class="total-percent">{{ (detail?.target_percent ?? 0).toFixed(1) }}%</div>
      </div>

      <!-- 各模块 -->
      <div class="module-list">
        <div
          v-for="item in sortedModules"
          :key="item.module"
          class="module-row"
          @click="$emit('view-module', item.module, year, month)"
        >
          <span class="m-dot" :style="{ background: item.color }"></span>
          <span class="m-label">{{ item.label }}</span>
          <span class="m-points">{{ item.points }} 点</span>
          <span class="m-raw">
            {{ formatRaw(item.raw_value, item.unit) }}
          </span>
          <el-icon class="m-arrow"><ArrowRight /></el-icon>
        </div>
        <div v-if="!detail?.modules?.length" class="empty">暂无数据</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import { useSummaryStore } from '../stores/summaryStore'

const props = withDefaults(defineProps<{
  visible: boolean
  year?: number
  month?: number
}>(), {
  year: new Date().getFullYear(),
  month: new Date().getMonth() + 1,
})

const emit = defineEmits<{
  'update:visible': [v: boolean]
  'view-module': [module: string, year: number, month: number]
}>()

const store = useSummaryStore()
const loading = ref(false)
const detail = computed(() => store.monthlyDetail)

const sortedModules = computed(() => {
  if (!detail.value?.modules) return []
  return [...detail.value.modules].sort((a, b) => b.points - a.points)
})

function formatRaw(val: number, unit: string) {
  if (!val && val !== 0) return ''
  if (val >= 10000) return `${(val / 10000).toFixed(2)}万${unit}`
  return `${val} ${unit}`
}

async function loadData() {
  loading.value = true
  try {
    await store.fetchMonthlyDetail(props.year, props.month)
  } finally {
    loading.value = false
  }
}

watch(() => [props.year, props.month], () => {
  if (props.visible) loadData()
})
</script>

<style scoped>
.monthly-modal-body {
  min-height: 200px;
}

.total-card {
  text-align: center;
  padding: 20px 16px;
  background: linear-gradient(135deg, #ECFDF5, #D1FAE5);
  border-radius: 12px;
  margin-bottom: 20px;
}

.total-title {
  font-size: 13px;
  color: #6B7280;
  margin-bottom: 8px;
}

.total-value {
  font-size: 28px;
  font-weight: 700;
  color: #059669;
}
.total-value .sep {
  color: #9CA3AF;
  margin: 0 4px;
  font-weight: 400;
}
.total-value .target {
  font-weight: 400;
  color: #6B7280;
}
.total-value .unit {
  font-size: 14px;
  color: #6B7280;
  font-weight: 400;
  margin-left: 4px;
}

.total-bar {
  height: 6px;
  background: #E5E7EB;
  border-radius: 3px;
  margin: 12px auto 6px;
  max-width: 240px;
  overflow: hidden;
}

.total-fill {
  height: 100%;
  background: linear-gradient(90deg, #34D399, #059669);
  border-radius: 3px;
  transition: width 0.6s ease;
}

.total-percent {
  font-size: 12px;
  color: #6B7280;
}

.module-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.module-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.module-row:hover {
  background: var(--el-fill-color-light);
}

.m-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.m-label {
  font-size: 13px;
  color: var(--el-text-color-primary);
  width: 64px;
  flex-shrink: 0;
}

.m-points {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  width: 60px;
}

.m-raw {
  flex: 1;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: right;
}

.m-arrow {
  font-size: 12px;
  color: #D1D5DB;
}

.empty {
  text-align: center;
  color: #9CA3AF;
  padding: 24px;
  font-size: 13px;
}
</style>
