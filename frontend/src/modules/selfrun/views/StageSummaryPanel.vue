<template>
  <div class="summary-panel" v-loading="loading">
    <template v-if="summary">
      <!-- ── ⓪ 统计范围：这一段区间是所有数字的边界 ──────────────
           ⚠️ 在这里重复一次区间**不是冗余**：页头那行是全局小字，
              而这一页的每个数字都要拿它来读（「计入 2 周」只有知道
              阶段 11-01 起、且起于周中，才解释得通）。
              区间文本本身仍只由后端 `range_label` 给，前端不拼日期。 -->
      <div class="sp-range">
        <span class="sp-range-label">本阶段区间</span>
        <b>{{ stage?.range_label || '—' }}</b>
        <span class="sp-hint">下面的周 / 月统计全部落在这一段里</span>
      </div>

      <!-- ── ① 概况 ─────────────────────────────────────────── -->
      <div class="sp-cards">
        <div class="sp-card">
          <div class="sp-num">{{ summary.counted_weeks }}</div>
          <div class="sp-label">
            计入的周
            <el-tooltip
              v-if="summary.partial_weeks"
              :content="`另有 ${summary.partial_weeks} 个残缺周（阶段起于周中）—— 参与展示但不进达标率`"
              placement="top"
            >
              <span class="sp-warn">+{{ summary.partial_weeks }} 残缺</span>
            </el-tooltip>
          </div>
        </div>
        <div class="sp-card">
          <div class="sp-num">{{ summary.total_months }}</div>
          <div class="sp-label">个月</div>
        </div>
        <div class="sp-card">
          <div class="sp-num" :style="{ color: onTrackColor }">{{ summary.weekly_breakdown.on_track }}</div>
          <div class="sp-label">合格周</div>
        </div>
        <div class="sp-card">
          <div class="sp-num">{{ summary.fingerprints.length }}</div>
          <div class="sp-label">
            把尺子
            <el-tooltip content="中途改过目标/底线/口径，就是换了一把尺子 —— 换过之后前后不可直接比" placement="top">
              <span class="sp-warn">?</span>
            </el-tooltip>
          </div>
        </div>
      </div>

      <!-- ── ② 逐条 KPI ─────────────────────────────────────── -->
      <el-card shadow="never">
        <template #header><span class="sp-title">逐条 KPI</span></template>
        <el-table :data="summary.metrics" size="small" empty-text="这个阶段没有 KPI">
          <el-table-column prop="name" label="KPI" min-width="120" />
          <el-table-column label="周期" width="60">
            <template #default="{ row }">{{ row.period_type === 'weekly' ? '周' : '月' }}</template>
          </el-table-column>
          <el-table-column label="目标 / 底线" width="170">
            <template #default="{ row }">
              {{ fmt(row.goal_value, row.unit) }} / {{ fmt(row.floor_value, row.unit) }}
              <!-- 🔴 这里显示的是**阶段默认**的双档。这条如果按期改过，
                   拿这个默认值去读往期就会读错 —— 所以必须点名。 -->
              <el-tooltip
                v-if="row.plan_count"
                :content="`这条按期改过 ${row.plan_count} 期（${row.plan_periods.join('、')}）—— 上面这两个数是阶段默认，那几期用的是各自的目标，别拿默认值去读它们`"
                placement="top"
              >
                <el-tag size="small" effect="plain" type="warning" class="sp-plan-tag">
                  换过 {{ row.plan_count }} 期
                </el-tag>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="平均" width="100">
            <template #default="{ row }">{{ fmt(row.avg, row.unit) }}</template>
          </el-table-column>
          <el-table-column label="达标" width="90">
            <template #default="{ row }">{{ row.hit }} / {{ row.total }}</template>
          </el-table-column>
          <el-table-column label="最好的一期" min-width="180">
            <template #default="{ row }">
              <!-- 🔴 不再套一层括号：`period_label` 自己带「（10-12 ~ 10-18）」，
                   套上去会变成「（2026-W42（10-12 ~ 10-18））」—— 两层括号一眼就是 bug -->
              <span v-if="row.best">{{ fmt(row.best.value, row.unit) }} · {{ row.best.period_label }}</span>
              <span v-else class="sp-hint">没有可比的期</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="sp-hint sp-note">
          平均与达标只统计<b>归档过</b>的周期，且剔掉了「取不到」的期 ——
          「没记」不是「没做」，不该被算进你的成绩单。
        </div>
      </el-card>

      <!-- ── ③ 周度分布 + 月度结论 ──────────────────────────── -->
      <div class="sp-two-col">
        <el-card shadow="never">
          <template #header><span class="sp-title">周度分布</span></template>
          <div class="sp-dist">
            <!-- 🔴 档位从标签表**派生**，不手写数组：
                 手写版在加档（v3.62.45 的「我超棒」）时静默漏一根柱，
                 而上面的总数还对得上 —— 最难发现的那种。 -->
            <div v-for="k in breakdownKeys" :key="k" class="sp-dist-row">
              <span class="sp-dist-dot" :style="{ background: statusColor(k) }" />
              <span class="sp-dist-name">{{ PERIOD_STATUS_LABEL[k] }}</span>
              <span class="sp-dist-count">{{ (summary.weekly_breakdown as any)[k] }} 周</span>
            </div>
          </div>
        </el-card>
        <el-card shadow="never">
          <template #header><span class="sp-title">月度结论</span></template>
          <div v-if="!summary.monthly_statuses.length" class="sp-hint">还没有归档过月度周期。</div>
          <div v-for="m in summary.monthly_statuses" :key="m.period_key" class="sp-dist-row">
            <span class="sp-dist-dot" :style="{ background: statusColor(m.status) }" />
            <span class="sp-dist-name">{{ m.period_key }}</span>
            <span class="sp-dist-count">
              {{ periodStatusLabel(m.status, 'monthly') }}
              <template v-if="m.yes_count !== null"> · 答是 {{ m.yes_count }}/{{ MONTHLY_QUESTION_COUNT }}</template>
              <template v-else> · 还没答三问</template>
            </span>
          </div>
        </el-card>
      </div>

      <!-- ── ④ 尺子时间轴（系统口径 · 默认收起）────────────────
           ⚠️ 2026-11-03 用户提出：这块是「给系统对账用的」，日常没有阅读价值 ——
              平时收起来，要排查口径时才打开。展开后的内容一字未删。 -->
      <el-card v-if="summary.fingerprints.length" shadow="never" class="sp-fold">
        <el-collapse>
          <el-collapse-item name="fingerprints">
            <template #title>
              <div class="sp-fold-head">
                <span class="sp-title">尺子时间轴</span>
                <span class="sp-hint">
                  共 {{ summary.fingerprints.length }} 把 · 系统口径：指纹变了 ⇒ 那之后不能和之前直接比
                </span>
              </div>
            </template>
            <div v-for="(g, i) in summary.fingerprints" :key="i" class="sp-fp">
              <el-tag size="small" :type="i === 0 ? 'success' : 'warning'" effect="plain">
                第 {{ i + 1 }} 把 · {{ g.fingerprint }}
              </el-tag>
              <span class="sp-fp-periods">{{ g.periods.join('、') }}</span>
            </div>
            <div class="sp-hint sp-note">
              P1 才会把这一段画成真正的对照图（断点、趋势、两把尺子的换算）。
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <!-- ── ⑤ 你写的话（T4 唯一落库的分析）─────────────────── -->
      <el-card shadow="never">
        <template #header>
          <div class="sp-card-head">
            <span class="sp-title">这一阶段，你写下的话</span>
            <span v-if="summaryAt" class="sp-hint">写于 {{ summaryAt.slice(0, 16) }}</span>
          </div>
        </template>
        <el-input
          v-model="text" type="textarea" :rows="6"
          placeholder="数字在上面，这里只写数字说不出来的那一部分。"
        />
        <div class="sp-actions">
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          <el-button
            v-if="stage && stage.status !== 'closed'"
            type="warning" plain :loading="closing" @click="doCloseStage"
          >
            收尾这个阶段
          </el-button>
          <span class="sp-hint">
            保存时会<b>同时冻结「你此刻看到的这些数字」</b> —— 将来口径变了重算会不同，
            而你是看着这一版写下的。
          </span>
        </div>
        <el-alert
          v-if="snapshotDiffers" type="warning" :closable="false" show-icon class="sp-note"
          title="现在的数字与你写这段话时看到的已经不一样了"
          description="很可能是后来改过口径或补录过数据。上面写下的文字对应的是当时那一版数字（已冻结保存）。"
        />
        <el-collapse v-if="snapshot" class="sp-snapshot">
          <el-collapse-item :title="`你写那段话时看到的数字（${summaryAt?.slice(0, 16) ?? ''}）`">
            <div class="sp-snap-body">
              计入周 {{ snapshot.counted_weeks }} · 残缺周 {{ snapshot.partial_weeks }} · 月 {{ snapshot.total_months }}
              <div v-for="m in snapshot.metrics" :key="m.metric_id" class="sp-snap-row">
                {{ m.name }}：平均 {{ fmt(m.avg, m.unit) }} · 达标 {{ m.hit }}/{{ m.total }}
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>
    </template>
    <el-empty v-else description="还没有进行中的阶段" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '../api/selfrunApi'
