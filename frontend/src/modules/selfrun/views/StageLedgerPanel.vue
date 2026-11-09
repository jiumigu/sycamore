<!-- 阶段账本 · 长阶段详情页
     ────────────────────────────────────────────────────────────
     「一段长路」上的一屏：钱 / 时间 / 作品 + 它下面的小阶段。

     🔴 这一页**不给**：KPI 编辑、按期修订、本周/本月状态、归档周期。
        那四件事都依赖 `SelfRunPeriod`，而长阶段按设计不产生 Period
        （同一周若同时属于长阶段与叶子阶段，判定会打两遍，而「本周 0/5」
        算谁的就说不清了）。

     🔴 数字**全部现算、零写库**（`GET /stages/<pk>/ledger/`）：
        改口径后它立刻跟着变，不存在「页面上是旧数」。

     🔴 零态一律**查表**，不许自己判 `null` 想当然：
        从前「日均支出为 0」被印成「永不耗尽」—— 把「还没有速度可外推」
        读成了「钱花不完」。0 就是 0，不是 ∞。
-->
<template>
  <div class="stage-ledger" v-loading="loading">
    <!-- ── ⓪ 加载失败：把后端那句话原样摆出来，**不要**退成「还没有长阶段」 ── -->
    <div v-if="!loading && loadError && !stage" class="sl-empty">
      <el-alert
        type="error" :closable="false" show-icon
        title="阶段账本加载失败"
        :description="loadError"
      />
      <div class="sl-empty-cta">
        <el-button type="primary" @click="loadAll">重试</el-button>
        <span class="sl-empty-hint">
          这跟「有没有建阶段」是两件事 —— 阶段列表是取到了的，出错的是账本本身。
        </span>
      </div>
    </div>

    <!-- ── ① 没有长阶段：说清长阶段是什么，并给出口 ──────────────── -->
    <div v-else-if="!loading && !stage" class="sl-empty">
      <el-alert
        type="info" :closable="false" show-icon
        title="还没有长阶段"
        description="长阶段是「一段长路」的容器（例如三年赎回期）：只汇总时间、钱、作品，不跑 KPI —— 周/月的判定留给它下面的小阶段。目前没有任何阶段被建成或标记为长阶段，所以这一页还没有账本。"
      />
      <div class="sl-empty-cta">
        <el-button type="primary" @click="goSetup">去「制定配置」</el-button>
        <span class="sl-empty-hint">
          建成之后这一页不用配置，它按现有账单与时间记录现算 —— 没有需要单独维护的表。
        </span>
      </div>
    </div>

    <template v-else-if="stage && ledger">
      <!-- ── ② 身份卡 ──────────────────────────────────────────── -->
      <el-card shadow="never" class="sl-card">
        <div class="sl-id-row">
          <h2 class="sl-id-name">{{ stage.name }}</h2>
          <el-tag size="small" effect="plain" :type="statusTagType">{{ stage.status_display }}</el-tag>
          <span class="sl-id-range">{{ stage.range_label }}</span>
          <span class="sl-id-days">{{ stage.days_label }}</span>
          <span class="sl-id-spacer" />
          <el-select
            v-if="longStages.length > 1"
            v-model="pickedId" size="small" class="sl-id-pick"
            @change="onPick"
          >
            <el-option v-for="s in longStages" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <el-button size="small" @click="openPrincipal">改本金</el-button>
        </div>
        <div class="sl-id-sub">
          <span>{{ ledger.children.length }} 个小阶段</span>
          <span class="sl-dot">·</span>
          <span>本金 ¥{{ formatAmount(ledger.money.pool.principal, 0) }}</span>
          <span class="sl-dot">·</span>
          <!-- 这句话按阶段形态换：长阶段不判定，带 KPI 的阶段要在别处判 -->
          <span class="sl-muted">
            {{ stage.is_long_stage
              ? '长阶段只汇总，不跑 KPI —— 周/月判定在小阶段里做'
              : '这个阶段带 KPI —— 周/月判定在「本周状态」「本月状态」里' }}
          </span>
        </div>
      </el-card>

      <!-- ── ③ 时间 ────────────────────────────────────────────── -->
      <el-card shadow="never" class="sl-card">
        <template #header>
          <span class="sl-card-title">时间</span>
          <span class="sl-card-src">与周 KPI「成长小时数」、贡献图同一份归因（任务映射表那一列）</span>
        </template>

        <div class="sl-cov">
          <div class="sl-cov-head">
            <span>数据覆盖</span>
            <span class="sl-cov-rate">{{ pct(ledger.time.coverage_rate) }}</span>
          </div>
          <!-- 分子已剔睡眠（分母本来就是「每天可支配小时」）。
               仍可能略超 100%：一天醒着 16h，而可支配按 14h 估 —— 进度条封顶，数字照实 -->
          <el-progress
            :percentage="Math.min(100, Math.round(ledger.time.coverage_rate * 100))"
            :color="ledger.time.coverage_warn ? '#F59E0B' : '#10B981'"
            :stroke-width="12" :show-text="false"
          />
          <div class="sl-cov-sub">
            已记录 {{ ledger.time.covered_hours }}h / 理论 {{ ledger.time.theoretical_hours }}h
            （按每天 {{ ledger.time.theoretical_daily_hours }}h 可支配估算）
            <span v-if="ledger.time.excluded_sleep_hours > 0" class="sl-excluded">
              · 睡眠 {{ ledger.time.excluded_sleep_hours }}h 已剔除（夜间 + 午睡，分母也不含）
            </span>
            <span v-if="ledger.time.fallback_hours > 0" class="sl-fallback">
              · 其中 {{ ledger.time.fallback_hours }}h 没设默认归因，按兜底「成长」计入
              <!-- 带 `unset_attr_only=1`：落地直接筛出没配的那几行。
                   不带的话，几十行里排在最末的两个小任务名根本找不着，
                   「去归好」变成「去自己找」。 -->
              <router-link
                :to="{ path: '/temporal/mapping', query: { unset_attr_only: '1' } }"
                class="sl-link"
              >去归好</router-link>
            </span>
          </div>
        </div>

        <!-- 六类 ⇒ 3 列 × 2 行刚好铺满（4 列会在第二行留两个空位）
             🔴 两位小数：这六格会被加总，「已记录」= 它们之和（后端按此口径算）。
                印 1 位小数时六格加起来是 34.00 而总数写 33.96 —— 页面自己打自己脸。 -->
        <div class="sl-attr-grid">
          <div v-for="(h, k) in ledger.time.hours" :key="k" class="sl-attr-cell">
            <span class="sl-attr-cap" :style="{ color: attrMeta(String(k)).color }">{{ k }}</span>
            <span class="sl-attr-num">{{ Number(h).toFixed(2) }}h</span>
          </div>
        </div>

        <div class="sl-metric-row">
          <div class="sl-metric-cell">
            <span class="sl-metric-cap">成长占比</span>
            <span class="sl-metric-num">{{ pct(ledger.time.toward_ratio) }}</span>
            <span class="sl-metric-hint">成长小时 ÷ 已记录小时</span>
          </div>
          <div class="sl-metric-cell">
            <span class="sl-metric-cap">已记录</span>
            <span class="sl-metric-num">{{ ledger.time.covered_hours }}h</span>
            <span class="sl-metric-hint">六类之和（两者必须相等 —— 不等就是漏数）</span>
          </div>
        </div>
      </el-card>

      <!-- ── ④ 钱 ──────────────────────────────────────────────── -->
      <el-card shadow="never" class="sl-card">
        <template #header>
          <span class="sl-card-title">钱</span>
          <span class="sl-card-src">账单里「赎回归属」标记过的笔 + 被标为「中途注入」的收入，现算</span>
        </template>

        <div class="sl-pool-grid">
          <div class="sl-pool-cell">
            <span class="pc-cap">本金</span>
            <span class="pc-num">¥{{ formatAmount(ledger.money.pool.principal, 0) }}</span>
          </div>
          <div class="sl-pool-cell">
            <span class="pc-cap">中途注入</span>
            <span class="pc-num">¥{{ formatAmount(ledger.money.pool.injected, 0) }}</span>
          </div>
          <div class="sl-pool-cell hl">
            <span class="pc-cap">当前余额</span>
            <span class="pc-num">¥{{ formatAmount(ledger.money.pool.balance, 0) }}</span>
          </div>
          <div class="sl-pool-cell">
            <span class="pc-cap">日均净消耗</span>
            <span class="pc-num">¥{{ formatAmount(ledger.money.pool.avg_daily, 0) }}</span>
          </div>
          <div class="sl-pool-cell">
            <span class="pc-cap">按当前速度撑到</span>
            <!-- 🔴 查表，不猜：算不出来时 backend 给原因码 -->
            <span class="pc-num" :class="{ 'pc-null': !ledger.money.pool.support_until }">
              {{ ledger.money.pool.support_until
                || SUPPORT_ZERO_LABEL[ledger.money.pool.support_zero_reason || '']
                || '—' }}
            </span>
          </div>
        </div>

        <div v-if="ledger.money.pool.support_zero_reason" class="sl-pool-hint">
          {{ SUPPORT_ZERO_HINT[ledger.money.pool.support_zero_reason] || '算不出来。' }}
          <!-- 「去记一笔」只对「还没账」有意义；净流入时不缺账，给这个链接等于叫错人 -->
          <router-link
            v-if="ledger.money.pool.support_zero_reason === 'no_self_expense'"
            to="/wealth/heatmap" class="sl-link"
          >去记一笔</router-link>
        </div>
        <!-- 🔴 一句话由 computed 拼好再渲染：模板里跨行写插值会在「，」后留下一格空白，
             而这是要读的口径说明，不能有毛刺 -->
        <div class="sl-pool-hint sl-muted">{{ avgDailyHint }}</div>

        <div class="sl-tier-list">
          <div v-for="t in ledger.money.tier" :key="t.period_tag" class="sl-tier-item">
            <el-tag size="small" effect="plain" :style="tagStyle(t.period_tag)">
              {{ PERIOD_TAG_META[t.period_tag]?.label || t.period_tag }}
            </el-tag>
            <span class="sl-tier-count">{{ t.count }} 笔</span>
            <span class="sl-tier-total">¥{{ formatAmount(t.total, 0) }}</span>
          </div>
        </div>

        <div class="sl-metric-row">
          <div class="sl-metric-cell">
            <span class="sl-metric-cap">允许日均</span>
            <!-- 与上面「日均净消耗」**同量纲**（每天多少钱），才能直接比大小。
                 2026-11-05 撤掉 ¥/h 那一对：两个分母不同，并排只会读出假结论。 -->
            <span class="sl-metric-num" :class="{ 'sl-null': ledger.money.daily_allowance == null }">
              {{ ledger.money.daily_allowance == null
                ? (ALLOWANCE_ZERO_LABEL[ledger.money.daily_allowance_zero_reason || ''] || '—')
                : `¥${formatAmount(ledger.money.daily_allowance, 0)}/天` }}
            </span>
            <span class="sl-metric-hint">
              剩余 ¥{{ formatAmount(ledger.money.pool.balance, 0) }} ÷ 剩余 {{ ledger.range.remaining_days }} 天
            </span>
          </div>
          <div class="sl-metric-cell">
            <span class="sl-metric-cap">预算占用</span>
            <span class="sl-metric-num" :class="{ 'sl-over': (ledger.money.daily_use_rate ?? 0) > 1 }">
              {{ ledger.money.daily_use_rate == null
                ? (USE_RATE_ZERO_LABEL[ledger.money.daily_use_rate_zero_reason || ''] || '—')
                : pct(ledger.money.daily_use_rate, 0) }}
            </span>
            <span class="sl-metric-hint">
              日均 ¥{{ formatAmount(ledger.money.pool.avg_daily, 0) }} ÷ 允许日均；过 100% 就撑不到终点
            </span>
          </div>
        </div>
      </el-card>

      <!-- ── ⑤ 作品 ────────────────────────────────────────────── -->
      <el-card shadow="never" class="sl-card">
        <div class="sl-works-row">
          <span class="sl-works-num">{{ ledger.works.count }}</span>
          <span class="sl-works-cap">件作品成形于这段时间</span>
          <span class="sl-works-hint">按「合成那件作品的那一刻」算，不是那件事发生的那天</span>
          <!-- 🔴 数字要能自己核对：件数是结论，明细是它的依据。
               从前只有一个孤零零的 `2`，它错了（取数区间、跨零点、算错）看不出来。
               ⚠️ 0 件**不给**按钮 —— 弹一个空窗比没有按钮更糟（像是坏了）。 -->
          <el-button
            v-if="ledger.works.count > 0"
            class="sl-works-btn" size="small" plain
            @click="worksVisible = true"
          >看是哪几件</el-button>
        </div>
      </el-card>

      <!-- ── ⑥ 小阶段 ──────────────────────────────────────────── -->
      <el-card shadow="never" class="sl-card">
        <template #header>
          <div class="sl-card-head">
            <div class="sl-card-head-text">
              <span class="sl-card-title">小阶段（{{ ledger.children.length }}）</span>
              <span class="sl-card-src">达标率是小阶段自己的判定；长阶段只汇总，不判定</span>
            </div>
            <!-- 入口就放在它管的那张清单上：三年切成几段，是在这里一段段开的 -->
            <el-button
              v-if="stage.status !== 'closed'"
              size="small" type="primary" plain @click="addChild"
            >
              + 开下一个小阶段
            </el-button>
            <!-- 已收尾的长阶段不再给入口，但要说明为什么没有按钮 -->
            <span v-else class="sl-card-src">这段路已收尾 —— 不能再往下挂新小阶段</span>
          </div>
        </template>

        <!-- 同一 parent 下只能有一个 open（后端也判）—— 先说清楚，别等人填完一屏才被 400 挡住 -->
        <div v-if="openChild" class="sl-children-note sl-warn">
          这个长阶段下已有「{{ openChild.name }}」在跑 —— 先收尾它，才能开下一段。
          <router-link to="/selfrun/summary" class="sl-link">去收尾</router-link>
        </div>

        <StageChildrenList :children="ledger.children" :open-stage-id="openLeafId" />
        <div v-if="ledger.children.length" class="sl-children-note">
          只有正在跑的那个能进详情 —— 周/月/总结三页讲的是「当前阶段」。
          已收尾的小阶段不单独开页，它的每一期结论在
          <router-link to="/selfrun/review" class="sl-link">历史复盘</router-link> 里。
        </div>
      </el-card>
    </template>

    <!-- ── 作品明细弹窗 ────────────────────────────────────────── -->
    <el-dialog
      v-model="worksVisible" append-to-body
      :title="`这段时间成形的 ${ledger?.works.count ?? 0} 件`" width="620px"
    >
      <!-- 🔴 先交代口径 —— 用户就是带着「为什么算在这段里」的疑问点开它的。
           每条给的是**成形时刻**，与作品里那件事发生的日期无关。 -->
      <div class="sl-dlg-hint sl-works-dlg-lead">
        每条后面是「合成那件作品的那一刻」—— 你把它收口成作品的时刻，
        不是里面那件事发生在哪天。所以一件 11-05 的作品，可能装的是 10-20 的事。
      </div>
      <ul class="sl-work-list">
        <li v-for="w in ledger?.works.items ?? []" :key="w.id" class="sl-work-item">
          <div class="sl-work-head">
            <span class="sl-work-name">{{ w.name }}</span>
            <el-tag size="small" effect="plain">{{ w.kind }}</el-tag>
            <el-tag size="small" effect="plain" type="info">{{ w.status }}</el-tag>
          </div>
          <div v-if="w.summary" class="sl-work-sum">{{ w.summary }}</div>
          <div class="sl-work-meta">
            <span>{{ formatDateTime(w.created_at) }} 成形</span>
            <span v-if="w.channel">发到：{{ w.channel }}</span>
          </div>
        </li>
      </ul>
      <!-- 🔴 截断必须说出来：只列了前 N 件却不说，那几条就会被当成全集 -->
      <div v-if="worksTruncatedLeft > 0" class="sl-dlg-hint">
        这里只列了最近 {{ ledger?.works.items.length }} 件 ——
        还有 {{ worksTruncatedLeft }} 件没列出来，去作品页看全部。
      </div>
      <template #footer>
        <el-button @click="worksVisible = false">关闭</el-button>
        <el-button type="primary" plain @click="goWorks">去作品页</el-button>
      </template>
    </el-dialog>

    <!-- ── 本金弹窗 ────────────────────────────────────────────── -->
    <el-dialog v-model="principalVisible" title="这段路带多少钱（本金）" width="420px">
      <el-input-number
        v-model="principalDraft" :min="0" :step="10000" :precision="2"
        controls-position="right" style="width: 100%"
      />
      <div class="sl-dlg-hint">
        本金是输入，不是算出来的：余额 = 本金 + 中途注入 − 为自己净消耗。
        改它只改这条公式的起点，不动任何历史账单。
      </div>
      <template #footer>
        <el-button @click="principalVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePrincipal">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as api from '../api/selfrunApi'
