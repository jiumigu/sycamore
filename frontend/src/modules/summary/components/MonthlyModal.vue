<template>
  <el-dialog
    :model-value="visible"
    :title="`${year}年${month}月 覆盖详情`"
    width="560px"
    @update:model-value="$emit('update:visible', $event)"
    @open="loadData"
  >
    <div v-loading="loading" class="monthly-modal-body">
      <!-- 本月最短板：不再有「总分 / 月目标」 -->
      <div class="weak-card">
        <div class="weak-title">本月最短板</div>
        <template v-if="detail?.weakest">
          <div class="weak-value">
            <span class="weak-name">{{ detail.weakest.label }}</span>
            <span class="weak-pct">{{ detail.weakest.coverage_pct }}%</span>
          </div>
          <div class="weak-sub">
            {{ detail.weakest.covered }}/{{ detail.weakest.periods }}
            {{ detail.weakest.period_word }}有记录
          </div>
        </template>
        <div v-else class="weak-sub">
          这个月还没有可比较的记录
        </div>
      </div>

      <div class="hint">
        覆盖率低的维度排在上面 —— 越低说明这个月漏得越多。
      </div>

      <!-- 各模块：覆盖率 + 强度 -->
      <div class="module-list">
        <div
          v-for="item in sortedModules"
          :key="item.module"
          class="module-row"
          @click="$emit('view-module', item.module, year, month)"
        >
          <span class="m-dot" :style="{ background: item.color }"></span>
          <span class="m-label">{{ item.label }}</span>

          <span class="m-cov">
            <span class="m-bar">
              <span
                v-if="item.coverage.pct !== null"
                class="m-bar-fill"
                :style="{ width: Math.min(item.coverage.pct, 100) + '%', background: item.color }"
              ></span>
            </span>
            <span class="m-pct">{{ item.coverage.pct === null ? '—' : item.coverage.pct + '%' }}</span>
          </span>

          <span class="m-frac">
            {{ item.coverage.covered }}/{{ item.coverage.periods }} {{ item.coverage.period_word }}
          </span>

          <span class="m-int" :title="item.coverage.intensity_label">
            <template v-if="item.coverage.intensity !== null">
              {{ fmtIntensity(item) }}
              <span class="m-unit">{{ item.coverage.intensity_unit }}</span>
            </template>
            <span v-else class="m-muted">—</span>
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
import { formatSignedAmount } from '@/shared/utils/format'
import type { ModulePoint } from '../types/summaryTypes'

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
// 显式引用避免 TS 认为 emit 未使用（模板里用的是 $emit）
void emit

const store = useSummaryStore()
const loading = ref(false)
const detail = computed(() => store.monthlyDetail)

/**
 * 按覆盖率**升序**：把漏得最多的放最上面。
 * 原来按点数降序 —— 那是「谁贡献大」，分数拆掉之后这个问题不再存在。
 */
const sortedModules = computed<ModulePoint[]>(() => {
  if (!detail.value?.modules) return []
  return [...detail.value.modules].sort((a, b) => {
    const x = a.coverage.pct
    const y = b.coverage.pct
    // 算不出来（null）排最后，不要被当成 0% 顶到最前面
    if (x === null && y === null) return 0
    if (x === null) return 1
    if (y === null) return -1
    return x - y
  })
})

function fmtIntensity(m: ModulePoint): string {
  const v = m.coverage.intensity
  if (v === null) return '—'
  if (m.module === 'wealth') return formatSignedAmount(v, 2)
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 1 })
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

.weak-card {
  text-align: center;
  padding: 16px;
  background: linear-gradient(135deg, #FFFBEB, #FEF3C7);
  border-radius: 12px;
  margin-bottom: 10px;
}
.weak-title {
  font-size: 12px;
  color: #92400E;
  margin-bottom: 6px;
}
.weak-value {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 10px;
}
.weak-name {
  font-size: 20px;
  font-weight: 700;
  color: #92400E;
}
.weak-pct {
  font-size: 20px;
  font-weight: 700;
  color: #B45309;
  font-variant-numeric: tabular-nums;
}
.weak-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #A16207;
}

.hint {
  margin-bottom: 8px;
  padding: 0 4px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
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
  padding: 9px 8px;
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
  width: 60px;
  flex-shrink: 0;
}

.m-cov {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.m-bar {
  flex: 1;
  min-width: 30px;
  height: 7px;
  border-radius: 4px;
  background: var(--el-fill-color);
  overflow: hidden;
}
.m-bar-fill {
  display: block;
  height: 100%;
  border-radius: 4px;
}
.m-pct {
  width: 42px;
  text-align: right;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}

.m-frac {
  width: 74px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.m-int {
  width: 92px;
  text-align: right;
  font-size: 12px;
  color: var(--el-text-color-regular);
  font-variant-numeric: tabular-nums;
}
.m-unit {
  font-size: 10px;
  color: var(--el-text-color-secondary);
}
.m-muted { color: var(--el-text-color-placeholder); }

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