import { useSelfRunStore } from '../stores/selfrunStore'
import {
  FALLBACK_COLOR, MONTHLY_QUESTION_COUNT, PERIOD_STATUS_LABEL, fmt, periodStatusLabel,
} from '../types/selfrunTypes'
import type { StageSummary } from '../types/selfrunTypes'

const emit = defineEmits<{ (e: 'changed'): void }>()

const store = useSelfRunStore()
const loading = ref(false)
const saving = ref(false)
const closing = ref(false)
const summary = ref<StageSummary | null>(null)
const snapshot = ref<StageSummary | null>(null)
const summaryAt = ref<string | null>(null)
const text = ref('')

const stage = computed(() => store.stage)

function statusColor(s: string) {
  return store.colors.period[s] ?? FALLBACK_COLOR
}
const onTrackColor = computed(() => statusColor('on_track'))

/**
 * 周度分布要显示哪几档 —— **从标签表派生**（顺序即枚举顺序）。
 *
 * 排除 `no_record`：它和 `fallow` 同属「没判好坏」，混进分布会把
 * 「我超棒 3 周」和其它档的对比冲淡；要看得见的是**好坏四档**（含休耕，
 * 因为休耕不是失败）。
 */
const breakdownKeys = computed(() => {
  const rows = (summary.value?.weekly_breakdown ?? {}) as Record<string, number>
  return Object.keys(PERIOD_STATUS_LABEL).filter(
    (k) => k !== 'no_record' && rows[k] !== undefined,
  )
})