import { useSelfRunStore } from '../stores/selfrunStore'
import StageChildrenList from '../components/StageChildrenList.vue'
import { attrMeta } from '@/shared/config/attributionMeta'
import { PERIOD_TAG_META } from '@/modules/wealth/types/wealthTypes'
import { formatAmount } from '@/shared/utils/format'
import { formatDateTime } from '@/shared/utils/datetime'
import { apiErrorText } from '@/shared/utils/apiError'
import {
  ALLOWANCE_ZERO_LABEL, SUPPORT_ZERO_HINT, SUPPORT_ZERO_LABEL, USE_RATE_ZERO_LABEL,
} from '../types/selfrunTypes'
import type { SelfRunStage, StageLedger } from '../types/selfrunTypes'

const route = useRoute()
const router = useRouter()
const store = useSelfRunStore()

const loading = ref(false)
const stage = ref<SelfRunStage | null>(null)
const ledger = ref<StageLedger | null>(null)
/**
 * 加载失败的原因（后端 `detail` 原话）；`null` = 这次没失败。
 *
 * 🔴 必须有这个状态：`stage` 为 `null` 有两种完全相反的含义 ——
 *    「真的没有长阶段」和「有，但没取到」。只留 `stage`，后者会被渲染成
 *    「还没有长阶段」，而那条提示还劝你去「制定配置」建一个已经存在的阶段。
 */
