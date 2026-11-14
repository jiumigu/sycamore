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
          归档后的读数是<b>冻结快照</b>，永远不重算 —— 所以这里看到的数就是当时的数。
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
          <el-tag v-if="row.status" size="small" :color="statusColor(row.status)" effect="dark" class="rp-tag">
            {{ periodStatusLabel(row.status, row.period_type) }}
          </el-tag>
          <!-- 老数据：月度没答三问就归档了（v3.64.6 起后端会拦住）—— 说清是「没判」，不是「—」 -->
          <el-tag v-else size="small" type="info" effect="plain" class="rp-tag">未判定</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="分数" width="110">
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
    <el-drawer v-model="drawer" :title="current?.period_key ?? ''" size="720px" append-to-body>
      <template v-if="current">
        <div class="rp-d-tags">
          <el-tag v-if="current.status" size="small" :color="statusColor(current.status)" effect="dark" class="rp-tag">
            {{ periodStatusLabel(current.status, current.period_type) }}
          </el-tag>
          <el-tag v-else size="small" type="info" effect="plain" class="rp-tag">未判定</el-tag>
          <el-tag v-if="current.is_partial" size="small" type="warning" effect="plain">残缺周期</el-tag>
          <el-tag v-if="current.is_backfilled" size="small" type="warning" effect="plain">事后补算</el-tag>
          <!-- 指纹三个月后才有用（查口径漂移）—— 首屏留给正文，它降级成角落一个小字 -->
          <el-tooltip
            :content="`口径指纹 ${current.config_fingerprint || '—'}｜配置改过这里就会变`"
            placement="top"
          >
            <span class="rp-fp">指纹 {{ (current.config_fingerprint || '—').slice(0, 6) }}</span>
          </el-tooltip>
        </div>

        <el-alert
          v-if="current.is_backfilled" type="warning" :closable="false" show-icon class="rp-gap"
          title="这一期是事后补归档的"
          description="补算出来的读数与「当天归档」不等价 —— 数据源在后来的日子里可能被补记或修正过。"
        />

        <!-- ① 这一期的话 —— 这一段是**唯一不可再生**的内容（其余都能重算），所以它排第一。
             🔴 有内容时是**正文**不是输入框：回顾时读自己的往事，不该像在读草稿。 -->
        <el-card shadow="never" class="rp-gap rp-letter-card">
          <template #header>
            <div class="rp-card-head">
              <span>这一期的话</span>
              <span class="rp-head-right">
                <span v-if="hasText && !editing" class="rp-hint">{{ writtenWhen }}</span>
                <el-button
                  v-if="hasText && !editing" link type="primary" size="small"
                  @click="startEdit"
                >
                  改
                </el-button>
                <span v-else-if="!hasText" class="rp-hint">还没写 —— 想到什么写什么，一段就够</span>
              </span>
            </div>
          </template>

          <p v-if="hasText && !editing" class="rp-letter-text">{{ reviewText }}</p>

          <template v-else>
            <!-- 高度随内容自适应：回顾时这段话是**要读的正文**，不是录入草稿，
                 固定 4 行会把它裁成一条缝（minRows 与 maxRows 是唯一一处高度定义） -->
            <el-input
              v-model="reviewText" type="textarea" resize="none"
              :autosize="{ minRows: 5, maxRows: 16 }"
              placeholder="一句话就行 —— 值得记住的不是数字，是你当时怎么想的"
            />
            <div class="rp-d-footer">
              <el-button size="small" type="primary" :loading="saving" @click="saveReview">保存</el-button>
              <el-button v-if="hasText" size="small" @click="cancelEdit">取消</el-button>
              <span class="rp-hint">归档后仍可写；改动会留痕（记下「写于归档后 N 天」）</span>
            </div>
          </template>

          <!-- 脚注：写这段话时我是什么状态 —— 信与当时的读数绑在一起，不让它们各占一屏 -->
          <div v-if="footReadings.length" class="rp-letter-foot">
            <span class="rp-foot-label">写这段话时</span>
            <span v-for="r in footReadings" :key="r.metric_id" class="rp-foot-item">
              {{ r.name }} <b>{{ fmt(r.final_value, r.unit) }}</b>
            </span>
            <span class="rp-foot-more" @click="expandReadings">
              全部 {{ (current.readings ?? []).length }} 条 ⌄
            </span>
          </div>

          <div v-if="current.review_edits.length" class="rp-edits">
            <div class="rp-hint">补写留痕：</div>
            <!-- 原文可能很长（月度那段有上百字）—— 一行省略 + 悬停看全文，
                 否则「这一期的话」下面挂着一大段旧稿，把正文淹掉 -->
            <el-tooltip
              v-for="(e, i) in current.review_edits" :key="i"
              :content="e.text || '（空）'" placement="top" :disabled="!e.text"
            >
              <div class="rp-edit">
                归档后第 {{ e.days_after_close }} 天改过 → 原内容是「{{ e.text || '（空）' }}」
              </div>
            </el-tooltip>
          </div>
        </el-card>

        <!-- ② 这一期我做了什么 —— 回答「我忘了这周干了什么」。
             数字勾不起回忆，做过的事才行；而「几点到几点」只有时段轴给得出。
             🔴 卡片本身在 `WhatHappenedCard`：「本周状态」页（归档按钮下方）
                用的是**同一个组件** —— 两处各写一份，早晚会各自漂移且不报错。 -->
        <WhatHappenedCard
          class="rp-gap"
          :what-happened="extras ? extras.what_happened : null"
          :title="whatTitle"
          :period-type="current?.period_type ?? 'weekly'"
          :period-key="current?.period_key ?? ''"
        />

        <!-- ③ 这一期干成了什么 —— ② 量的是「投入」，这一张量的是「产出」。
             三栏各报各的数（不给跨源总数）；三栏全空时整卡不渲染。 -->
        <OutcomeCard
          v-if="extras && extras.outcomes && !extras.outcomes.empty"
          :outcomes="extras.outcomes"
          :period-type="current?.period_type ?? 'weekly'"
        />

        <!-- ④ 缺口与读数：都是「当时的报表」，默认收起。
             复盘时第一眼不该是欠条 —— 而且它们都能重算，随时可以展开。 -->
        <el-collapse v-model="faces" class="rp-faces">
          <el-collapse-item name="gap">
            <template #title>
              <div class="rp-face">
                <span class="rp-face-name">当时的缺口</span>
                <span v-if="extras" class="rp-face-sum">
                  到期 {{ extras.goals.due }} · 完成 {{ extras.goals.done }} ·
                  <b :class="{ 'rp-warn': extras.goals.missed > 0 }">
                    本期新增逾期 {{ extras.goals.missed }}
                  </b>
                  · 流失 {{ fmt(extras.time_loss.loss_hours) }}h
                </span>
                <span v-else class="rp-face-sum">读取中…</span>
              </div>
            </template>

            <div v-if="!extras" class="rp-hint">读取中…</div>
            <template v-else>
              <div class="rp-sub-title">该交的</div>
              <div class="rp-stat-row">
                <span>到期 <b>{{ extras.goals.due }}</b></span>
                <span>已完成 <b>{{ extras.goals.done }}</b></span>
                <span :class="{ 'rp-warn': extras.goals.missed > 0 }">
                  本期新增逾期 <b>{{ extras.goals.missed }}</b>
                </span>
              </div>
              <ul v-if="extras.goals.items.length" class="rp-mini-list">
                <li v-for="it in extras.goals.items" :key="it.id">
                  <span class="rp-dot" :class="it.status === 'completed' ? 'ok' : 'todo'" />
                  <span class="rp-mini-name">{{ it.title }}</span>
                  <span class="rp-muted">{{ it.goal }} · {{ it.target_date ?? '—' }}</span>
                </li>
              </ul>
              <div v-else class="rp-hint">这一期没有到期的里程碑。</div>
              <!-- 🔴 历史积压不按周算：这个数每期都一样，放在「本周」里只会被读成
                   「这周又欠了 27」。它是「目标」模块的账。 -->
              <div v-if="extras.goals.overdue" class="rp-note">
                另有 {{ extras.goals.overdue }} 项早先到期、至今未清 —— 这笔账不按周重算，去「目标」里清（每期印同一个数只会变成背景噪音）。
              </div>

              <div class="rp-sub-title rp-sub-gap">流走的时间</div>
              <div class="rp-stat-row">
                <span><b>{{ fmt(extras.time_loss.loss_hours) }}</b> h</span>
                <span v-if="extras.time_loss.ratio !== null" class="rp-warn">
                  占记录的 {{ (extras.time_loss.ratio * 100).toFixed(1) }}%
                </span>
                <span v-else class="rp-muted">本期没有任何时间记录</span>
                <span>日均 {{ fmt(extras.time_loss.per_day) }} h</span>
              </div>
              <ul v-if="extras.time_loss.top.length" class="rp-mini-list">
                <li v-for="t in extras.time_loss.top" :key="t.task_name">
                  <span class="rp-mini-name">{{ t.task_name }}</span>
                  <span class="rp-muted">{{ fmt(t.hours) }} h</span>
                </li>
              </ul>
              <div v-else class="rp-hint">这一期没有「流失」记录 —— 挺好。</div>
            </template>
          </el-collapse-item>

          <el-collapse-item name="readings" class="rp-readings">
            <template #title>
              <div class="rp-face">
                <span class="rp-face-name">当时的逐条读数</span>
                <span class="rp-face-sum">
                  {{ (current.readings ?? []).length }} 条 · 冻结不可改
                </span>
              </div>
            </template>

            <!-- 档位来源：月度只看三问 —— 复盘时必须能看见「当时选了什么」，
                 否则档位就是一个没有出处的词（v3.64.6） -->
            <div v-if="current.period_type === 'monthly'" class="rp-sub">
              <div class="rp-sub-title">
                当时的三问
                <span class="rp-hint">本月档位的唯一来源；归档后补答不改档</span>
              </div>
              <ul class="rp-mini-list">
                <li v-for="q in MONTHLY_QUESTIONS" :key="q.key">
                  <span class="rp-dot" :class="current.answer_sheet?.[q.key]?.answer ? 'ok' : 'todo'" />
                  <span class="rp-mini-name">{{ q.label }}</span>
                  <span class="rp-muted">{{ answerLabel(current.answer_sheet?.[q.key]?.answer) }}</span>
                </li>
              </ul>
            </div>

            <ReadingCard
              v-for="r in current.readings ?? []" :key="r.metric_id"
              :reading="r" :editable="false"
            />
          </el-collapse-item>
        </el-collapse>

        <!-- 「重开」是破坏性操作，不该贴着「保存」并排（v3.64.14 挪到页底） -->
        <div v-if="isLatest" class="rp-bottom">
          <el-button size="small" text type="warning" :loading="reopening" @click="doReopen">
            重开这一期
          </el-button>
          <span class="rp-hint">改历史判定的<b>唯一出口</b>，只允许最近一期、必须写原因</span>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ReadingCard from '../components/ReadingCard.vue'
