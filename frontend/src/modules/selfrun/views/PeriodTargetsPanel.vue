<template>
  <el-card shadow="never" class="pt-card">
    <template #header>
      <div class="pt-head">
        <span class="pt-title">按期修订</span>
        <span class="pt-hint">
          每周 / 每月都可以在这里改**下一周、下一月**的目标 —— 改的是「那一期拿什么尺子」，
          不动阶段默认值。
        </span>
        <span class="pt-spacer" />
        <el-radio-group v-model="periodType" size="small">
          <el-radio-button value="weekly">周</el-radio-button>
          <el-radio-button value="monthly">月</el-radio-button>
        </el-radio-group>
        <el-select v-model="selectedKey" size="small" style="width: 250px" :loading="loading">
          <el-option
            v-for="o in store.periodOptions" :key="o.key"
            :label="optionLabel(o)" :value="o.key"
          />
        </el-select>
        <el-button size="small" @click="load">刷新</el-button>
      </div>
    </template>

    <el-alert
      v-if="!store.stage"
      type="info" :closable="false" show-icon
      title="还没有进行中的阶段"
      description="按期修订改的是「某一条已建 KPI 在某一期的目标」—— 先回「制定配置」开一个阶段，这一页才有内容。"
    />

    <template v-else>
      <!-- 这一期的性质：本期 / 未来 / 已过去。三种话必须说得不一样 -->
      <div v-if="payload" class="pt-status">
        <el-tag v-if="payload.is_current" size="small" type="success" effect="plain">这一期正在跑</el-tag>
        <el-tag v-else-if="!payload.is_past" size="small" effect="plain">还没开始的一期</el-tag>
        <el-tag v-else size="small" type="warning" effect="plain">已经过去的一期</el-tag>
        <span class="pt-range">
          {{ payload.period_key }} · {{ payload.period_start }} ~ {{ lastDay(payload.period_end) }}
        </span>
        <span v-if="payload.is_past" class="pt-hint">
          改过去那一期是「补记当时该拿的尺子」，会留痕；**已经归档**的期改不动（后端会拦）。
        </span>
        <span v-else-if="!payload.is_current" class="pt-hint">
          这一期还没到 —— 现在定好，到那一期就按这个算。
        </span>
      </div>

      <el-table
        :data="payload?.rows ?? []" size="small" v-loading="loading"
        empty-text="这个阶段没有对应的 KPI（周/月各一把尺子，切上面那个开关看看）"
      >
        <el-table-column label="KPI" min-width="140">
          <template #default="{ row }">
            <div class="pt-name">{{ row.name }}</div>
            <div class="pt-sub">
              {{ DIRECTION_LABEL[row.direction] ?? row.direction }}
              <span v-if="row.plan_count" class="pt-sub-warn">· 共改过 {{ row.plan_count }} 期</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="阶段默认" width="130">
          <template #default="{ row }">
            <span class="pt-base">{{ fmt(row.base_goal, row.unit) }} / {{ fmt(row.base_floor, row.unit) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="这一期生效" width="160">
          <template #default="{ row }">
            <span class="pt-live">{{ fmt(row.goal_value, row.unit) }} / {{ fmt(row.floor_value, row.unit) }}</span>
            <el-tag
              v-if="row.target_source !== 'metric'" size="small" effect="plain"
              :type="TARGET_SOURCE_TAG[row.target_source] || 'info'" class="pt-tag"
            >
              {{ row.target_source_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="依据（这一期）" min-width="180">
          <template #default="{ row }">
            <div v-if="row.plan_note" class="pt-note">备注：{{ row.plan_note }}</div>
            <div v-if="row.goal_why" class="pt-sub">目标：{{ row.goal_why }}</div>
            <div v-if="row.floor_why" class="pt-sub">底线：{{ row.floor_why }}</div>
            <span v-if="!row.plan_note && !row.goal_why && !row.floor_why" class="pt-sub">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openPlan(row)">改这一期</el-button>
            <el-button
              v-if="row.plan_id" size="small" text type="danger"
              @click="cancelPlan(row)"
            >
              取消设定
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pt-foot">
        「阶段默认」是这条 KPI 建阶段时定的值；「这一期生效」是**这一期真的会拿来判的**值。
        归档之后，当时的「这一期生效」会被**冻进快照** —— 之后再改（如果有）不会回头改写已归档的结论。
      </div>
    </template>

    <TargetPlanDialog
      v-model="dialogVisible"
      :row="editingRow"
      :period-key="selectedKey"
      :period-label="editingLabel"
      @saved="onSaved"
    />
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '../api/selfrunApi'
import TargetPlanDialog from '../components/TargetPlanDialog.vue'
import { useSelfRunStore } from '../stores/selfrunStore'
import {
  DIRECTION_LABEL, TARGET_SOURCE_TAG, fmt,
} from '../types/selfrunTypes'
import type { PeriodOption, PeriodType, TargetRow, TargetsPayload } from '../types/selfrunTypes'

const emit = defineEmits<{ (e: 'changed'): void }>()

const store = useSelfRunStore()

const periodType = ref<PeriodType>('weekly')
const selectedKey = ref('')
const payload = ref<TargetsPayload | null>(null)
const loading = ref(false)
const dialogVisible = ref(false)
const editingRow = ref<TargetRow | null>(null)

/** 半开区间的右端是**不含**的 —— 显示时要减一天，否则你会以为最后一天不算 */
function lastDay(end: string): string {
  const [y, m, d] = end.split('-').map(Number)
  const dt = new Date(y, (m || 1) - 1, (d || 1) - 1)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}`
}

function optionLabel(o: PeriodOption): string {
  return `${o.key} · ${o.label}（${o.start} 起）`
}

const editingLabel = computed(() => {
  const o = store.periodOptions.find(x => x.key === selectedKey.value)
  return o ? `${o.key}（${o.label}）` : selectedKey.value
})

/**
 * 默认停在**下一期**（`offset === 1`）。
 *
 * 🔴 这是有意的：进这一栏的人十有八九是来「定下一周/下个月的线」的。
 *    默认停在本期的话，改完会以为「改的是下周」，实际把正在跑的这一周改了。
 *    （落不到下一期时——比如期列表只剩上一期和本期——才回到本期。）
 */
function pickDefault(options: PeriodOption[]): string {
  const next = options.find(o => o.offset === 1)
  if (next) return next.key
  const cur = options.find(o => o.offset === 0)
  return cur?.key ?? options[0]?.key ?? ''
}

async function loadOptions() {
  const options = await store.loadPeriodOptions(periodType.value, 6)
  if (!options.some(o => o.key === selectedKey.value)) {
    selectedKey.value = pickDefault(options)
  }
}

async function load() {
  if (!store.stage || !selectedKey.value) {
    payload.value = null
    return
  }
  loading.value = true
  try {
    const res = await api.getTargets(periodType.value, selectedKey.value)
    payload.value = res.data.targets
  } catch (e: any) {
    payload.value = null
    ElMessage.error(e?.response?.data?.detail ?? '取不到这一期的目标')
  } finally {
    loading.value = false
  }
}

/** 周期类型换了 ⇒ 期列表整份换掉，选中项也要重新落位 */
watch(periodType, async () => {
  selectedKey.value = ''
  payload.value = null
  try {
    await loadOptions()
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '加载周期失败')
  }
})

watch(selectedKey, () => { if (selectedKey.value) load() })

function openPlan(row: TargetRow) {
  editingRow.value = row
  dialogVisible.value = true
}

async function cancelPlan(row: TargetRow) {
  if (!row.plan_id) return
  try {
    await ElMessageBox.confirm(
      `「${row.name}」在 ${selectedKey.value} 的设定会被**删掉**（回到上一层口径：更早的「从这一期起」或阶段默认）。`
      + `\n\n⚠️ 这一条是**配置**不是流水，所以是真的删除；留痕由变更记录承担。`,
      '取消这一期的设定？',
      { confirmButtonText: '取消设定', cancelButtonText: '算了', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await store.cancelPlan(row.metric_id, row.plan_id)
    ElMessage.success('已取消这一期的设定')
    await load()
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '取消失败')
  }
}

async function onSaved() {
  await load()
  emit('changed')
}

// 🔴 **不能靠一次性的 `onMounted`**：阶段是异步拉回来的（`store.bootstrap()`），
//    而直接进 `/selfrun/setup/targets`（或在这页硬刷新）时，组件比阶段**先挂载** ——
//    `onMounted` 里那一刻 `store.stage` 还是 `null`，写成「没阶段就 return」就是
//    空转一次之后**再没人叫它**，页面永远是「请选择 + 没有对应的 KPI」（看着像没做功能）。
//    ⇒ 改成盯住「阶段是谁」，阶段一到就自己加载。
watch(
  () => store.stage?.id,
  async (id, old) => {
    if (!id) {
      selectedKey.value = ''
      payload.value = null
      return
    }
    if (id === old) return
    try {
      await loadOptions()
      await load()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail ?? '加载周期失败')
    }
  },
  { immediate: true },
)

defineExpose({ reload: load })
</script>

<style scoped>
.pt-card { border-radius: 10px; }
.pt-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pt-title { font-weight: 600; }
.pt-spacer { flex: 1; }
.pt-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }

.pt-status {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin-bottom: 10px;
}
.pt-range { font-size: 12px; color: var(--el-text-color-regular); font-variant-numeric: tabular-nums; }

.pt-name { font-weight: 600; }
.pt-sub { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; }
.pt-sub-warn { color: var(--el-color-warning); }
.pt-note { font-size: 12px; color: var(--el-text-color-regular); line-height: 1.5; }
.pt-base { font-size: 12px; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.pt-live { font-weight: 600; font-variant-numeric: tabular-nums; }
.pt-tag { margin-left: 6px; }

.pt-foot {
  margin-top: 10px; padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.7;
}
</style>