const loadError = ref<string | null>(null)
/** 所有**长阶段**（顶级 + 零 KPI）。多于一个时给下拉切换（人生不止一段长路） */
const longStages = ref<SelfRunStage[]>([])
const pickedId = ref<number | null>(null)

const principalVisible = ref(false)
const principalDraft = ref<number>(0)
const saving = ref(false)
/** 作品明细弹窗（点「看是哪几件」开） */
const worksVisible = ref(false)

/** 明细被截断时还有几件没列 —— `count` 与 `items` 同源，差额就是被上限截掉的。
 *  ⚠️ 用 `items.length` 而不是后端 `limit`：万一以后上限变了、或明细过滤了某条，
 *     `count - limit` 会算出 0 或负数，而那正是「还有几件」最不该出错的地方。 */
const worksTruncatedLeft = computed(() => {
  const w = ledger.value?.works
  if (!w || !w.truncated) return 0
  return Math.max(w.count - w.items.length, 0)
})

/** 去作品页看全部（/works 是作品唯一的列表页；这里只是这段区间的切片）。 */
function goWorks() {
  worksVisible.value = false
  router.push('/works')
}

/** 当前真正在跑的那个阶段（叶子）。子阶段列表据此决定给不给「进详情」 */
const openLeafId = computed(() => store.stage?.id ?? null)