import OutcomeCard from '../components/OutcomeCard.vue'
import WhatHappenedCard from '../components/WhatHappenedCard.vue'
import { useSelfRunStore } from '../stores/selfrunStore'
import { getPeriodDetail } from '../api/selfrunApi'
import { FALLBACK_COLOR, MONTHLY_QUESTIONS, fmt, periodStatusLabel } from '../types/selfrunTypes'
import type { PeriodExtras, PeriodType, SelfRunPeriod } from '../types/selfrunTypes'

const emit = defineEmits<{ (e: 'changed'): void }>()

const store = useSelfRunStore()
const loading = ref(false)
const saving = ref(false)
const reopening = ref(false)
const filterType = ref<PeriodType | ''>('')
const list = ref<SelfRunPeriod[]>([])
const drawer = ref(false)
/** 复盘三块补充（本期做过什么 / 到期里程碑 / 时间流失）；`null` = 没取到 / 读取中 */
const extras = ref<PeriodExtras | null>(null)
const current = ref<SelfRunPeriod | null>(null)
const reviewText = ref('')
/** 卡片是**读**还是**写**：有内容时先给正文，点「改」才换成输入框 */
const editing = ref(false)
/** 折叠区（`gap` 缺口 / `readings` 逐条读数）—— 默认全收起，欠账不占首屏 */
const faces = ref<string[]>([])

