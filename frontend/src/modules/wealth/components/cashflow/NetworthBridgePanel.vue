<template>
  <div class="bridge">
    <div class="bridge__header">
      <span class="bridge__title">净值变动归因</span>
      <!-- 🔴 v3.64.1：这两个词原来是**一排灰字**（`资产表 ↔ 账本`）—— 看着像能点，
           其实既不是链接也没有事件，点了一点反应都没有。
           现在做成按钮，点了真去对应的地方：
             · 账本  → 月度日历（账单明细在那里）
             · 资产表 → **本页**的「资产快照（按科目）」区块（滚动定位）
           ⚠️ 资产表**刻意不做路由跳转** —— 它就在这一页；`push` 到当前页
              只会让人以为「按钮坏了」（项目铁律：点了没反应 = 头号问题）。
           ⚠️ 落点由父级决定（`emit`），本组件不认识路由器 —— 它被挂到别的页面也能用。 -->
      <div class="bridge__links">
        <el-button link type="primary" size="small" title="定位到本页的「资产快照（按科目）」" @click="emit('go-assets')">
          资产表
        </el-button>
        <span class="bridge__link-sep">↔</span>
        <el-button link type="primary" size="small" title="去月度日历看账单明细" @click="emit('go-ledger')">
          账本
        </el-button>
      </div>
      <InfoTip :width="420" title="这个卡片在算什么">
        <p>净资产的变化 = 账本净流量 + 未解释差额 − Δ负债。</p>
        <p>「未解释差额」只算<strong>资产端</strong>：还债本身不改变净资产，
          所以 Δ负债 单独一行列出，不混进差额里。</p>
        <p>窗口 = (上期盘点日, 本期盘点日]。账单精确到秒、盘点只到日，
          所以边界日的几十元差额属于噪声。</p>
      </InfoTip>
    </div>

    <div v-if="loading" class="bridge__empty">加载中…</div>
    <div v-else-if="!latest" class="bridge__empty">
      还没有两期盘点，暂时算不出归因。
    </div>

    <template v-else>
      <!-- 一句话结论：只说事实，不给评价 -->
      <div class="bridge__summary" :class="`is-${latest.level}`">
        {{ summaryText }}
      </div>

      <!-- 最新一期的拆解 -->
      <div class="bridge__rows">
        <div v-for="line in lines" :key="line.label" class="bridge__row">
          <span class="bridge__row-label">{{ line.label }}</span>
          <span class="bridge__row-value" :class="line.tone">{{ line.value }}</span>
        </div>
      </div>

      <!-- 算不出窗口时，必须说清为什么，而不是给 0 -->
      <div v-if="latest.window_reason !== 'ok'" class="bridge__note">
        {{ windowReasonText }}
      </div>
      <div v-else-if="latest.level === 'material'" class="bridge__note is-warn">
        {{ sideHint }}
      </div>

      <!-- 历史：按需展开，不占首屏 -->
      <div v-if="history.length" class="bridge__history">
        <div class="bridge__history-head" @click="expanded = !expanded">
          <span>近 {{ history.length }} 期</span>
          <span class="bridge__toggle">{{ expanded ? '收起' : '展开' }}</span>
        </div>
        <table v-if="expanded" class="bridge__table">
          <thead>
            <tr>
              <th>区间</th>
              <th class="num">账本净流量</th>
              <th class="num">未解释</th>
              <th class="num">Δ负债</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in history" :key="p.to_yearmon">
              <td>{{ p.from_yearmon }}→{{ p.to_yearmon }}</td>
              <td class="num">{{ amount(p.flow_net) }}</td>
              <td class="num" :class="{ 'is-warn': p.level === 'material' }">
                {{ amount(p.unexplained) }}
              </td>
              <td class="num">{{ amount(p.borrow_change) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 数据本身的问题：盘点断档 / 太久没盘 -->
      <div v-if="dataNotes.length" class="bridge__notes">
        <div v-for="note in dataNotes" :key="note" class="bridge__note is-muted">{{ note }}</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getNetworthBridge } from '../../api/wealthApi'
import { formatSignedAmount } from '@/shared/utils/format'
import InfoTip from '@/shared/components/InfoTip.vue'
import type { NetworthBridge, NetworthBridgePeriod } from '../../types/wealthTypes'

const loading = ref(true)
const data = ref<NetworthBridge | null>(null)
const expanded = ref(false)

/**
 * 「资产表 / 账本」两个按钮点了往哪走，**由父级决定**（本组件不认识 router）。
 * 这样它被挂到别的页面时，父级换一处落点即可，不用改这里。
 */
const emit = defineEmits<{ 'go-assets': []; 'go-ledger': [] }>()

/**
 * 联动：父级刷新时由父级调 `reload()`。
 * 🔴 自带 `onMounted` 取数 —— 卡片被单独挂到任何页面都能活（§118.4）。
 */
async function reload() {
  loading.value = true
  try {
    const resp = await getNetworthBridge({ limit: 24 })
    data.value = resp.data as NetworthBridge
  } catch (e) {
    console.error('获取净值归因失败:', e)
    data.value = null
  } finally {
    loading.value = false
  }
}

onMounted(reload)
defineExpose({ reload })

const latest = computed<NetworthBridgePeriod | null>(() => data.value?.latest ?? null)
const threshold = computed(() => data.value?.thresholds.material_amount ?? 0)

/** 金额唯一入口：空值 `—`，不写 `¥—`；「确实当 0」在调用点写 `?? 0` */
function amount(v: number | null | undefined): string {
  return formatSignedAmount(v, 2)
}

const summaryText = computed(() => {
  const p = latest.value
  if (!p) return ''
  if (p.window_reason !== 'ok') return '这一期的区间划不出来。'
  const head = `${p.from_yearmon} → ${p.to_yearmon}，净资产${p.net_worth_change >= 0 ? '增加' : '减少'} ${amount(Math.abs(p.net_worth_change))}`
  if (p.level === 'no_window') return `${head}。`
  if (p.level !== 'material') return `${head}；账本和盘点对得上。`
  return `${head}；其中 ${amount(p.unexplained)} 对不上账本。`
})

const lines = computed(() => {
  const p = latest.value
  if (!p) return []
  return [
    {
      label: 'Δ总资产',
      value: amount(p.assets_change),
      tone: p.assets_change >= 0 ? 'is-up' : 'is-down',
    },
    {
      label: '账本净流量',
      value: p.flow_net === null ? '—' : amount(p.flow_net),
      tone: '',
    },
    {
      label: '未解释差额',
      value: p.unexplained === null ? '—' : amount(p.unexplained),
      tone: p.level === 'material' ? 'is-warn' : '',
    },
    {
      // 单列一行：还债不改变净资产，混进差额会把「正常还贷」误报成漏记
      label: 'Δ负债',
      value: amount(p.borrow_change),
      tone: '',
    },
  ]
})

const sideHint = computed(() => {
  const p = latest.value
  if (!p) return ''
  if (p.unexplained_side === 'more_than_recorded') {
    return `钱比账本多出 ${amount(p.unexplained)}：可能有收入没记，或某个账户余额抄少了。`
  }
  if (p.unexplained_side === 'less_than_recorded') {
    return `钱比账本少 ${amount(Math.abs(p.unexplained ?? 0))}：可能有支出没记，或某个账户余额抄多了。`
  }
  return ''
})

const windowReasonText = computed(() => {
  const reason = latest.value?.window_reason
  if (reason === 'undated') return '这一期（或上一期）盘点没填日期，算不出收支区间。'
  if (reason === 'invalid_span') return '相邻两期盘点日期相同或倒挂，区间无效。'
  return ''
})

/** 历史只展示能算出的期次；按年月倒序，最近的在最上面 */
const history = computed(() =>
  (data.value?.periods ?? [])
    .filter((p) => p.window_reason === 'ok')
    .slice()
    .reverse(),
)

const dataNotes = computed(() => {
  const s = data.value?.summary
  if (!s) return []
  const notes: string[] = []
  if (s.missing_count) {
    notes.push(`盘点断了 ${s.missing_count} 个月：${s.missing_months.join('、')}`)
  }
  if (s.stale_days !== null && s.stale_days > 31) {
    notes.push(`距上次盘点已 ${s.stale_days} 天，最新一期可能不代表现在`)
  }
  if (threshold.value) {
    notes.push(`差额超过 ${formatSignedAmount(threshold.value, 0)} 才提示`)
  }
  return notes
})
</script>

<style scoped>
.bridge {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.bridge__header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bridge__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
/* 原来这里是「资产表 ↔ 账本」一排灰字，现在换成两个按钮 + 中间那个关系符。
   ⚠️ 分隔符单独一个节点：夹在两个按钮中间才读得出「这两处要对账」，
      塞进按钮文案里会让「资产表」看起来像一个词组。 */
.bridge__links {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.bridge__link-sep {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.bridge__empty {
  padding: 18px 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.bridge__summary {
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}
.bridge__summary.is-material {
  color: var(--el-color-warning-dark-2);
}
.bridge__rows {
  display: flex;
  flex-direction: column;
}
.bridge__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}
.bridge__row:last-child {
  border-bottom: none;
}
.bridge__row-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.bridge__row-value {
  font-size: 14px;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}
.bridge__row-value.is-up {
  color: var(--el-color-danger);
}
.bridge__row-value.is-down {
  color: var(--el-color-success);
}
.bridge__row-value.is-warn {
  color: var(--el-color-warning-dark-2);
  font-weight: 600;
}
.bridge__note {
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.bridge__note.is-warn {
  color: var(--el-color-warning-dark-2);
}
.bridge__note.is-muted {
  color: var(--el-text-color-placeholder);
}
.bridge__notes {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.bridge__history {
  margin-top: 2px;
}
.bridge__history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  user-select: none;
}
.bridge__toggle {
  color: var(--el-color-primary);
}
.bridge__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.bridge__table th,
.bridge__table td {
  padding: 4px 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  text-align: left;
}
.bridge__table .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.bridge__table td.is-warn {
  color: var(--el-color-warning-dark-2);
}
</style>