/**
 * 🔴 「现在的数」与「当时冻结的数」不一致 ⇒ **显式说出来**。
 *    不报的话，你留下的文字会与旁边的数字对不上，而你不知道是哪个变了。
 */
const snapshotDiffers = computed(() => {
  const a = summary.value
  const b = snapshot.value
  if (!a || !b) return false
  if (a.counted_weeks !== b.counted_weeks || a.total_months !== b.total_months) return true
  const key = (s: StageSummary) => s.metrics.map(m => `${m.metric_id}:${m.hit}/${m.total}:${m.avg ?? '-'}`).join('|')
  return key(a) !== key(b)
})

async function load() {
  const s = store.stage
  if (!s) {
    summary.value = null
    return
  }
  loading.value = true
  try {
    const res = await api.getStageSummary(s.id)
    summary.value = res.data.summary
    snapshot.value = res.data.summary_snapshot
    summaryAt.value = res.data.summary_at
    text.value = res.data.stage.summary ?? ''
  } catch {
    summary.value = null
    ElMessage.error('加载阶段总结失败')
  } finally {
    loading.value = false
  }
}

watch(() => store.stage?.id, load)

async function save() {
  const s = store.stage
  if (!s) return
  if (!text.value.trim()) {
    ElMessage.warning('先写点什么 —— 哪怕一句。')
    return
  }
  saving.value = true
  try {
    const res = await api.saveStageSummary(s.id, text.value)
    snapshot.value = res.data.summary_snapshot
    summaryAt.value = res.data.stage.summary_at
    await store.loadStage(true)
    await load()
    ElMessage.success('已保存（当时的数字已一并冻结）')
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function doCloseStage() {
  const s = store.stage
  if (!s) return
  if (!text.value.trim()) {
    ElMessage.warning('收尾前请先写下阶段总结（哪怕一句话）。')
    return
  }
  try {
    await ElMessageBox.confirm(
      '收尾会把阶段置为「已收尾」并写死终点：\n'
      + '· 之后不能再归档周期、不能重开历史；\n'
      + '· 结论与快照全部保留，随时可回看；\n'
      + '· 想继续就用「复制这个配置开新阶段」（历史不会被复制）。',
      `收尾「${s.name}」？`,
      { confirmButtonText: '收尾', cancelButtonText: '再等等', type: 'warning' },
    )
  } catch {
    return
  }
  closing.value = true
  try {
    await api.closeStage(s.id, { text: text.value })
    await store.bootstrap()
    await load()
    ElMessage.success('已收尾 —— 随时可以去「复盘」回看')
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '收尾失败')
  } finally {
    closing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.summary-panel { display: flex; flex-direction: column; gap: 12px; }
.sp-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.sp-range {
  display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;
  font-size: 13px; color: var(--el-text-color-regular); margin-bottom: 10px;
}
.sp-range-label { color: var(--el-text-color-secondary); }
.sp-card {
  border: 1px solid var(--el-border-color-lighter); border-radius: 10px;
  padding: 14px; text-align: center;
}
.sp-num { font-size: 26px; font-weight: 700; line-height: 1.1; }
.sp-label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
.sp-warn { color: var(--el-color-warning); cursor: help; }
.sp-title { font-weight: 600; }
.sp-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.sp-hint { font-size: 12px; color: var(--el-text-color-secondary); }
.sp-note { margin-top: 8px; }
.sp-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.sp-dist-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; font-size: 13px; }
.sp-dist-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.sp-dist-name { min-width: 110px; }
.sp-dist-count { margin-left: auto; color: var(--el-text-color-regular); font-variant-numeric: tabular-nums; }
.sp-plan-tag { margin-left: 6px; }
/* 尺子时间轴是折叠卡：去掉 collapse 自带的外框与上下分隔线，只留卡片那一圈 ——
   否则一张卡里套两根线，看起来像两个区块 */
.sp-fold-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sp-fold :deep(.el-collapse) { border-top: none; border-bottom: none; }
.sp-fold :deep(.el-collapse-item__header) {
  border-bottom: none; height: auto; line-height: 1.6; padding: 2px 0;
}
.sp-fold :deep(.el-collapse-item__wrap) { border-bottom: none; }
.sp-fp { display: flex; align-items: center; gap: 10px; padding: 4px 0; }
.sp-fp-periods { font-size: 12px; color: var(--el-text-color-secondary); }
.sp-actions { display: flex; align-items: center; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
.sp-snapshot { margin-top: 10px; }
.sp-snap-body { font-size: 12px; color: var(--el-text-color-regular); }
.sp-snap-row { padding: 2px 0; }
</style>
