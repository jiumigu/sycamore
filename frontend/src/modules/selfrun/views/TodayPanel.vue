<!--
  「今天」四格 · 定档 / 结算（v3.64.76）

  🔴 这一页**不持有数据**：候选、计数、理由全部现算。「标完成」调的是
     goals / inbox / works 现有的接口（路径由后端随候选下发）。
     它自己只写一张表 —— `selfrun_day_cell`（走了一格 / 成没成 / 一句话）。

  🔴 四条规则（见设计稿 §4.2，这三条是这功能能不能用起来的关键）：

     ① 未定档时**只显示「每格有几件」，不显示候选** —— 点一格就是定档。
        省掉这一步，页面就又变回一个 426 件的列表。
     ② 一天只有一格：定完其余三格**缩成一行小字**（当天可换，跨天锁定在后端）。
     ③ 风干 `count=0` 但**必须可点**：它的 0 不是「没有活」，
        是「这一格本来就没有清单」。所以能不能点只看 `selectable`，
        **不许**写成 `count > 0`。
     ④ 三种空不许混：`empty_reason`（为什么空）在格内说，`quadrant=null`
        （那天没定档）在色带上说，`outcome=''`（没结算）在结算条上说。
-->
<template>
  <div class="today-panel" v-loading="loading">
    <!-- ── 页头：日期归页面，不在页签里重复 ────────────────── -->
    <div class="tp-head">
      <div class="tp-date">
        <span class="tp-date-num">{{ payload?.date ?? '—' }}</span>
        <span class="tp-date-week">{{ payload?.weekday ?? '' }}</span>
      </div>
      <div class="tp-hint">{{ cell ? '今天走这一格' : '' }}</div>
    </div>

    <!-- ══ 未定档：四格是「选项」 ═══════════════════════════
         🔴 上面那行提示（v3.64.80）不是装饰：四个格子只有 hover 才有反应，
            静止时与统计卡长得一样 —— 用户真的在这一屏上问过「定档入口在哪」。
            所以把「点一格就是定档」写成一句话摆在格子正上方，
            而不是缩在页头右上角 12px 灰字里。 -->
    <template v-if="!cell">
      <div class="tp-ask">
        <span class="tp-ask-title">今天走哪一格？</span>
        <span class="tp-ask-sub">点一格就定档 —— 一天只走一格，过了 24 点不能再改</span>
      </div>
      <div class="tp-quadrants">
        <button
          v-for="q in quadrants"
          :key="q.quadrant"
          type="button"
          class="tp-quad"
          :class="{ 'is-off': !q.selectable, 'is-busy': defining === q.quadrant }"
          :style="{ '--q-color': q.color }"
          :disabled="!q.selectable || !!defining"
          :title="q.selectable ? `点这一格：今天按「${q.label}」走` : `「${q.label}」今天没排活`"
          @click="define(q.quadrant)"
        >
          <span class="tp-quad-label">{{ q.label }}</span>
          <!-- 风干的 0 不是「0 件活」，是「不排活」——词不同，因为事不同 -->
          <span class="tp-quad-count">
            {{ q.quadrant === 'rest' ? '不排活' : `${q.count} 件` }}
          </span>
        </button>
      </div>

      <!-- 四格全空：给一句总口径 + 两个真实出口（不是「去加一件」这种空话） -->
      <div v-if="payload?.empty_reason === 'all_empty'" class="tp-all-empty">
        <p>今天没有任何排着的活。要么去加一件，要么就选风干。</p>
        <div class="tp-all-empty-acts">
          <el-button size="small" @click="go('/goals')">去人生目标</el-button>
          <el-button size="small" @click="go('/inbox')">去收件箱</el-button>
        </div>
      </div>
    </template>

    <!-- ══ 已定档：这一格展开，其余三格缩成一行 ═════════════ -->
    <template v-else>
      <div class="tp-chosen" :style="{ '--q-color': activeColor }">
        <div class="tp-chosen-head">
          <span class="tp-chosen-label">{{ cell.quadrant_label }}</span>
          <span v-if="cell.is_backfilled" class="tp-chosen-tag">补记</span>
          <span
            v-if="cell.quadrant !== 'rest' && cell.total > cell.candidates.length"
            class="tp-chosen-total"
          >
            <!-- 🔴 池子规模在这里说，不在格子上说。措辞不催：「手上还有」是陈述，
                 「你还有 X 件没做」是讨债 —— 同一件事，后者会让人关掉这一页。 -->
            这一类手上还有 {{ cell.total }} 件；今天只看这三件
          </span>
        </div>

        <!-- 风干：没有清单，也不该有 —— 休了就是休了，没有「成没成」 -->
        <div v-if="cell.quadrant === 'rest'" class="tp-rest">
          今天不排活。这一格没有清单，也不需要结算。
        </div>

        <template v-else>
          <div v-if="cell.candidates.length" class="tp-list">
            <div v-for="(c, i) in cell.candidates" :key="`${c.kind}-${c.id}`" class="tp-row">
              <span class="tp-idx">{{ i + 1 }}</span>
              <div class="tp-main">
                <div class="tp-title">{{ c.title }}</div>
                <div class="tp-sub">
                  <span v-if="c.subtitle" class="tp-sub-text">{{ c.subtitle }}</span>
                  <!-- reason 由后端按排序依据生成 —— 前端原样显示，不自己拼「逾期几天」 -->
                  <span class="tp-reason">{{ c.reason }}</span>
                </div>
              </div>
              <div class="tp-acts">
                <el-button link size="small" @click="go(c.open_route)">打开</el-button>
                <!-- 🔴 书没有 done：读完由换书动作触发，不在这一行里做 -->
                <el-button
                  v-if="c.done" size="small" type="primary" plain
                  :loading="finishing === `${c.kind}-${c.id}`"
                  @click="finish(c)"
                >完成</el-button>
              </div>
            </div>
          </div>

          <!-- 空态由后端给原因码，这里只查表 —— 文案写死就是零态 -->
          <div v-else class="tp-empty">
            <p>{{ emptyText(cell.empty_reason) }}</p>
            <el-button v-if="cell.empty_reason === 'no_focus'" size="small" @click="go('/books')">
              去书库选一本
            </el-button>
          </div>

          <!-- 有候选、但还没有「当前这本」：这条提示**不能**挂在 empty_reason 上
               （格子不为空，那个字段是 null），所以是独立的一条。 -->
          <div v-if="cell.no_focus && cell.candidates.length" class="tp-note">
            还没指定「当前这本」—— 播种的第一条本该是它。
            <el-button link size="small" type="primary" @click="go('/books')">去书库选一本</el-button>
          </div>

          <!-- 结算：`outcome=''` = 还没结算。它**不是**「没成」，所以不显示成灰点 -->
          <div class="tp-settle">
            <template v-if="!cell.outcome">
              <span class="tp-settle-q">这一格成了吗？</span>
              <el-button
                size="small" type="primary" plain
                :loading="settling === `${cell.id}:done`"
                @click="settle(cell.id, 'done')"
              >成了</el-button>
              <el-button
                size="small" plain
                :loading="settling === `${cell.id}:missed`"
                @click="settle(cell.id, 'missed')"
              >没成</el-button>
            </template>
            <!-- 回显用后端给的词（`outcome_label` 在前端只有一份映射，这里不另写 -->
            <span v-else class="tp-settled">记下了：{{ cell.outcome === 'done' ? '成了' : '没成' }}</span>
          </div>
        </template>
      </div>

      <!-- 其余三格：一行小字。点它就是改档（当天可改，跨天后端会拒） -->
      <div class="tp-switch">
        <span class="tp-switch-label">换成</span>
        <button
          v-for="q in others"
          :key="q.quadrant"
          type="button"
          class="tp-switch-item"
          :style="{ '--q-color': q.color }"
          :disabled="!q.selectable || !!switching"
          @click="switchTo(q.quadrant)"
        >
          {{ q.label }}
          <span class="tp-switch-count">{{ q.quadrant === 'rest' ? '不排活' : `${q.count} 件` }}</span>
        </button>
        <span class="tp-switch-note">当天可换，过了 24 点就定了</span>
      </div>
    </template>

    <!-- ══ 还有一格没结算（最近的那天） ═════════════════════ -->
    <div v-if="prompt" class="tp-prompt">
      <span class="tp-prompt-text">{{ promptText }}</span>
      <el-button
        size="small" type="primary" plain
        :loading="settling === `${prompt.cell_id}:done`"
        @click="settle(prompt.cell_id, 'done')"
      >成了</el-button>
      <el-button
        size="small" plain
        :loading="settling === `${prompt.cell_id}:missed`"
        @click="settle(prompt.cell_id, 'missed')"
      >没成</el-button>
    </div>

    <!-- ══ 这一周 ═══════════════════════════════════════════
         🔴 色带是共享组件：同一份 7 格也出现在「本周状态」页，
            各写一份就是改一处漏一处。图例传 `quadrants` —— 那是后端
            下发的四格词与配色，组件自己不持有任何一份。 -->
    <div v-if="payload" class="tp-week-wrap">
      <DayWeekStrip
        :days="payload.week"
        :summary="payload.week_summary"
        :legend="payload.quadrants"
        :today="payload.date"
      />
    </div>

    <!-- ══ 补记：色带上看得见的洞，在这里点得动 ═══════════════
         只列「还空着的那几天」，不写「全部记齐」这种无信息的话。
         入口与色带摆在一起：洞在色带上，出口就在它下面。 -->
    <div v-if="backfillDays.length" class="tp-backfill">
      <span>最近 {{ backfillLimit }} 天还有 {{ backfillDays.length }} 天没记</span>
      <el-button link size="small" type="primary" @click="openBackfill">补记</el-button>
    </div>

    <!-- 补记弹窗：一个入口只问一件事（走了哪一格）。
         「成了吗」不在这里问 —— 记完结算条会接着问，那是它的活。 -->
    <el-dialog v-model="bfOpen" title="补记一天" width="400px" append-to-body>
      <div class="bf-form">
        <div class="bf-field">
          <span class="bf-label">哪一天</span>
          <el-select v-model="bfDate" size="small" placeholder="选一天" style="width: 150px">
            <el-option
              v-for="d in backfillDays" :key="d.date"
              :label="`${d.date.slice(5)} ${d.weekday}`" :value="d.date"
            />
          </el-select>
        </div>
        <div class="bf-field bf-field-top">
          <span class="bf-label">走了哪一格</span>
          <!-- 🔴 这里**不显示件数**：`count` 是今天的池子，补的是三天前 -->
          <div class="bf-quads">
            <button
              v-for="q in quadrants" :key="q.quadrant"
              type="button"
              class="bf-quad"
              :class="{ 'is-on': bfQuadrant === q.quadrant }"
              :style="{ '--q-color': q.color }"
              @click="bfQuadrant = q.quadrant"
            >{{ q.label }}</button>
          </div>
        </div>
        <p class="bf-note">补记只记「走了哪一格」；成了没有，记完这一页会接着问你。</p>
      </div>
      <template #footer>
        <el-button size="small" @click="bfOpen = false">取消</el-button>
        <el-button
          size="small" type="primary"
          :disabled="!bfDate || !bfQuadrant"
          :loading="bfSaving"
          @click="saveBackfill"
        >记下</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  completeCandidate, createDayCell, getToday, patchDayCell,
} from '../api/selfrunApi'
import type {
  DayCandidate, DayEmptyReason, DayOutcome, DayQuadrant, TodayPayload,
} from '../types/selfrunTypes'
import DayWeekStrip from '../components/DayWeekStrip.vue'
import { promptCompletionReview } from '@/shared/utils/completionReview'