const hasText = computed(() => reviewText.value.trim().length > 0)

const whatTitle = computed(() =>
  current.value?.period_type === 'monthly' ? '这一个月我做了什么' : '这一周我做了什么')

/** 「这句话是什么时候写的」—— 归档后补写的必须与当天写的分开说 */
const writtenWhen = computed(() => {
  const c = current.value
  if (!c) return ''
  const edits = c.review_edits ?? []
  if (!edits.length) return '归档当天写的'
  const d = edits[edits.length - 1].days_after_close
  return d <= 0 ? '归档当天补写' : `归档后第 ${d} 天补写`
})

/** 脚注只看**有结论**的读数：`unknown`（没数据）和「本期先不算」都不该混进来 */
const footReadings = computed(() => (current.value?.readings ?? [])
  .filter(r => !r.skipped && r.verdict !== 'unknown' && r.final_value !== null)
  .slice(0, 4))

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

/** 三问答案的显示词（`null` 是「没答」，不是「否」——两件事） */
function answerLabel(a?: boolean | null): string {
  if (a === true) return '是'
  if (a === false) return '否'
  return '未答'
}

/** 分数列：**必须与这一行档位同源**（周 = KPI 达标数；月 = 三问几比几）。
 *
 * 🔴 月度原来也显示 `达标 4/4`，而档位印的是「合格」（三问 2/3）——
 *    同一行里 100% 配「合格」，读起来就是「4/4 才合格」（v3.64.6 修）。
 */