/** 这个长阶段下正在跑的小阶段（有 ⇒ 开不了第二段，先把这条路走完/收尾） */
const openChild = computed(() =>
  ledger.value?.children.find(c => c.id === openLeafId.value) ?? null,
)

const statusTagType = computed(() => {
  const s = stage.value
  if (!s) return 'info'
  if (s.status === 'paused') return 'warning'
  if (s.status === 'active') return s.elapsed_days > 0 ? 'success' : 'info'
  return 'info'
})

function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

/** 日均那行的口径说明：分母是 `min(实际天数, 30)`，数值不再被稀释；
 *  但样本不足 30 天时速度可能还没经历月末大额。判据（够不够 30 天）由后端
 *  `avg_daily_sample_thin` 给，前端**不自己比 30** —— 否则又是第二份阈值。 */
const avgDailyHint = computed(() => {
  const m = ledger.value?.money
  if (!m) return ''
  if (m.avg_daily_sample_days <= 0) {
    return '日均按本阶段已走天数实算 —— 阶段还没开始，没有可外推的速度。'
  }
  if (!m.avg_daily_sample_thin) {
    return '日均按最近 30 天滚动，样本已满 30 天。'
  }
  const days = m.avg_daily_sample_days
  return `日均按本阶段已走的 ${days} 天实算 —— 样本不足 30 天，`
    + '还没经历月末大额，所以「撑到哪天」仍可能偏乐观。'
})

