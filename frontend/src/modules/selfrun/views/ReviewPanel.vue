<template>
  <div class="review-panel">
    <div class="rp-head">
      <div class="rp-filters">
        <el-radio-group v-model="filterType" size="small" @change="load">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="weekly">周</el-radio-button>
          <el-radio-button value="monthly">月</el-radio-button>
        </el-radio-group>
        <span class="rp-hint">
          归档后的读数是**冻结快照**，永远不重算 —— 所以这里看到的数就是当时的数。
        </span>
      </div>
      <el-button size="small" @click="load">刷新</el-button>
    </div>

    <el-table
      :data="list" size="small" v-loading="loading" empty-text="还没有归档过任何一期"
      @row-click="openDetail"
    >
      <el-table-column prop="period_key" label="周期" width="120" />
      <el-table-column label="区间" width="190">
        <template #default="{ row }">
          <span class="rp-mono">{{ row.period_start }} ~ {{ row.period_end }}</span>
        </template>
      </el-table-column>
      <el-table-column label="判定" width="120">
        <template #default="{ row }">
          <el-tag size="small" :color="statusColor(row.status)" effect="dark" class="rp-tag">
            {{ PERIOD_STATUS_LABEL[row.status] ?? (row.status || '—') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="达标" width="90">
        <template #default="{ row }">
          <span class="rp-mono">{{ okOf(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="标记" min-width="200">
        <template #default="{ row }">
          <el-tag v-if="row.is_partial" size="small" type="warning" effect="plain">残缺</el-tag>
          <el-tag v-if="row.is_backfilled" size="small" type="warning" effect="plain">事后补算</el-tag>
          <el-tag v-if="row.reopen_count" size="small" type="info" effect="plain">
            重开 {{ row.reopen_count }} 次
          </el-tag>
          <el-tag v-if="row.review_text" size="small" type="success" effect="plain">写过话</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="closed_at" label="归档于" width="150">
        <template #default="{ row }">
          <span class="rp-mono">{{ (row.closed_at ?? '').slice(0, 16) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click.stop="openDetail(row)">复盘</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- ── 单期复盘抽屉 ─────────────────────────────────────── -->
    <el-drawer v-model="drawer" :title="current?.period_key ?? ''" size="640px">
      <template v-if="current">
        <div class="rp-d-tags">
          <el-tag size="small" :color="statusColor(current.status)" effect="dark" class="rp-tag">
            {{ PERIOD_STATUS_LABEL[current.status] ?? (current.status || '—') }}
          </el-tag>
          <el-tag v-if="current.is_partial" size="small" type="warning" effect="plain">残缺周期</el-tag>
          <el-tag v-if="current.is_backfilled" size="small" type="warning" effect="plain">事后补算</el-tag>
          <el-tag size="small" type="info" effect="plain">指纹 {{ current.config_fingerprint || '—' }}</el-tag>
        </div>

        <el-alert
          v-if="current.is_backfilled" type="warning" :closable="false" show-icon class="rp-gap"
          title="这一期是事后补归档的"
          description="补算出来的读数与「当天归档」不等价 —— 数据源在后来的日子里可能被补记或修正过。"
        />

        <!-- 这一期的话（归档后**仍可写** —— 记忆型 ≠ 数据型） -->
        <el-card shadow="never" class="rp-gap">
          <template #header>
            <div class="rp-card-head">
              <span>这一期的话</span>
              <span class="rp-hint">补写会留痕（记下「写于归档后 N 天」）</span>
            </div>
          </template>
          <!-- 高度随内容自适应：回顾时这段话是**要读的正文**，不是录入草稿，
               固定 4 行会把它裁成一条缝（minRows 与 maxRows 是唯一一处高度定义，
               不另写 :rows —— 两个口径同时存在就会互相覆盖） -->
          <el-input
            v-model="reviewText" type="textarea" resize="none"
            :autosize="{ minRows: 4, maxRows: 12 }"
            placeholder="一句话就行 —— 值得记住的不是数字，是你当时怎么想的"
          />
          <div class="rp-d-footer">
            <el-button size="small" type="primary" :loading="saving" @click="saveReview">保存</el-button>
            <el-button
              v-if="isLatest" size="small" type="warning" plain :loading="reopening"
              @click="doReopen"
            >
              重开这一期
            </el-button>
            <span class="rp-hint">
              重开是改历史判定的**唯一出口**，且只允许最近一期、必须写原因。
            </span>
          </div>
          <div v-if="current.review_edits.length" class="rp-edits">
            <div class="rp-hint">补写留痕：</div>
            <div v-for="(e, i) in current.review_edits" :key="i" class="rp-edit">
              归档后第 {{ e.days_after_close }} 天改过 → 原内容是「{{ e.text || '（空）' }}」
            </div>
          </div>
        </el-card>

        <!-- 冻结读数（只读） -->
        <div class="rp-gap">
          <div class="rp-section-title">当时的逐条读数（冻结，不可改）</div>
          <ReadingCard
            v-for="r in current.readings ?? []" :key="r.metric_id"
            :reading="r" :editable="false"
          />
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ReadingCard from '../components/ReadingCard.vue'
import { useSelfRunStore } from '../stores/selfrunStore'
import { FALLBACK_COLOR, PERIOD_STATUS_LABEL } from '../types/selfrunTypes'
import type { PeriodType, SelfRunPeriod } from '../types/selfrunTypes'

const emit = defineEmits<{ (e: 'changed'): void }>()

const store = useSelfRunStore()
const loading = ref(false)
const saving = ref(false)
const reopening = ref(false)
const filterType = ref<PeriodType | ''>('')
const list = ref<SelfRunPeriod[]>([])
const drawer = ref(false)
const current = ref<SelfRunPeriod | null>(null)
const reviewText = ref('')

/** 「重开」只对**最近一期**开放（更早的属于改写历史）—— 后端也这么判。 */
const isLatest = computed(() => {
  const c = current.value
  if (!c) return false
  const pool = list.value.filter(p => p.period_type === c.period_type)
  return pool.length > 0 && pool[0].id === c.id
})

function statusColor(s: string) {
  return store.colors.period[s] ?? FALLBACK_COLOR
}

/** 达标数 = 判定为 `goal`/`floor` 的条数（与后端分母口径同一把尺子） */
function okOf(p: SelfRunPeriod): string {
  const rows = (p.readings ?? []).filter(r => !r.skipped && r.verdict !== 'unknown')
  const ok = rows.filter(r => r.verdict === 'goal' || r.verdict === 'floor').length
  return `${ok}/${rows.length}`
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { limit: 100 }
    if (filterType.value) params.period_type = filterType.value
    const res = await store.loadPeriods(params as any)
    list.value = res
  } catch {
    list.value = []
    ElMessage.error('加载历史周期失败')
  } finally {
    loading.value = false
  }
}

function openDetail(row: SelfRunPeriod) {
  current.value = row
  reviewText.value = row.review_text ?? ''
  drawer.value = true
}

async function saveReview() {
  const c = current.value
  if (!c) return
  saving.value = true
  try {
    const res = await store.saveReview(c.id, { review_text: reviewText.value })
    current.value = res.period
    await load()
    ElMessage.success('已保存')
    emit('changed')
  } catch (e: any) {
    // 405 = 试图写冻结字段（本页只送 review_text，正常不会触发）—— 原样念出来
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function doReopen() {
  const c = current.value
  if (!c) return
  let reason = ''
  try {
    const r = await ElMessageBox.prompt(
      '重开会把这一期退回「进行中」，读数重新跟着当前口径现算 —— 往期结论会变。写一下为什么。',
      '重开这一期？',
      {
        confirmButtonText: '重开', cancelButtonText: '算了', type: 'warning',
        inputPlaceholder: '例如：那天把周报日期记错了，时间统计补了 8 小时',
        inputValidator: (v: string) => (!!v && v.trim().length > 0) || '必须写原因',
      },
    )
    reason = r.value
  } catch {
    return
  }
  reopening.value = true
  try {
    await store.reopenPeriod(c.id, reason)
    drawer.value = false
    await load()
    ElMessage.success('已重开')
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '重开失败')
  } finally {
    reopening.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.review-panel { display: flex; flex-direction: column; gap: 10px; }
.rp-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.rp-filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.rp-hint { font-size: 12px; color: var(--el-text-color-secondary); }
.rp-mono { font-variant-numeric: tabular-nums; font-size: 12px; }
.rp-tag { border: none; }
.rp-d-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.rp-gap { margin-top: 12px; }
.rp-card-head { display: flex; align-items: center; justify-content: space-between; font-weight: 600; }
.rp-d-footer { display: flex; align-items: center; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.rp-edits { margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--el-border-color-lighter); }
.rp-edit { font-size: 12px; color: var(--el-text-color-secondary); padding: 2px 0; }
.rp-section-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
</style>