const router = useRouter()

const loading = ref(false)
const payload = ref<TodayPayload | null>(null)
/** 正在定档的那一格（只让它转圈，不让四格一起灰） */
const defining = ref<DayQuadrant | ''>('')
/** 正在改档的那一格 */
const switching = ref<DayQuadrant | ''>('')
/** 正在结算的 `<cellId>:<outcome>` */
const settling = ref('')
/** 正在提交的候选行（`kind-id`），用来只让那一行转圈 */
const finishing = ref('')

/* ── 补记 ── */
const bfOpen = ref(false)
const bfDate = ref('')
const bfQuadrant = ref<DayQuadrant | ''>('')
const bfSaving = ref(false)

const cell = computed(() => payload.value?.cell ?? null)
const quadrants = computed(() => payload.value?.quadrants ?? [])
const prompt = computed(() => payload.value?.settle_prompt ?? null)

/** 还空着的那几天（不含今天）。列表本身由后端算 —— 窗口是 `今-7 … 昨`，
 *  与色带的 `今-6 … 今` 错开一天，前端照色带去推会漏掉第 7 天。 */
const backfillDays = computed(() => payload.value?.backfill.days ?? [])
const backfillLimit = computed(() => payload.value?.backfill.limit ?? 0)

/** 已选那一格的颜色；风干也要有颜色（它不是「没有格」） */
const activeColor = computed(
  () => quadrants.value.find((q) => q.quadrant === cell.value?.quadrant)?.color ?? '#4A4A4A',
)