function tagStyle(tag: string) {
  const m = PERIOD_TAG_META[tag] || PERIOD_TAG_META.unmarked
  return { color: m.color, borderColor: m.color, backgroundColor: m.bg }
}

function goSetup() {
  router.push({ name: 'selfrun-setup' })
}

/**
 * 「+ 开下一个小阶段」：带 `?parent=` 去向导，形态与上级阶段预先填好。
 *
 * 🔴 必须带 id：向导不知道你刚从哪一段路进来，不带就只能从三个形态里重选一遍
 *    （而人多半会选错成「独立阶段」，于是新段跑到长阶段之外）。
 */
function addChild() {
  const id = stage.value?.id
  if (!id) return
  router.push({ name: 'selfrun-setup', query: { parent: String(id) } })
}

/**
 * 该给哪一段路出账本。
 *
 * 🔴 路由带 `id` 就用它（下拉切换、或别处深链过来）；不带就取**正在跑的那个长阶段**。
 *    `:id?` 是可选的，因为页头那个下拉入口拿不到 id —— 它只知道「去账本」。
 * ⚠️ 顶层同一时间只允许一个 open 阶段（模型层保证），所以「正在跑的」唯一。
 *    万一真有两个，用 `find` 取第一个也**不会**让两个页面互相覆盖。
 */