function okOf(p: SelfRunPeriod): string {
  if (p.period_type === 'monthly') {
    const sheet = p.answer_sheet ?? {}
    const bools = MONTHLY_QUESTIONS.map((q) => sheet[q.key]?.answer)
    const answered = bools.filter((a) => a === true || a === false).length
    if (!answered) return '未答'
    return `三问 ${bools.filter((a) => a === true).length}/${MONTHLY_QUESTIONS.length}`
  }
  const rows = (p.readings ?? []).filter(r => !r.skipped && r.verdict !== 'unknown')
  const ok = rows.filter(r => r.verdict === 'goal' || r.verdict === 'floor').length
  return `达标 ${ok}/${rows.length}`
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
  // 还没写过 ⇒ 直接进编辑态（别让人先点一下「改」）；写过 ⇒ 先给正文
  editing.value = !reviewText.value.trim()
  faces.value = []
  extras.value = null
  // 「时段 / 清单」的默认看法由 `WhatHappenedCard` 按 `period_key` 自己重置 ——
  // 这里不用管：上期看月、这期看周，也不会打开成一张「月视图」的周。
  drawer.value = true
  loadExtras(row.id)
}

function startEdit() {
  editing.value = true
}

function cancelEdit() {
  reviewText.value = current.value?.review_text ?? ''
  editing.value = false
}

/** 点「全部 N 条」：展开读数折叠区并滚到它 —— 否则那个 ⌄ 是个点了没反应的死箭头 */
async function expandReadings() {
  if (!faces.value.includes('readings')) faces.value = [...faces.value, 'readings']
  await nextTick()
  // 🔴 `el-collapse` 展开有 300ms 高度过渡：量早了拿到的是展开前的矩形，
  //    滚动量会偏小，结果「点了箭头只挪了一点」。等过渡结束再量。
  await new Promise((r) => setTimeout(r, 320))
  const el = document.querySelector('.rp-readings') as HTMLElement | null
  const box = el?.closest('.el-drawer__body') as HTMLElement | null
  if (!el || !box) return
  // 用矩形差值算，不赌 offsetTop（offsetParent 未必是抽屉体）
  const r1 = el.getBoundingClientRect()
  const r2 = box.getBoundingClientRect()
  box.scrollTo({ top: box.scrollTop + (r1.top - r2.top) - 8, behavior: 'smooth' })
}

