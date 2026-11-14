<template>
  <div class="plan-map">
    <!-- 地图 -->
    <div class="map-box">
      <div ref="chartRef" class="chart" />
      <div v-if="plan.stops.length === 0" class="map-empty">
        这条路线还没有站，先把城市排上再看地图
      </div>
      <div v-else-if="locatedStops.length === 0" class="map-empty">
        没有一站能定位到坐标 —— 城市名改个常见写法（如「泉州」）试试
      </div>
      <div v-if="brokenText" class="map-warn">{{ brokenText }}</div>
      <div class="map-legend">
        <span class="dot" /> 站点（圈内数字 = 站序）
        <span class="line" /> 行程顺序
      </div>
    </div>

    <!-- 右侧：站序 + 选中站的明细 -->
    <aside class="stop-panel">
      <div class="panel-head">
        <span class="panel-title">📍 {{ plan.stops.length }} 站 · ¥{{ fmt(plan.stops_total) }}</span>
        <span class="panel-note">
          不含路上 ¥{{ fmt(plan.transfer_total) }}<template v-if="plan.stops.length > 1"> · 点圆点或下面一行切换</template>
        </span>
      </div>

      <!-- 站序即路线：点一行等于点地图上的那个点 -->
      <ul class="stop-rows">
        <li
          v-for="(stop, i) in plan.stops"
          :key="stop.id"
          class="stop-row"
          :class="{ active: stop.id === activeId }"
          @click="select(stop.id)"
        >
          <span class="row-order">{{ i + 1 }}</span>
          <span class="row-city">
            {{ stop.city_input }}
            <el-tooltip v-if="!stop.located" content="城市名没在坐标表里找到，地图上不画（不猜坐标）" placement="top">
              <span class="row-unlocated">未定位</span>
            </el-tooltip>
          </span>
          <span class="row-days">{{ daysLabel(stop.days) }}</span>
          <span class="row-cost">¥{{ fmt(stop.subtotal) }}</span>
        </li>
      </ul>

      <!-- 选中站明细：只读（勾完成仍走清单，那里有「打卡并记录」的完整流程） -->
      <div v-if="activeStop" class="detail">
        <div class="detail-head">
          <span class="detail-city">{{ activeStop.city_input }}</span>
          <span class="detail-meta">
            {{ arriveLabel(activeStop.arrive_date) }} · {{ daysLabel(activeStop.days) }}
          </span>
        </div>
        <div class="detail-nums">
          <span class="detail-cost">¥{{ fmt(activeStop.subtotal) }}</span>
          <span v-for="c in countChips(activeStop)" :key="c.key" class="chip">{{ c.icon }}{{ c.n }}</span>
        </div>
        <div v-if="activeItems.length" class="item-list">
          <div v-for="item in activeItems" :key="item.id" class="item" :class="{ done: item.is_completed }">
            <span class="item-icon">{{ itemIcon(item.item_type) }}</span>
            <span class="item-name">{{ item.name }}</span>
            <span class="item-cost">¥{{ fmt(item.estimate_cost) }}</span>
          </div>
        </div>
        <div v-else class="item-empty">这一站还没排条目</div>
        <p class="detail-hint">勾完成、加条目请在清单里做，地图只负责「这一站要花多少、都有什么」。</p>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { formatAmount } from '@/shared/utils/format'
import { registerChinaProvinceMap } from '../../utils/chinaProvinceMap'
import { fitRouteView, type LngLat } from '../../utils/routeView'
import { arriveLabel, countChips, daysLabel } from '../../utils/stopText'
import { TRAVEL_PLAN_ITEM_TYPES, type TravelPlan, type TravelPlanItemType, type TravelPlanStop } from '../../types/travelTypes'

const props = defineProps<{ plan: TravelPlan }>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

const fmt = (n: unknown) => formatAmount(Number(n ?? 0), 2)

/** 能画到地图上的站：`located=false` 的一律不画（猜坐标会落到海里） */
const locatedStops = computed(() =>
  props.plan.stops.filter((s): s is TravelPlanStop & { lat: number; lng: number } =>
    s.located && s.lat != null && s.lng != null,
  ),
)

const activeId = ref<number | null>(props.plan.stops[0]?.id ?? null)
const activeStop = computed(() => props.plan.stops.find((s) => s.id === activeId.value) ?? null)
const activeItems = computed(() => activeStop.value?.items ?? [])

/** 相邻两站只有一端能定位：连线在这里断开，要说出来（否则看着像漏画） */
const brokenText = computed(() => {
  const stops = props.plan.stops
  const broken = stops.filter((s, i) => {
    const prev = stops[i - 1]
    if (!prev) return false
    return prev.located !== s.located
  })
  if (!broken.length) return ''
  return `有 ${broken.length} 处相邻站未能连线（其中一端没定位），不是地图漏画`
})