function resolveTargetId(): number | null {
  const q = route.params.id
  if (q) {
    const n = Number(q)
    return Number.isFinite(n) ? n : null
  }
  const open = longStages.value.find(s => s.status === 'active' || s.status === 'paused')
  return (open ?? longStages.value[0])?.id ?? null
}

async function loadOne(id: number) {
  const res = await api.getStageLedger(id)
  stage.value = res.data.stage
  ledger.value = res.data.ledger
  pickedId.value = res.data.stage.id
}

async function loadAll() {
  loading.value = true
  loadError.value = null
  try {
    const list = await api.listStages()
    longStages.value = list.data.filter(s => s.is_long_stage)
    const target = resolveTargetId()
    if (!target) {
      stage.value = null
      ledger.value = null
      return
    }
    await loadOne(target)
  } catch (e) {
    // 🔴 不清空已有内容：接口偶发失败时把页面打空，看着像「这段路没有数据」
    // 🔴 也**不能只说「失败」**：503 的 `detail` 就是那句「请先执行数据库迁移」，
    //    它是唯一能让用户知道该做什么的线索。`apiErrorText` 对 5xx 一律给兜底文案，
    //    会把这句话盖掉，所以这里先取 `detail`，取不到才回落到它。
    const detail = (e as { response?: { data?: { detail?: unknown } } })
      ?.response?.data?.detail
    loadError.value = typeof detail === 'string' && detail
      ? detail
      : apiErrorText(e, '加载阶段账本失败')
    ElMessage.error('加载阶段账本失败')
  } finally {
    loading.value = false
  }
}