/** 🔴 列表接口不带 `extras`（那是每期现算的，带在列表里就是 N 次遍历），
 *  所以打开抽屉时单独取一次详情。取不到就保持 `null` —— 卡片显示「读取中…」，
 *  不伪装成「这周没有到期项」。 */
async function loadExtras(id: number) {
  try {
    const res = await getPeriodDetail(id)
    // 用户可能已经切到别的期了 —— 回来时只认当前这一期
    if (current.value?.id === id) extras.value = res.data.extras
  } catch {
    if (current.value?.id === id) extras.value = null
  }
}

async function saveReview() {
  const c = current.value
  if (!c) return
  saving.value = true
  try {
    const res = await store.saveReview(c.id, { review_text: reviewText.value })
    current.value = res.period
    reviewText.value = res.period.review_text ?? reviewText.value
    editing.value = false
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
.rp-d-tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.rp-fp { margin-left: auto; font-size: 12px; color: var(--el-text-color-placeholder); cursor: help; }
.rp-gap { margin-top: 12px; }
.rp-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-weight: 600; }
.rp-head-right { display: flex; align-items: center; gap: 8px; }
.rp-d-footer { display: flex; align-items: center; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.rp-edits { margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--el-border-color-lighter); }
.rp-edit {
  font-size: 12px; color: var(--el-text-color-secondary); padding: 2px 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ① 这一期的话：回顾时它是正文，不是草稿 */
.rp-letter-text {
  margin: 0; font-size: 15px; line-height: 1.95; letter-spacing: 0.2px;
  color: var(--el-text-color-primary);
  white-space: pre-wrap; word-break: break-word;
}
.rp-letter-foot {
  display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap;
  margin-top: 14px; padding-top: 10px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px; color: var(--el-text-color-secondary);
}
.rp-foot-label { color: var(--el-text-color-placeholder); }
.rp-foot-item b { font-weight: 600; color: var(--el-text-color-primary); font-variant-numeric: tabular-nums; }
.rp-foot-more { margin-left: auto; color: var(--el-color-primary); cursor: pointer; }

/* ② 「这一期我做了什么」的样式随组件走（`WhatHappenedCard` 的 `.whc-*`），
      这里不再留任何 `.rp-day*` / `.rp-attr*` —— 留在原处会让人以为本页还在用。 */

/* ③ 折叠区：缺口与读数 */
.rp-faces { margin-top: 12px; }
.rp-faces :deep(.el-collapse-item__header) { font-weight: 500; }
.rp-faces :deep(.el-collapse-item__content) { padding-bottom: 6px; }
.rp-face { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; width: 100%; }
.rp-face-name { font-size: 13px; font-weight: 500; }
.rp-face-sum { font-size: 12px; color: var(--el-text-color-secondary); }
.rp-face-sum b { font-variant-numeric: tabular-nums; }
.rp-sub { margin-bottom: 10px; }
.rp-sub-title { font-size: 13px; font-weight: 600; margin: 8px 0 6px; }
.rp-sub-gap { margin-top: 16px; }
.rp-note {
  margin-top: 8px; font-size: 12px; line-height: 1.6;
  color: var(--el-text-color-secondary);
}

/* 缺口里那两块补充 */
.rp-stat-row { display: flex; align-items: baseline; gap: 16px; font-size: 13px; }
.rp-stat-row b { font-size: 16px; font-variant-numeric: tabular-nums; }
.rp-warn { color: var(--el-color-warning); }
.rp-muted { color: var(--el-text-color-secondary); font-size: 12px; }
.rp-mini-list { margin: 8px 0 0; padding: 0; list-style: none; }
.rp-mini-list li {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; font-size: 12px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.rp-mini-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rp-dot { width: 6px; height: 6px; border-radius: 50%; flex: none; }
.rp-dot.ok { background: var(--el-color-success); }
.rp-dot.todo { background: var(--el-color-warning); }

.rp-bottom {
  display: flex; align-items: center; justify-content: flex-end; gap: 10px;
  margin-top: 16px; padding-top: 12px; flex-wrap: wrap;
  border-top: 1px dashed var(--el-border-color-lighter);
}
</style>