/** 定完之后，其余三格 —— 它们是出口，不是选项 */
const others = computed(() => quadrants.value.filter((q) => q.quadrant !== cell.value?.quadrant))

/** 空态文案表（原因码 → 话）。🔴 风干不进这张表：它不是「空」。 */
const EMPTY_TEXT: Record<Exclude<DayEmptyReason, 'all_empty'>, string> = {
  no_focus: '还没指定「当前这本」。指定一本之后，这一格第一条就是它。',
  no_candidates: '这一类今天没有排着的活。',
}

function emptyText(reason: DayEmptyReason | null): string {
  if (!reason || reason === 'all_empty') return '这一类今天没有排着的活。'
  return EMPTY_TEXT[reason]
}

/** 后端错误码：前端按码分流，不按文案猜 */
function errCode(e: unknown): string {
  return (e as { response?: { data?: { code?: string } } })?.response?.data?.code ?? ''
}

/** ⚠️ 补记的日子单独说一句 —— 色带上它和「当天记的」长得一样，
 *  但「事后补的」与「当天记的」在复盘时不是一回事。 */
const promptText = computed(() => {
  const p = prompt.value
  if (!p) return ''
  const when = p.days_ago === 1 ? '昨天' : `${p.days_ago} 天前`
  return `${when}选了「${p.quadrant_label}」，成了吗？`
})