/** 下拉切换 = 改路由（**不另存一份选中态**），再由 watch 去拉数 */
function onPick(id: number) {
  router.replace({ name: 'selfrun-stage', params: { id: String(id) } })
}

watch(
  () => route.params.id,
  (v) => {
    // ⚠️ 只有**数字**才去拉：地址栏被手敲成 `/selfrun/stage/abc` 时，
    //    不挡这一下就是一次必然 404 的请求 + 一条红色 toast（页面本身没错）。
    const n = Number(v)
    if (v && Number.isFinite(n)) loadOne(n)
  },
)

function openPrincipal() {
  principalDraft.value = ledger.value?.money.pool.principal ?? 0
  principalVisible.value = true
}

async function savePrincipal() {
  if (!stage.value) return
  saving.value = true
  try {
    const res = await api.patchLedgerConfig(stage.value.id, {
      pool_principal: Number(principalDraft.value) || 0,
    })
    stage.value = res.data.stage
    ledger.value = res.data.ledger
    principalVisible.value = false
    ElMessage.success('本金已更新 —— 余额与「撑到哪天」跟着重算')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadAll)

/** 页头那个「刷新」转到这里 —— 两处刷新按钮各刷各的，必然有一半是旧的 */
defineExpose({ refresh: loadAll })
</script>

<style scoped>
.stage-ledger { display: flex; flex-direction: column; gap: 14px; }
.sl-card { border-radius: 10px; }
.sl-muted { color: var(--el-text-color-secondary); }
.sl-link { color: var(--el-color-primary); text-decoration: none; }
.sl-link:hover { text-decoration: underline; }

/* ── 空态 ─────────────────────────────────────────────────── */
.sl-empty { display: flex; flex-direction: column; gap: 12px; }
.sl-empty-cta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sl-empty-hint { font-size: 12px; color: var(--el-text-color-secondary); }

/* ── 身份卡 ───────────────────────────────────────────────── */
.sl-id-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sl-id-name { margin: 0; font-size: 20px; font-weight: 600; }
.sl-id-range { font-size: 13px; color: var(--el-text-color-regular); }
.sl-id-days { font-size: 13px; color: var(--el-text-color-secondary); }
.sl-id-spacer { flex: 1; }
.sl-id-pick { width: 200px; }
.sl-id-sub {
  margin-top: 8px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  font-size: 13px; color: var(--el-text-color-regular);
}
.sl-dot { color: var(--el-text-color-placeholder); }

/* ── 卡头：标题 + 出处角标 ────────────────────────────────── */
.sl-card-title { font-weight: 600; }
.sl-card-src { margin-left: 10px; font-size: 12px; color: var(--el-text-color-secondary); }
.sl-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.sl-card-head-text { min-width: 0; }

/* ── 时间 ─────────────────────────────────────────────────── */
.sl-cov { margin-bottom: 14px; }
.sl-cov-head { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px; }
.sl-cov-rate { font-weight: 700; }
.sl-cov-sub { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; line-height: 1.7; }
.sl-fallback { color: var(--el-color-warning); }
/* 剔睡眠是「口径说明」，不是告警 —— 用次级色，别抢了兜底归因那行橙色 */
.sl-excluded { color: var(--el-text-color-secondary); }
.sl-attr-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 14px; }
.sl-attr-cell {
  display: flex; flex-direction: column; gap: 4px;
  padding: 10px; background: var(--el-fill-color-light); border-radius: 8px;
}
.sl-attr-cap { font-weight: 600; }
.sl-attr-num { font-size: 16px; font-weight: 700; }