function itemIcon(type: TravelPlanItemType): string {
  const hit = TRAVEL_PLAN_ITEM_TYPES.find((t) => t.value === type)
  return hit ? hit.label.split(' ')[0] : '📌'
}

function select(id: number) {
  activeId.value = id
  render()
}

function buildOption(): echarts.EChartsOption {
  const coords: LngLat[] = locatedStops.value.map((s) => [s.lng, s.lat])
  const { center, zoom } = fitRouteView(coords)

  // 只连「相邻且两端都能定位」的站：中间断掉的段不跨海乱飞
  const segments: { coords: LngLat[] }[] = []
  const stops = props.plan.stops
  for (let i = 1; i < stops.length; i++) {
    const a = stops[i - 1]
    const b = stops[i]
    if (a.located && b.located && a.lng != null && a.lat != null && b.lng != null && b.lat != null) {
      segments.push({ coords: [[a.lng, a.lat], [b.lng, b.lat]] })
    }
  }

  const points = locatedStops.value.map((s) => ({
    name: s.city_input,
    // 🔴 `value` 是坐标（ECharts 约定），别往里塞金额 —— 第三个维度更不是钱。
    //    金额只从 `plan.stops[].subtotal` 现读（tooltip / 侧栏），不复制到图表数据里。
    value: [s.lng, s.lat, 1],
    stopId: s.id,
    order: s.order,
  }))

  return {
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: any) => {
        if (params.seriesType !== 'scatter') return ''
        const d = params.data
        const stop = props.plan.stops.find((s) => s.id === d.stopId)
        if (!stop) return d.name
        return `<strong>${d.name}</strong><br/>
          ${arriveLabel(stop.arrive_date)} · ${daysLabel(stop.days)}<br/>
          本站合计：¥${fmt(stop.subtotal)}<br/>
          ${stop.items?.length ? `条目 ${stop.items.length} 条` : '还没排条目'}`
      },
    },
    geo: {
      map: registerChinaProvinceMap(),
      roam: true,
      center,
      zoom,
      scaleLimit: { min: 0.8, max: 20 },
      itemStyle: { areaColor: '#F4F7FB', borderColor: '#D8DFEA', borderWidth: 1 },
      emphasis: { itemStyle: { areaColor: '#E8EFFA' }, label: { show: false } },
      select: { disabled: true },
    },
    series: [
      {
        name: '行程',
        type: 'lines' as const,
        coordinateSystem: 'geo' as const,
        z: 3,
        data: segments,
        symbol: ['none', 'arrow'],
        symbolSize: 7,
        lineStyle: { color: '#4C8DFF', width: 3, curveness: 0.12 },
        effect: { show: false },
      },
      {
        name: '站点',
        type: 'scatter' as const,
        coordinateSystem: 'geo' as const,
        z: 6,
        data: points,
        symbolSize: (_val: number[], params: any) => (params?.data?.stopId === activeId.value ? 28 : 20),
        itemStyle: {
          color: (params: any) => (params?.data?.stopId === activeId.value ? '#FF7A45' : '#4C8DFF'),
          borderColor: '#fff',
          borderWidth: 2,
          shadowBlur: 6,
          shadowColor: 'rgba(31,41,55,0.25)',
        },
        label: {
          show: true,
          // 🔴 点里只放**站序**，城市名与金额交给右侧站序表（同号的顺序一一对齐）。
          //    试过「名称+金额」直接标在点上：相邻两站（泉州↔漳州）只隔 40 多像素，
          //    横排、竖排都会压在一起，叠着的价格等于没写。数字只有一个字符，怎么排都不撞。
          position: 'inside' as const,
          formatter: (params: any) => String(params.data.order),
          color: '#fff',
          fontSize: 12,
          fontWeight: 'bold' as const,
        },
        emphasis: { scale: 1.2 },
        // 兜底：万一两站近到圆点本身都叠了，也按顺序保证数字可读
        labelLayout: { hideOverlap: true },
      },
    ],
  } as echarts.EChartsOption
}

function render() {
  if (!chart) return
  chart.setOption(buildOption(), true)
}

onMounted(async () => {
  await nextTick()
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  render()
  chart.on('click', (params: any) => {
    if (params?.seriesType !== 'scatter') return
    const id = params?.data?.stopId
    if (typeof id === 'number') select(id)
  })
  // 🔴 抽屉/侧栏改变宽度时 window 不触发 resize，画布会停在旧尺寸
  //    （地图右半边被裁掉，看着像瓦片没加载完）。
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(chartRef.value)
})