async function loadToday() {
  loading.value = true
  try {
    const { data } = await getToday()
    payload.value = data
  } catch {
    ElMessage.error('取「今天」失败')
  } finally {
    loading.value = false
  }
}

/** 定档：点一格就是一次决定，不再弹确认。
 *
 *  🔴 不给二次确认是有意的：定档是这个功能的**仪式**，弹窗会把它变成
 *     「又一个要点两下的表单」。点错了当场就能换（其余三格那一行）。
 */
async function define(quadrant: DayQuadrant) {
  if (defining.value) return
  defining.value = quadrant
  try {
    await createDayCell({ quadrant })
    await loadToday()
  } catch (e) {
    const code = errCode(e)
    if (code === 'already_set') {
      // 409：今天已经定过了（另一个标签页 / 双击）—— 直接切到当前状态，不报错
      await loadToday()
      ElMessage.info('今天已经定过档了')
    } else {
      ElMessage.error('没定上，再试一次')
    }
  } finally {
    defining.value = ''
  }
}

async function switchTo(quadrant: DayQuadrant) {
  if (!cell.value || switching.value) return
  switching.value = quadrant
  try {
    await patchDayCell(cell.value.id, { quadrant })
    await loadToday()
  } catch (e) {
    ElMessage.error(
      errCode(e) === 'locked' ? '那天已经过去了，改不动了' : '没改成，再试一次',
    )
  } finally {
    switching.value = ''
  }
}

async function settle(cellId: number, outcome: DayOutcome) {
  const key = `${cellId}:${outcome}`
  if (settling.value) return
  settling.value = key
  try {
    await patchDayCell(cellId, { outcome })
    await loadToday()
  } catch (e) {
    ElMessage.error(
      errCode(e) === 'rest_not_settled' ? '风干不结算' : '没记上，再试一次',
    )
  } finally {
    settling.value = ''
  }
}

/** 打开补记：「哪一天」默认选最近的那天 —— 补记十次有九次是补昨天。 */
function openBackfill() {
  bfDate.value = backfillDays.value[0]?.date ?? ''
  bfQuadrant.value = ''
  bfOpen.value = true
}

/** 记下补记。🔴 写的是同一个 `POST /day-cells/`，只是多给一个 `cell_date`;
 *  `is_backfilled` 由后端按日期差算，不由前端传 —— 传进来就能撒谎。 */
