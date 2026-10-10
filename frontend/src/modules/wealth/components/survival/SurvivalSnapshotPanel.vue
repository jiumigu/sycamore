<!--
  生存时长快照（P3-A 二期，v3.59.3 改名）

  ⚠️ 这块原本标题叫「盘点历史」，其实是**名不副实**的：它是系统自己
     算出来的结论，点一下就落一份，不需要人动手。v3.59.3 真加了实盘盘点
     （人一件件数出来的）之后，两个都叫「盘点」会让「我到底盘没盘过」
     永远说不清 —— 所以这里正名为「生存时长快照」，动作叫「记一次快照」。
     名字改了，行为没变。

  这一块回答的是**第二个问题**：比上次是变长了还是变短了。
  一期只回答「现在能撑多久」—— 没有方向，那个数字每看一次都像第一次看。

  三条必须守住的展示判据：

  ① **空值不补 0**。折线上某期算不出来就**断开**，不连线、不落点。
     补 0 会画出一条「那天物资归零」的假线 —— 比没有线更糟。
  ② **不可比就说不可比**。两次之间改过类别或消耗模式的话，天数的差里
     混着「换了算法」这一项，必须显示后端给的 reason，而不是照常显示差值。
  ③ **天数不掩码**。天数是推导值、不是隐私项（同 `progress_percentage` 与比率）。
     快照的**备注**是自由文本，才走 `maskFreeText`。
     别顺手给「还能撑 47 天」加星号 —— 这个页面掩了就没有意义了。

  ⚠️ 颜色刻意不套「涨红跌绿」：那套是**价格**语义。天数变长是好事，
     颜色跟语义走、不跟数值方向走（见 survivalFormat.deltaType）。