/* ── 钱 ───────────────────────────────────────────────────── */
.sl-pool-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.sl-pool-cell {
  display: flex; flex-direction: column; gap: 4px;
  padding: 10px; background: var(--el-fill-color-light); border-radius: 8px;
}
.sl-pool-cell.hl { background: var(--el-color-primary-light-9); }
.pc-cap { font-size: 12px; color: var(--el-text-color-secondary); }
.pc-num { font-size: 16px; font-weight: 700; }
.pc-null { color: var(--el-text-color-placeholder); font-weight: 600; }
.sl-pool-hint { margin-top: 8px; font-size: 12px; line-height: 1.7; }
.sl-tier-list { display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0; }
.sl-tier-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; background: var(--el-fill-color-light); border-radius: 8px;
}
.sl-tier-count { font-size: 13px; }
.sl-tier-total { font-weight: 600; }

/* ── 通用指标行 ───────────────────────────────────────────── */
.sl-metric-row { display: flex; gap: 12px; flex-wrap: wrap; }
.sl-metric-cell {
  flex: 1 1 200px; display: flex; flex-direction: column; gap: 2px;
  padding: 10px; background: var(--el-fill-color-light); border-radius: 8px;
}
.sl-metric-cap { font-size: 12px; color: var(--el-text-color-secondary); }
.sl-metric-num { font-size: 18px; font-weight: 700; }
.sl-metric-hint { font-size: 12px; color: var(--el-text-color-secondary); }
/* 「算不出来」用占位色，别跟真数字同色 —— 否则「未设本金」看着像个¥值 */
.sl-null { color: var(--el-text-color-placeholder); font-weight: 600; }
/* 预算占用过 100% ⇒ 按当前速度撑不到终点，这是唯一需要抢眼的判据 */
.sl-over { color: var(--el-color-danger); }

/* ── 作品 ─────────────────────────────────────────────────── */
.sl-works-row { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sl-works-num { font-size: 24px; font-weight: 700; }
.sl-works-cap { font-size: 14px; }
.sl-works-hint { font-size: 12px; color: var(--el-text-color-secondary); }
/* 按钮推到最右（`margin-left:auto` 而不是给整行加 justify-content —— 左边那三样
   本来就是并排读的一句话，被撑开会读断） */
.sl-works-btn { margin-left: auto; }

/* ── 作品明细弹窗 ─────────────────────────────────────────── */
.sl-works-dlg-lead { margin-top: 0; margin-bottom: 10px; }
.sl-work-list { margin: 0; padding: 0; list-style: none; max-height: 52vh; overflow-y: auto; }
.sl-work-item { padding: 10px 2px; border-bottom: 1px solid var(--el-border-color-lighter); }
.sl-work-item:last-child { border-bottom: none; }
.sl-work-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sl-work-name { font-size: 14px; font-weight: 600; }
.sl-work-sum { margin-top: 4px; font-size: 12px; color: var(--el-text-color-regular); line-height: 1.7; white-space: pre-line; }
.sl-work-meta {
  margin-top: 4px; font-size: 12px; color: var(--el-text-color-secondary);
  display: flex; gap: 12px; flex-wrap: wrap;
}

/* ── 小阶段说明 ───────────────────────────────────────────── */
.sl-children-note { margin-top: 10px; font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.7; }
.sl-warn {
  margin-top: 0; margin-bottom: 10px; color: var(--el-color-warning);
  padding: 6px 10px; border-radius: 6px; background: var(--el-color-warning-light-9);
}

/* ── 本金弹窗 ─────────────────────────────────────────────── */
.sl-dlg-hint { margin-top: 10px; font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.7; }
</style>