// 计划在抽屉里被改名/改站后重画：选中站消失时退回第一站，不让面板空着
watch(
  () => props.plan.stops.map((s) => s.id).join(','),
  () => {
    if (!props.plan.stops.some((s) => s.id === activeId.value)) {
      activeId.value = props.plan.stops[0]?.id ?? null
    }
    render()
  },
)

onUnmounted(() => {
  observer?.disconnect()
  observer = null
  chart?.dispose()
  chart = null
})
</script>

<style scoped lang="scss">
.plan-map {
  display: flex;
  /* 🔴 它是 flex 行容器 .map-body 里的一个 item：不给 flex/width 会被压成 0 宽
     （画布 rect.width = 0，地图一片空白，而 DOM 上"看起来"都在） */
  flex: 1;
  width: 100%;
  min-width: 0;
  height: 100%;
  min-height: 0;
  background: #fff;

  .map-box {
    position: relative;
    flex: 1;
    min-width: 0;
    min-height: 0;

    .chart { width: 100%; height: 100%; }

    .map-empty {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 13px;
      color: #9ca3af;
      text-align: center;
      pointer-events: none;
    }

    .map-warn {
      position: absolute;
      top: 12px;
      left: 12px;
      padding: 4px 10px;
      border-radius: 6px;
      background: #fdf6ec;
      border: 1px solid #faecd8;
      font-size: 12px;
      color: #b88230;
    }

    .map-legend {
      position: absolute;
      left: 12px;
      bottom: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 5px 10px;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid #eef0f3;
      font-size: 12px;
      color: #6b7280;

      .dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background: #4c8dff;
      }
      .line {
        width: 16px;
        height: 3px;
        border-radius: 2px;
        background: #4c8dff;
        margin-left: 6px;
      }
    }
  }

  .stop-panel {
    width: 320px;
    flex-shrink: 0;
    border-left: 1px solid #eef0f3;
    overflow-y: auto;
    padding: 12px 14px 16px;
    background: #fcfdfe;

    .panel-head {
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding-bottom: 8px;
      border-bottom: 1px solid #f0f2f5;

      .panel-title { font-size: 14px; font-weight: 700; color: #1f2937; }
      .panel-note { font-size: 12px; color: #9ca3af; }
    }

    .stop-rows {
      list-style: none;
      margin: 6px 0 0;
      padding: 0;

      .stop-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 8px;
        border-radius: 6px;
        cursor: pointer;

        &:hover { background: #f3f7ff; }
        &.active { background: #ecf3ff; }

        .row-order {
          width: 18px;
          height: 18px;
          line-height: 18px;
          text-align: center;
          border-radius: 50%;
          background: #e8effa;
          color: #4c8dff;
          font-size: 11px;
          font-weight: 700;
          flex-shrink: 0;
        }
        &.active .row-order { background: #ff7a45; color: #fff; }

        .row-city { flex: 1; font-size: 13px; color: #1f2937; min-width: 0; }
        .row-unlocated {
          margin-left: 4px;
          font-size: 11px;
          color: #b88230;
          border: 1px solid #faecd8;
          border-radius: 8px;
          padding: 0 4px;
        }
        .row-days { font-size: 12px; color: #9ca3af; white-space: nowrap; }
        .row-cost { font-size: 13px; font-weight: 600; color: #e6a23c; white-space: nowrap; }
      }
    }

    .detail {
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px dashed #eef0f3;

      .detail-head {
        display: flex;
        align-items: baseline;
        gap: 8px;

        .detail-city { font-size: 15px; font-weight: 700; color: #1f2937; }
        .detail-meta { font-size: 12px; color: #9ca3af; }
      }

      .detail-nums {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 6px;

        .detail-cost { font-size: 18px; font-weight: 700; color: #e6a23c; }
        .chip {
          font-size: 12px;
          color: #6b7280;
          background: #f5f7fa;
          border-radius: 10px;
          padding: 1px 8px;
        }
      }

      .item-list {
        margin-top: 8px;

        .item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 3px 0;
          font-size: 13px;

          &.done .item-name { color: #c0c4cc; text-decoration: line-through; }

          .item-icon { font-size: 13px; }
          .item-name { flex: 1; color: #303133; min-width: 0; }
          .item-cost { color: #909399; font-size: 12px; }
        }
      }

      .item-empty { margin-top: 8px; font-size: 12px; color: #9ca3af; }

      .detail-hint {
        margin: 10px 0 0;
        font-size: 11px;
        line-height: 1.6;
        color: #c0c4cc;
      }
    }
  }
}
</style>
