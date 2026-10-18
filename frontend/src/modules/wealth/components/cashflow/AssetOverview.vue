<template>
  <div class="asset-overview">
    <div v-if="!overview" class="asset-overview__empty">暂无资产数据</div>
    <template v-else>
      <div class="asset-overview__chart">
        <div ref="chartRef" class="asset-overview__canvas" />
      </div>
      <div class="asset-overview__summary">
        <div class="asset-overview__total">
          <span class="asset-overview__total-label">净资产</span>
          <span class="asset-overview__total-value">¥{{ fmt(overview.summary.net_worth) }}</span>
        </div>
        <div class="asset-overview__items">
          <div class="asset-overview__item" v-for="item in assetItems" :key="item.key">
            <el-tooltip v-if="item.hint" :content="item.hint" placement="top">
              <span class="asset-overview__item-label is-hinted">{{ item.label }}</span>
            </el-tooltip>
            <span v-else class="asset-overview__item-label">{{ item.label }}</span>
            <span class="asset-overview__item-value">¥{{ fmt(item.value) }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { formatAmount } from '@/shared/utils/format'
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { CashFlowOverview } from '../../types/wealthTypes'

echarts.use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  overview: CashFlowOverview | null
  loading?: boolean
}>()

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

const assetItems = computed(() => {
  if (!props.overview) return []
  const s = props.overview.summary
  return [
    // 🔴 「金融资产」= 全部非自用资产合计（**含**应收借出）——
    // 下面四行是它的拆解，不是并列的另外四项，别把它们和金融资产相加。
    //
    // 🔴 拆解必须**加得回去**（v3.62.28 —— 用户报「账面数据对不上」）：
    //    金融资产 = 流动资金 + 非流动资金 + 公积金 + 应收借出
    // 改前只有「流动资金」一行，`T+0 可取 = 否` 的余额
    // （实测三张储蓄卡 206,752.88）不属于任何一行 ⇒ 拆项之和比金融资产
    // 少一截，而两边各自都看着正常。四个桶由后端 rollup_items 按定义
    // 互斥划分，前端只展示、不判断、不折算。
    {
      key: 'financial_assets',
      label: '金融资产',
      value: s.financial_assets,
      hint: '全部非自用资产合计，已包含应收借出',
    },
    {
      key: 'flow_total',
      label: '流动资金',
      value: s.flow_total,
      hint: 'T+0 可取用的钱（应急金按这个算）；取不出来的在下一行',
    },
    {
      key: 'non_liquid',
      label: '非流动资金',
      value: s.non_liquid,
      hint: '计入资产但 T+0 取不出来的余额：定期、理财、被锁定的存款等。'
        + '某笔钱算不算，由科目主数据里的「T+0 可取」开关决定',
    },
    { key: 'accumulationfund', label: '公积金', value: props.overview.accounts.accumulationfund },
    { key: 'lend', label: '应收借出', value: s.lend, hint: '上面「金融资产」的其中一部分' },
    { key: 'borrow', label: '负债', value: s.borrow },
  ]
})

function fmt(v: number): string {
  return formatAmount(v)
}

function initChart() {
  if (!chartRef.value || !props.overview) return
  chart = echarts.init(chartRef.value)
  updateChart()
}

function updateChart() {
  if (!chart || !props.overview) return
  const a = props.overview.accounts
  const data = [
    { name: '支付宝', value: a.zplay },
    { name: '微信', value: a.wechat },
    { name: '现金', value: a.cash },
    { name: '建行', value: a.jianbank },
    { name: '工行', value: a.gongbank },
    { name: '中国银行', value: a.zhongbank },
    { name: '农信社', value: a.nongbank },
    { name: '公积金', value: a.accumulationfund },
  ].filter(d => d.value > 0)

  chart.setOption({
    tooltip: {
      trigger: 'item',
      valueFormatter: (v: number) => '¥' + v.toLocaleString(),
    },
    series: [{
      type: 'pie',
      radius: ['30%', '60%'],
      center: ['50%', '50%'],
      data,
      label: {
        show: true,
        formatter: '{b}\n{d}%',
        fontSize: 11,
      },
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' },
      },
    }],
  })
}

onMounted(() => { nextTick(initChart) })
watch(() => props.overview, () => {
  nextTick(() => {
    if (chart) updateChart()
    else initChart()
  })
}, { deep: true })
</script>

<style scoped>
.asset-overview {
  display: flex;
  gap: 16px;
}
.asset-overview__chart {
  flex: 1;
}
.asset-overview__canvas {
  width: 100%;
  height: 260px;
}
.asset-overview__summary {
  width: 200px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.asset-overview__total {
  text-align: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
}
.asset-overview__total-label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.asset-overview__total-value {
  display: block;
  font-size: 22px;
  font-weight: 700;
  color: #1890ff;
}
.asset-overview__items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.asset-overview__item {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}
.asset-overview__item-label.is-hinted {
  border-bottom: 1px dashed var(--el-border-color);
  cursor: help;
}
.asset-overview__item-label {
  color: var(--el-text-color-secondary);
}
.asset-overview__item-value {
  font-weight: 600;
}
.asset-overview__empty {
  padding: 40px;
  text-align: center;
  color: var(--el-text-color-placeholder);
}
@media (max-width: 768px) {
  .asset-overview { flex-direction: column; }
  .asset-overview__summary { width: 100%; }
}
</style>
