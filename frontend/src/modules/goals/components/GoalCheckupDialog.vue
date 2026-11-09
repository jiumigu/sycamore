<template>
  <el-dialog
    :model-value="visible"
    width="880"
    append-to-body
    class="checkup-dialog"
    @update:model-value="$emit('update:visible', $event)"
    @open="reload"
  >
    <template #header>
      <div class="ck-head">
        <div class="ck-title">过程检查 · {{ todayLabel }}</div>
        <div class="ck-question">
          {{ headline }}
        </div>
      </div>
    </template>

    <p class="ck-why">
      这不是打分，是点名 —— 只回答「哪些还动、哪些不动了」。
      <b>检查不会改动任何目标</b>：要不要处理，你自己决定。
    </p>

    <div v-loading="loading" class="ck-body">
      <div v-if="rows.length" class="ck-list">
        <div
          v-for="row in rows"
          :key="row.id"
          class="ck-row"
          :class="`is-${row.verdict}`"
        >
          <div class="ck-row-main">
            <span class="ck-verdict">{{ row.verdict_label }}</span>
            <span class="ck-name">{{ row.title }}</span>
          </div>
          <div class="ck-row-meta">
            <span>进度 {{ row.progress }}%</span>
            <!-- 时间进度算不出来时说原因，不填 0 假装算过 -->
            <span v-if="row.time_progress !== null">
              时间 {{ row.time_progress }}%（{{ gapText(row.progress_gap) }}）
            </span>
            <span v-else class="ck-muted">{{ reasonText(row.time_progress_reason) }}</span>
            <!--
              🔴 长期目标不显示「剩 N 天」：跨度 50 年时会渲染成「剩 19797 天」，
                 那个数既没人读得懂、也不影响任何判断（§「恒等的列不占位置」的反面）。
            -->
            <span v-if="row.time_progress_reason === 'long_horizon'" class="ck-muted">长期</span>
            <span v-else-if="row.deadline">
              剩 {{ row.days_left }} 天
            </span>
            <span v-if="row.days_since_activity !== null" class="ck-muted">
              {{ row.days_since_activity }} 天没动
            </span>
            <span v-else class="ck-muted">从没记录过进展</span>
            <span class="ck-muted">里程碑 {{ row.milestones_done }}/{{ row.milestones_total }}</span>
          </div>
        </div>
      </div>
      <el-empty
        v-else-if="!loading"
        description="没有在途目标"
        :image-size="80"
      />
    </div>

    <template #footer>
      <div class="ck-foot">
        <span class="ck-thresholds">
          判据：停滞 ≥ {{ stallDays }} 天 · 落后 ≥ {{ behindGap }} 点 ·
          跨度 &gt; {{ horizonYears }} 年不算落后
        </span>
        <el-button @click="$emit('update:visible', false)">知道了</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { getGoalCheckup } from '../api/goalApi'
import type { GoalCheckupRow, GoalCheckupResponse } from '../api/goalApi'

const props = defineProps<{ visible: boolean }>()
defineEmits<{ 'update:visible': [val: boolean] }>()

const loading = ref(false)
const data = ref<GoalCheckupResponse | null>(null)

/** 阈值由后端下发 —— 前端一个都不写死（§同一事实一把尺子） */
const stallDays = computed(() => data.value?.stall_days ?? 0)
const behindGap = computed(() => data.value?.behind_gap ?? 0)
const horizonYears = computed(() => data.value?.horizon_years ?? 0)
const rows = computed<GoalCheckupRow[]>(() => data.value?.rows ?? [])

const todayLabel = computed(() => data.value?.as_of ?? '')

const headline = computed(() => {
  const s = data.value?.summary
  if (!s) return '正在检查…'
  if (!s.checked) return '没有在途目标，无检查可做'
  if (!s.problem) return `${s.checked} 条在途目标都在推进`
  const parts: string[] = []
  if (s.overdue) parts.push(`${s.overdue} 条逾期`)
  if (s.stalled) parts.push(`${s.stalled} 条停滞`)
  if (s.behind) parts.push(`${s.behind} 条落后`)
  return `${s.checked} 条在途，${parts.join('、')}`
})

const REASON_TEXT: Record<string, string> = {
  no_deadline: '没有截止日',
  no_start: '没有开始日',
  invalid_span: '起止日期无效',
  long_horizon: '长期目标，不算时间进度',
  ok: '',
}

function reasonText(reason: string): string {
  return REASON_TEXT[reason] ?? ''
}

/**
 * 时间进度与完成进度的差 —— 只负责说人话，**不参与判定**
 *
 * 🔴 判定在 `verdict` 里（后端给的），这里算出来的正负号只影响措辞。
 *    别在这里加 `if (gap > 15)` 之类，那是第二把尺子。
 */
function gapText(gap: number | null): string {
  if (gap === null) return ''
  if (gap > 0) return `落后 ${gap} 点`
  if (gap < 0) return `领先 ${Math.abs(gap)} 点`
  return '持平'
}

async function reload() {
  loading.value = true
  try {
    const resp = await getGoalCheckup()
    data.value = resp.data as GoalCheckupResponse
  } catch (e) {
    console.error('获取过程检查失败:', e)
    data.value = null
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.ck-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ck-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.ck-question {
  font-size: 13px;
  color: var(--el-color-warning-dark-2);
}
.ck-why {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}
.ck-body {
  min-height: 120px;
}
.ck-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ck-row {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-left-width: 3px;
  border-radius: 6px;
}
.ck-row.is-overdue {
  border-left-color: var(--el-color-danger);
}
.ck-row.is-stalled {
  border-left-color: var(--el-color-warning);
}
.ck-row.is-behind {
  border-left-color: var(--el-color-warning-light-3);
}
.ck-row.is-paused {
  border-left-color: var(--el-border-color);
}
.ck-row.is-on_track,
.ck-row.is-ahead {
  border-left-color: var(--el-color-success);
}
.ck-row-main {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ck-verdict {
  flex-shrink: 0;
  padding: 1px 6px;
  font-size: 12px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
}
.ck-row.is-overdue .ck-verdict {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}
.ck-row.is-stalled .ck-verdict {
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning-dark-2);
}
.ck-row.is-behind .ck-verdict {
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning-dark-2);
}
.ck-name {
  font-size: 14px;
  color: var(--el-text-color-primary);
}
.ck-row-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.ck-muted {
  color: var(--el-text-color-secondary);
}
.ck-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ck-thresholds {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  text-align: left;
}
</style>