async function saveBackfill() {
  if (!bfDate.value || !bfQuadrant.value || bfSaving.value) return
  bfSaving.value = true
  try {
    await createDayCell({ cell_date: bfDate.value, quadrant: bfQuadrant.value })
    bfOpen.value = false
    ElMessage.success('记上了')
    // 重取：那一天从补记列表里消失，色带上多一个格子，结算条可能多一条
    await loadToday()
  } catch (e) {
    const code = errCode(e)
    if (code === 'already_set' || code === 'too_late') {
      // 别的标签页刚记过 / 窗口在打开弹窗这段时间里滑走了 —— 都是重取后自然消失
      ElMessage.info(code === 'too_late' ? '那天太早了，补不了' : '那天已经记过了')
      bfOpen.value = false
      await loadToday()
    } else {
      ElMessage.error('没记上，再试一次')
    }
  } finally {
    bfSaving.value = false
  }
}

async function finish(c: DayCandidate) {
  if (!c.done) return

  // 🔴 里程碑要先留一句批阅 —— 后端强制（goals/services/completion_review.py），
  //    只发状态会 400。之前这里直接 PATCH，于是 131 条完成里只有 41 条有批阅：
  //    目标页的完成弹窗必填、这里不问，人一定走不问的那条。
  //    交互与文案的**唯一实现**在 `shared/utils/completionReview`（行为追踪卡共用）。
  //    ⚠️ 字段名属于 goals 的契约；本页只负责收集与转发。
  let extra: Record<string, unknown> | undefined
  if (c.kind === 'milestone') {
    const review = await promptCompletionReview(
      '这一条做完了。写一句留给以后的自己 —— 难在哪，下次怎么改。',
    )
    // `null` = 用户自己点了「还没做完」：既不是失败，也不该标完成。
    // 这里静默返回 —— 弹一个「取消失败」的提示才是真误导。
    if (review === null) return
    extra = { self_review: review }
  }

  const key = `${c.kind}-${c.id}`
  finishing.value = key
  try {
    await completeCandidate(c.done, extra)
    ElMessage.success('已完成')
    // 候选与计数都要重取：那一件已经不在池子里了，不刷新就是「点了没反应」
    await loadToday()
  } catch {
    ElMessage.error('没标上，再试一次')
  } finally {
    finishing.value = ''
  }
}

function go(route: string) {
  router.push(route)
}

onMounted(loadToday)
</script>

<style scoped lang="scss">
.tp-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.tp-date { display: flex; align-items: baseline; gap: 8px; }
.tp-date-num {
  font-size: 20px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}
.tp-date-week { font-size: 13px; color: var(--el-text-color-secondary); }
.tp-hint { font-size: 12px; color: var(--el-text-color-secondary); }

/* 「点一格就定档」这句话必须紧贴四格（v3.64.80）：它解释的是下面那四个格子，
   放页头右上角就变成一句谁都不读的灰字。 */