-->
<template>
  <div class="survival-snapshot">
    <div class="survival-snapshot__head">
      <div class="survival-snapshot__title-wrap">
        <span class="survival-snapshot__title">生存时长快照</span>
        <span class="survival-snapshot__subtitle">
          系统算出来的结论；每记一次留一个点，比较的是「当时的结论」，
          事后改库存不会回改历史
        </span>
      </div>
      <div class="survival-snapshot__actions">
        <el-input
          v-model="note"
          size="small"
          placeholder="备注（选填）"
          maxlength="200"
          class="survival-snapshot__note"
        />
        <el-button
          size="small"
          type="primary"
          :loading="store.saving"
          @click="takeSnapshot(false)"
        >
          记一次快照
        </el-button>
        <MetricTooltip :meta="snapshotDaysMeta" />
      </div>
    </div>

    <!-- 与上次对比：不可比时把原因摊开，而不是只给一个差值 -->
    <div v-if="comparison" class="survival-snapshot__compare">
      <template v-if="comparison.delta_expected !== null || comparison.config_changed">
        <span class="survival-snapshot__compare-label">与上次快照相比</span>
        <el-tag :type="deltaType(comparisonDeltaKind)" size="small" effect="dark">
          {{ formatDelta(comparison.delta_expected, comparisonDeltaKind) }}
        </el-tag>
        <span v-if="comparison.days_since_previous !== null" class="survival-snapshot__compare-meta">
          {{ formatInterval(comparison.days_since_previous) }}
          （{{ comparison.previous_date }} → {{ comparison.latest_date }}）
        </span>
        <span v-if="comparison.delta_item_count" class="survival-snapshot__compare-meta">
          可用物品 {{ comparison.delta_item_count > 0 ? '+' : '' }}{{ comparison.delta_item_count }} 件
        </span>
      </template>
      <el-alert
        v-if="!comparison.comparable"
        type="warning"
        :closable="false"
        show-icon
        class="survival-snapshot__compare-alert"
        :title="comparison.reason || '还不能与上一期比较'"
      />
    </div>

    <!-- 折线：升序序列，空值断线 -->
    <div v-if="hasPoints" class="survival-snapshot__chart">
      <div class="survival-snapshot__chart-head">
        <span>综合能撑多少天</span>
        <span v-if="!store.hasTrendDirection" class="survival-snapshot__chart-hint">
          只有一个点 —— 再记一次才看得出方向
        </span>
      </div>
      <svg class="survival-snapshot__svg" :viewBox="`0 0 ${CHART_W} ${CHART_H}`" preserveAspectRatio="none">
        <!-- 网格：三条淡线给个量级参照，不标阈值（没有阈值） -->
        <line
          v-for="(y, index) in gridLines"
          :key="`grid-${index}`"
          :x1="0" :x2="CHART_W" :y1="y" :y2="y"
          class="survival-snapshot__grid"
        />
        <!-- 断线折线：每段独立 polyline，null 处自然断开 -->
        <polyline
          v-for="(segment, index) in segments"
          :key="`seg-${index}`"
          :points="segment"
          class="survival-snapshot__line"
        />
        <circle
          v-for="(point, index) in dots"
          :key="`dot-${index}`"
          :cx="point.x" :cy="point.y" :r="3"
          :class="['survival-snapshot__dot', `is-${point.kind}`]"
        />
      </svg>
      <div class="survival-snapshot__axis">
        <span v-for="(label, index) in axisLabels" :key="index">{{ label }}</span>
      </div>
    </div>

    <el-table
      v-if="hasPoints"
      :data="store.snapshots"
      size="small"
      class="survival-snapshot__table"
    >
      <el-table-column prop="date" label="记录日" width="110" />
      <el-table-column label="综合三档" width="180">
        <template #default="{ row }">{{ formatScenarioRange(row.days) }}</template>
      </el-table-column>
      <el-table-column label="期望" width="110">
        <template #default="{ row }">{{ formatDays(row.expected) }}</template>
      </el-table-column>
      <el-table-column label="短板" width="90">
        <template #default="{ row }">{{ row.shortest_category || '—' }}</template>
      </el-table-column>
      <el-table-column label="瓶颈" width="110">
        <template #default="{ row }">
          <el-tag :type="bottleneckType(row.bottleneck)" size="small" effect="plain">
            {{ row.bottleneck_label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="可用物品" width="90">
        <template #default="{ row }">{{ row.item_count }} 件</template>
      </el-table-column>
      <el-table-column label="可信" width="70">
        <template #default="{ row }">
          <el-tag v-if="!row.trustworthy" type="warning" size="small" effect="plain">有缺件</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="备注">
        <template #default="{ row }">{{ maskFreeText(row.note) || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button link size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-else
      description="还没有快照 —— 点「记一次快照」把今天的结论留下来，第二次开始就能看出方向"
      :image-size="60"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MetricTooltip from '../common/MetricTooltip.vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import {
  bottleneckType, deltaType, formatDateShort, formatDays, formatDelta,
  formatInterval, formatScenarioRange,
} from '../../utils/survivalFormat'
import type { SurvivalSnapshot } from '../../types/survivalTypes'
import type { RatioMeta } from '../../types/wealthTypes'

const store = useSurvivalStore()
const { maskFreeText } = usePrivacyMask()

const note = ref('')

const hasPoints = computed(() => (store.snapshotTrend?.count ?? 0) > 0)
const comparison = computed(() => store.snapshotComparison)
const snapshotDaysMeta = computed<RatioMeta | null>(
  () => store.metricMetaByKey['snapshot_days'] ?? null,
)

/** 对比条上的色 —— 后端判过 epsilon，这里不重复判 */
const comparisonDeltaKind = computed(() => {
  const points = store.snapshotTrend?.points ?? []
  return points.length ? (points[points.length - 1].delta_kind ?? null) : null
})

// ── 折线几何（纯展示，不做任何口径判断） ──

const CHART_W = 640
const CHART_H = 120
const PAD = 8

/** 只在有点的地方连线段：null 处断开，**不补 0、不跨越空缺连线** */
const segments = computed<string[]>(() => {
  const values = store.snapshotTrend?.series.expected ?? []
  const valid = values.filter((v): v is number => v !== null && v !== undefined)
  if (!valid.length) return []
  const { min, span } = scaleOf(valid)

  const result: string[] = []
  let current: string[] = []
  values.forEach((value, index) => {
    if (value === null || value === undefined) {
      if (current.length > 1) result.push(current.join(' '))
      current = []
      return
    }
    current.push(`${xOf(index, values.length)},${yOf(value, min, span)}`)
  })
  if (current.length > 1) result.push(current.join(' '))
  return result
})

const dots = computed(() => {
  const values = store.snapshotTrend?.series.expected ?? []
  const kinds = store.snapshotTrend?.points.map((p) => p.delta_kind ?? 'flat') ?? []
  const valid = values.filter((v): v is number => v !== null && v !== undefined)
  if (!valid.length) return []
  const { min, span } = scaleOf(valid)
  return values
    .map((value, index) => ({ value, index }))
    .filter((entry): entry is { value: number; index: number } => entry.value !== null && entry.value !== undefined)
    .map((entry) => ({
      x: xOf(entry.index, values.length),
      y: yOf(entry.value, min, span),
      kind: kinds[entry.index] ?? 'flat',
    }))
})

const gridLines = computed(() => [PAD, CHART_H / 2, CHART_H - PAD])

const axisLabels = computed(() =>
  (store.snapshotTrend?.series.dates ?? []).map((d) => formatDateShort(d)),
)

/** 值域：上下各留一点余量，否则最高/最低点会贴在边框上 */
function scaleOf(valid: number[]) {
  const max = Math.max(...valid)
  const min = Math.min(...valid)
  const span = max - min || 1
  return { min, span }
}

function xOf(index: number, total: number): number {
  if (total <= 1) return CHART_W / 2
  return (index / (total - 1)) * (CHART_W - PAD * 2) + PAD
}

function yOf(value: number, min: number, span: number): number {
  const ratio = (value - min) / span
  return CHART_H - PAD - ratio * (CHART_H - PAD * 2)
}

// ── 写 ──

/**
 * 记一次快照。
 *
 * 同一天重复记录时后端拒绝并给一句**能照做**的话（不是静默覆盖），
 * 所以这里把「要不要覆盖」变成一次明确询问 —— 用户知道自己在替换什么。
 */
async function takeSnapshot(overwrite: boolean) {
  try {
    await store.takeSnapshot({ note: note.value.trim(), overwrite })
    note.value = ''
    ElMessage.success(overwrite ? '已覆盖今天的快照' : '已记下这次结论')
  } catch (e: unknown) {
    const message = extractMessage(e, '记快照失败')
    if (!message.includes('已经盘点过')) {
      ElMessage.error(message)
      return
    }
    try {
      await ElMessageBox.confirm(message, '今天已经记录过', {
        type: 'warning',
        confirmButtonText: '覆盖它',
        cancelButtonText: '保留原记录',
      })
    } catch {
      return
    }
    await takeSnapshot(true)
  }
}

async function remove(row: SurvivalSnapshot) {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${row.date} 这一期快照？删掉的是当时算出来的历史结论，`
      + '删完这一段曲线就少一个点，且无法恢复（快照不可编辑，只能重新记一次）。',
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeSnapshot(row.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

function extractMessage(e: unknown, fallback: string): string {
  const data = (e as { response?: { data?: Record<string, unknown> } })?.response?.data
  if (data && typeof data.detail === 'string') return data.detail
  if (data) {
    const first = Object.values(data)[0]
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string') return first
  }
  return fallback
}
</script>

<style scoped>
.survival-snapshot {
  margin-top: 16px;
  padding: 12px 14px 4px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
}
.survival-snapshot__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.survival-snapshot__title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.survival-snapshot__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.survival-snapshot__subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-snapshot__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.survival-snapshot__note {
  width: 160px;
}
.survival-snapshot__compare {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  font-size: 13px;
}
.survival-snapshot__compare-label {
  color: var(--el-text-color-secondary);
}
.survival-snapshot__compare-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-snapshot__compare-alert {
  width: 100%;
}
.survival-snapshot__chart {
  margin-bottom: 10px;
}
.survival-snapshot__chart-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.survival-snapshot__chart-hint {
  color: var(--el-color-info);
}
.survival-snapshot__svg {
  width: 100%;
  height: 120px;
  display: block;
}
.survival-snapshot__grid {
  stroke: var(--el-border-color-extra-light);
  stroke-width: 1;
}
.survival-snapshot__line {
  fill: none;
  stroke: var(--el-color-primary);
  stroke-width: 2;
  stroke-linejoin: round;
}
.survival-snapshot__dot {
  fill: var(--el-color-primary);
}
.survival-snapshot__dot.is-up {
  fill: var(--el-color-success);
}
.survival-snapshot__dot.is-down {
  fill: var(--el-color-danger);
}
.survival-snapshot__axis {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.survival-snapshot__table {
  width: 100%;
}
</style>