.tp-ask {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.tp-ask-title { font-size: 13px; font-weight: 600; color: var(--el-text-color-primary); }
.tp-ask-sub { font-size: 12px; color: var(--el-text-color-secondary); }

/* 四格：一行四列，窄屏两列。用 button 而不是 div —— 它天生可聚焦、可键盘点。 */
.tp-quadrants {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.tp-quad {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-left: 3px solid var(--q-color);
  border-radius: 6px;
  background: var(--el-bg-color);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s, transform 0.15s;
}
/* hover 要**一眼看出可点**：光换边色在浅色底上几乎看不见。
   抬起 1px + 一道同色阴影，是「这是个按钮」最省字的一种说法。 */
.tp-quad:hover:not(:disabled) {
  border-color: var(--q-color);
  background: var(--el-fill-color-light);
  box-shadow: 0 2px 8px -2px color-mix(in srgb, var(--q-color) 45%, transparent);
}
.tp-quad:active:not(:disabled) { transform: translateY(1px); }
.tp-quad:focus-visible { outline: 2px solid var(--q-color); outline-offset: 1px; }
/* 不可点的那三格：降不透明度，但**保留**颜色标识 —— 灰成一团就分不清是哪一格了 */
.tp-quad.is-off { cursor: not-allowed; opacity: 0.45; }
.tp-quad.is-busy { opacity: 0.7; }
.tp-quad-label { font-size: 14px; font-weight: 600; color: var(--q-color); }
.tp-quad-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.tp-all-empty {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.tp-all-empty p { margin: 0 0 8px; }
.tp-all-empty-acts { display: flex; gap: 8px; }

/* ── 已定档的那一格：一张宽卡，左沿一道色条（四格里只剩它有颜色） ── */
.tp-chosen {
  padding: 12px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-left: 3px solid var(--q-color);
  border-radius: 6px;
  background: var(--el-bg-color);
}
.tp-chosen-head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 4px;
}
.tp-chosen-label { font-size: 15px; font-weight: 600; color: var(--q-color); }
.tp-chosen-tag {
  padding: 0 6px;
  border-radius: 3px;
  background: var(--el-fill-color);
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.tp-chosen-total { font-size: 12px; color: var(--el-text-color-secondary); }

.tp-rest {
  padding: 12px 0 4px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

/* 「还没指定当前这本」：一条待办式的提示，不是错误 —— 左边一道主色竖线就够，
   不用 alert 的那种黄底（它会把下面三条候选压下去）。 */
.tp-note {
  margin-top: 10px;
  padding: 8px 12px;
  border-left: 2px solid var(--el-color-primary);
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.tp-list { display: flex; flex-direction: column; }
.tp-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}
.tp-row:last-child { border-bottom: none; }
.tp-idx {
  flex: none;
  width: 18px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-variant-numeric: tabular-nums;
  line-height: 22px;
}
.tp-main { flex: 1; min-width: 0; }
/* 标题可能很长（收件箱内容上限 500 字）⇒ 两行截断，不撑破行高 */
.tp-title {
  font-size: 13px;
  color: var(--el-text-color-primary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.tp-sub {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.tp-sub-text { min-width: 0; }
/* 理由单独一色：它是「为什么排在这一位」，与副标题不是一类信息 */
.tp-reason { color: var(--el-text-color-placeholder); }
.tp-acts { flex: none; display: flex; align-items: center; gap: 4px; }

.tp-empty {
  padding: 14px 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.tp-empty p { margin: 0 0 8px; }

/* 结算：贴着候选列表尾部，一行就够 —— 它不是第二个页面 */
.tp-settle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.tp-settle-q { color: var(--el-text-color-regular); }
.tp-settled { color: var(--el-text-color-regular); }

/* ── 其余三格：一行小字。有颜色、但不再是「卡片」 ── */
.tp-switch {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 10px;
  padding: 0 2px;
}
.tp-switch-label { font-size: 12px; color: var(--el-text-color-placeholder); }
.tp-switch-item {
  padding: 2px 0;
  border: none;
  background: none;
  font-size: 12px;
  color: var(--q-color);
  cursor: pointer;
}
.tp-switch-item:hover:not(:disabled) { text-decoration: underline; }
.tp-switch-item:disabled { color: var(--el-text-color-placeholder); cursor: not-allowed; }
.tp-switch-count { margin-left: 4px; color: var(--el-text-color-placeholder); }
.tp-switch-note { margin-left: auto; font-size: 11px; color: var(--el-text-color-placeholder); }

/* ── 结算提示：横条，不抢四格的位置 ── */
.tp-prompt {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  padding: 10px 14px;
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.tp-prompt-text { margin-right: 4px; }

/* ── 这一周：7 个方块的样式全在 `DayWeekStrip.vue`（唯一实现），
      这里只管它与上面内容的间距。 */
.tp-week-wrap { margin-top: 16px; }

/* ── 补记入口：一行小字，不抢四格的位置。
      它是家务，不是今天的问题 —— 所以只有一句话加一个链接。 */
.tp-backfill {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

/* ── 补记弹窗 ── */
.bf-form { display: flex; flex-direction: column; gap: 14px; }
.bf-field { display: flex; align-items: center; gap: 12px; }
/* 四格那一行要顶对齐：标签在左，按钮组可能折行 */
.bf-field-top { align-items: flex-start; }
.bf-label {
  flex: none;
  width: 68px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.bf-quads { display: flex; flex-wrap: wrap; gap: 8px; }
/* 四格按钮：只承载「哪一格」，**不带件数** —— 件数是今天的池子，
   补的却是三天前，摆在一起就是两个时期的数看着像同一件事。 */
.bf-quad {
  padding: 4px 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: var(--el-bg-color);
  font-size: 13px;
  color: var(--q-color);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.bf-quad:hover { border-color: var(--q-color); }
.bf-quad.is-on {
  border-color: var(--q-color);
  background: var(--el-fill-color-light);
  font-weight: 600;
}
.bf-note {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}

@media (max-width: 720px) {
  .tp-quadrants { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tp-switch-note { display: none; }
}
</style>
