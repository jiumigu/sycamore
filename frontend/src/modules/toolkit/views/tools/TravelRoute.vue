<template>
  <div class="travel-route">
    <!-- 左侧折叠窄条 -->
    <div class="sidebar-toggle" @click="drawerOpen = !drawerOpen">
      <el-icon :size="20">
        <ArrowRight v-if="!drawerOpen" />
        <ArrowLeft v-else />
      </el-icon>
      <span v-if="!drawerOpen" class="toggle-text">路线</span>
    </div>

    <!-- 左侧抽屉（覆盖在地图上） -->
    <transition name="slide">
      <div v-if="drawerOpen" class="route-drawer">
        <div class="drawer-header">
          <span>📋 已保存路线</span>
          <el-button size="small" type="primary" @click="openNewRoute">+ 新建</el-button>
        </div>

        <div class="preset-list">
          <div
            v-for="preset in presets"
            :key="preset.id"
            class="preset-item"
            :class="{ active: selectedPreset?.id === preset.id }"
            @click="selectPreset(preset)"
          >
            <div class="preset-name">{{ preset.name }}</div>
            <div class="preset-route">{{ preset.origin }} → {{ preset.destinations.join(' → ') }}</div>
            <div class="preset-actions" @click.stop>
              <el-button size="small" text @click="editPreset(preset)">✏️</el-button>
              <el-button size="small" text type="danger" @click="deletePreset(preset.id)">🗑️</el-button>
            </div>
          </div>
        </div>

        <el-empty v-if="presets.length === 0" description="暂无路线，点击新建" />
      </div>
    </transition>

    <!-- 地图全屏 -->
    <div class="map-container">
      <div ref="chartRef" class="route-map" />

      <!-- 空状态提示（地图中央） -->
      <div v-if="!started" class="empty-hint">
        <div class="empty-icon">🗺️</div>
        <div class="empty-text">选择左侧路线或点击「新建」创建路线</div>
        <el-button type="primary" @click="drawerOpen = true">展开路线列表</el-button>
      </div>

      <!-- 控制栏 -->
      <div v-if="started" class="map-controls">
        <span class="current-stop">{{ stops[currentStop] }} 🚂</span>
        <el-button-group>
          <el-button size="small" :disabled="currentStop === 0" @click="prevStop">上一站</el-button>
          <el-button size="small" :disabled="currentStop >= stops.length - 1 || isAnimating" @click="nextStop">下一站</el-button>
        </el-button-group>
        <el-button size="small" :type="playing ? 'warning' : 'primary'" @click="autoPlay">{{ playing ? '⏸' : '▶' }}</el-button>
      </div>
    </div>

    <!-- 新建/编辑路线弹窗 -->
    <el-dialog v-model="showPresetDialog" :title="editingPreset ? '编辑路线' : '新建路线'" width="600px" destroy-on-close>
      <el-form :model="presetForm" label-width="80px">
        <el-form-item label="路线名称">
          <el-input v-model="presetForm.name" placeholder="如：福建沿海线" />
        </el-form-item>
        <el-form-item label="出发地">
          <el-select v-model="presetForm.origin" filterable allow-create placeholder="选择或输入城市" style="width:100%">
            <el-option v-for="c in cityList" :key="c.name" :label="c.name" :value="c.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="目的地">
          <draggable v-model="presetForm.destinations" item-key="index" handle=".drag-handle" :animation="200">
            <template #item="{ element, index }">
              <div class="destination-item">
                <span class="drag-handle">⋮⋮</span>
                <span class="dest-order">{{ index + 1 }}</span>
                <el-autocomplete
                  v-model="presetForm.destinations[index]"
                  :fetch-suggestions="queryCities"
                  :trigger-on-focus="false"
                  placeholder="搜索城市"
                  style="flex:1"
                  clearable
                />
                <el-button @click="removePresetDest(index)" circle size="small" type="danger">✕</el-button>
              </div>
            </template>
          </draggable>
          <el-button @click="addPresetDest" size="small" style="margin-top:8px">+ 添加目的地</el-button>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="presetForm.description" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPresetDialog = false">取消</el-button>
        <el-button type="primary" @click="savePreset" :loading="savingPreset">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import betterEchartsMaps from 'better-echarts-maps/dist/china.js'
import draggable from 'vuedraggable'

import * as api from '../../api/toolkitApi'
import type { CityCoordinate, TravelRoutePreset } from '../../types/toolkitTypes'

const drawerOpen = ref(false)
const origin = ref('')
const destinations = ref<string[]>([])
const started = ref(false)
const currentStop = ref(0)
const playing = ref(false)
const stops = ref<string[]>([])
const trainProgress = ref(0)
const isAnimating = ref(false)
const loadingCities = ref(false)

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null
let animFrameId: number | null = null
let autoPlayTimeout: number | null = null

// 路线预设
const presets = ref<TravelRoutePreset[]>([])
const selectedPreset = ref<TravelRoutePreset | null>(null)
const showPresetDialog = ref(false)
const editingPreset = ref<TravelRoutePreset | null>(null)
const savingPreset = ref(false)
const presetForm = ref({
  name: '',
  origin: '',
  destinations: [''],
  description: '',
})

// 从 API 加载的城市坐标
const cityMap = ref<Record<string, CityCoordinate>>({})
const cityList = ref<CityCoordinate[]>([])

async function loadCities() {
  loadingCities.value = true
  try {
    const res = await api.getAllCities()
    const list: CityCoordinate[] = res.data || []
    const map: Record<string, CityCoordinate> = {}
    for (const c of list) {
      map[c.name] = c
    }
    cityList.value = list
    cityMap.value = map
  } catch {
    // 静默失败，无坐标时使用默认值
  } finally {
    loadingCities.value = false
  }
}

// ====== 路线预设 ======
async function loadPresets() {
  try {
    const res = await api.getTravelRoutes()
    presets.value = res.data?.results || res.data || []
  } catch {
    // 静默失败
  }
}

function selectPreset(p: TravelRoutePreset) {
  selectedPreset.value = p
  origin.value = p.origin
  destinations.value = [...p.destinations]
  drawerOpen.value = false
  startJourney()
}

function openNewRoute() {
  selectedPreset.value = null
  editingPreset.value = null
  presetForm.value = {
    name: '',
    origin: '',
    destinations: [''],
    description: '',
  }
  showPresetDialog.value = true
}

async function savePreset() {
  const data = { ...presetForm.value }
  if (!data.name.trim() || !data.origin.trim() || data.destinations.filter((d: string) => d.trim()).length === 0) {
    ElMessage.warning('请填写路线名称、出发地和目的地')
    return
  }
  data.destinations = data.destinations.filter((d: string) => d.trim())
  savingPreset.value = true
  try {
    if (editingPreset.value) {
      await api.updateTravelRoute(editingPreset.value.id, data)
      ElMessage.success('路线已更新')
    } else {
      await api.createTravelRoute(data)
      ElMessage.success('路线已保存')
    }
    showPresetDialog.value = false
    await loadPresets()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingPreset.value = false
  }
}

function editPreset(p: TravelRoutePreset) {
  editingPreset.value = p
  presetForm.value = {
    name: p.name,
    origin: p.origin,
    destinations: [...p.destinations],
    description: p.description,
  }
  showPresetDialog.value = true
}

async function deletePreset(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该路线？', '确认删除', { type: 'warning' })
    await api.deleteTravelRoute(id)
    if (selectedPreset.value?.id === id) {
      reset()
    }
    ElMessage.success('已删除')
    await loadPresets()
  } catch {
    // 取消或失败
  }
}

function addPresetDest() {
  presetForm.value.destinations.push('')
}

function removePresetDest(i: number) {
  presetForm.value.destinations.splice(i, 1)
}

function hasCity(name: string): boolean {
  return !!cityMap.value[name]
}

function queryCities(query: string, cb: (results: any[]) => void) {
  if (!query.trim()) {
    cb(cityList.value.slice(0, 10).map(c => ({ value: c.name, ...c })))
    return
  }
  const q = query.trim()
  const results = cityList.value
    .filter(c => c.name.includes(q) || (c.pinyin && c.pinyin.includes(q.toLowerCase())))
    .slice(0, 10)
    .map(c => ({ value: c.name, ...c }))
  cb(results)
}

function getCoords(name: string): [number, number] {
  const c = cityMap.value[name]
  return c ? [c.lng, c.lat] : [118.3, 25.5]
}

function calcCenter(): [number, number] {
  const coords: [number, number][] = []
  for (const s of stops.value) {
    const c = getCoords(s)
    if (c[0] !== 118.3 || c[1] !== 25.5 || cityMap.value[s]) {
      coords.push(c)
    }
  }
  if (coords.length === 0) return [118.3, 25.5]
  const avgLng = coords.reduce((s, c) => s + c[0], 0) / coords.length
  const avgLat = coords.reduce((s, c) => s + c[1], 0) / coords.length
  return [avgLng, avgLat]
}

function calcZoom(): number {
  const coords: [number, number][] = []
  for (const s of stops.value) {
    const c = getCoords(s)
    if (c[0] !== 118.3 || c[1] !== 25.5 || cityMap.value[s]) {
      coords.push(c)
    }
  }
  if (coords.length < 2) return 8

  const lngs = coords.map(c => c[0])
  const lats = coords.map(c => c[1])
  const lngRange = Math.max(...lngs) - Math.min(...lngs)
  const latRange = Math.max(...lats) - Math.min(...lats)
  const maxRange = Math.max(lngRange, latRange)

  if (maxRange < 0.5) return 15
  if (maxRange < 2) return 10
  if (maxRange < 5) return 5
  if (maxRange < 15) return 3
  return 1.5
}

function startJourney() {
  const valid = destinations.value.filter(d => d.trim())
  if (!origin.value.trim() || valid.length === 0) return

  stops.value = [origin.value.trim(), ...valid]
  currentStop.value = 0
  trainProgress.value = 0
  started.value = true

  nextTick(() => {
    initMap()
    updateMap()
  })
}

function reset() {
  stopAnimation()
  started.value = false
  currentStop.value = 0
  trainProgress.value = 0
  playing.value = false
  selectedPreset.value = null
  chart?.dispose()
  chart = null
}

function initMap() {
  if (!chartRef.value) return

  const chinaPkg = (betterEchartsMaps as any)
  const chinaGeoJSON = chinaPkg.China?.[0]?.[1] || chinaPkg
  echarts.registerMap('china', chinaGeoJSON)

  chart = echarts.init(chartRef.value)
}

function getTrainPos(): [number, number] {
  if (stops.value.length === 0) return [118.3, 25.5]
  const fromIdx = currentStop.value
  if (fromIdx >= stops.value.length - 1) {
    return getCoords(stops.value[stops.value.length - 1])
  }
  const from = getCoords(stops.value[fromIdx])
  const to = getCoords(stops.value[fromIdx + 1])
  const t = trainProgress.value
  return [from[0] + (to[0] - from[0]) * t, from[1] + (to[1] - from[1]) * t]
}

function buildOption() {
  const center = calcCenter()
  const zoom = calcZoom()

  const series: any[] = []

  // 已走过的连线（实线）
  const passedData: { coords: [number, number][] }[] = []
  for (let i = 0; i < currentStop.value; i++) {
    passedData.push({
      coords: [getCoords(stops.value[i]), getCoords(stops.value[i + 1])],
    })
  }
  if (passedData.length > 0) {
    series.push({
      type: 'lines',
      coordinateSystem: 'geo',
      data: passedData,
      lineStyle: { color: '#52c41a', width: 4, curveness: 0.1 },
      effect: { show: false },
    })
  }

  // 未走过的连线（虚线），排除当前正在行驶的段
  const futureData: { coords: [number, number][] }[] = []
  for (let i = currentStop.value + 1; i < stops.value.length - 1; i++) {
    futureData.push({
      coords: [getCoords(stops.value[i]), getCoords(stops.value[i + 1])],
    })
  }
  if (futureData.length > 0) {
    series.push({
      type: 'lines',
      coordinateSystem: 'geo',
      data: futureData,
      lineStyle: { color: '#94a3b8', width: 3, curveness: 0.1, type: 'dashed' as const },
      effect: { show: false },
    })
  }

  // 当前段飞线动画
  if (currentStop.value < stops.value.length - 1) {
    series.push({
      type: 'lines',
      coordinateSystem: 'geo',
      zlevel: 2,
      data: [{
        coords: [getCoords(stops.value[currentStop.value]), getCoords(stops.value[currentStop.value + 1])],
      }],
      lineStyle: {
        color: '#ff6b6b',
        width: 4,
        curveness: 0.1,
        opacity: 0,
      },
      effect: {
        show: true,
        period: 3,
        symbol: 'arrow',
        symbolSize: 6,
        color: '#ff6b6b',
        trailLength: 0.3,
      },
    })
  }

  // 所有站点标记
  const stopPoints = stops.value.map((s, i) => {
    const c = getCoords(s)
    let color = '#94a3b8'
    let size = 6
    if (i < currentStop.value) {
      color = '#52c41a'
      size = 8
    } else if (i === currentStop.value) {
      color = '#ff9800'
      size = 12
    } else {
      color = '#94a3b8'
      size = 6
    }
    return {
      name: s,
      value: [...c, 1],
      itemStyle: { color },
      symbolSize: size,
      symbol: i === currentStop.value ? 'pin' : 'circle',
      label: {
        show: true,
        formatter: s,
        color: i <= currentStop.value ? '#1f2937' : '#9ca3af',
        fontSize: i === currentStop.value ? 14 : 12,
        fontWeight: i === currentStop.value ? 'bold' as const : 'normal' as const,
        position: 'bottom',
        distance: 10,
      },
    }
  })

  series.push({
    type: 'scatter',
    coordinateSystem: 'geo',
    zlevel: 3,
    data: stopPoints,
    symbolSize: (val: any, params: any) => params?.data?.symbolSize || 8,
    itemStyle: {
      color: (params: any) => params?.data?.itemStyle?.color || '#94a3b8',
    },
    label: {
      show: true,
      formatter: (params: any) => params?.data?.name || '',
      color: '#374151',
      fontSize: 13,
      position: 'bottom',
      distance: 10,
    },
  })

  // 小火车标记
  const trainPos = getTrainPos()
  series.push({
    type: 'effectScatter',
    coordinateSystem: 'geo',
    zlevel: 4,
    data: [{ value: [...trainPos, 1] }],
    symbolSize: 18,
    rippleEffect: { brushType: 'stroke', scale: 4, period: 4 },
    itemStyle: { color: '#ff4d4f' },
    label: {
      show: true,
      formatter: '🚂',
      fontSize: 18,
      offset: [0, -24],
    },
  })

  return {
    geo: {
      map: 'china',
      roam: true,
      center,
      zoom,
      itemStyle: {
        areaColor: '#f0f5ff',
        borderColor: '#d1d5db',
        borderWidth: 1,
      },
      emphasis: {
        itemStyle: { areaColor: '#e0ecff' },
        label: { show: true, fontSize: 12 },
      },
    },
    series,
  }
}

function updateMap() {
  if (!chart) return
  chart.setOption(buildOption(), true)
}

function animateToNextStop(duration = 1500) {
  if (isAnimating.value || currentStop.value >= stops.value.length - 1) return
  isAnimating.value = true
  trainProgress.value = 0
  const startTime = performance.now()

  function step(now: number) {
    const elapsed = now - startTime
    trainProgress.value = Math.min(elapsed / duration, 1)
    updateMap()

    if (trainProgress.value < 1) {
      animFrameId = requestAnimationFrame(step)
    } else {
      currentStop.value++
      trainProgress.value = 0
      isAnimating.value = false
      animFrameId = null
      updateMap()

      if (playing.value && currentStop.value < stops.value.length - 1) {
        autoPlayTimeout = window.setTimeout(() => {
          animateToNextStop(duration)
        }, 800)
      } else if (currentStop.value >= stops.value.length - 1) {
        playing.value = false
      }
    }
  }

  animFrameId = requestAnimationFrame(step)
}

function stopAnimation() {
  if (animFrameId !== null) {
    cancelAnimationFrame(animFrameId)
    animFrameId = null
  }
  if (autoPlayTimeout !== null) {
    clearTimeout(autoPlayTimeout)
    autoPlayTimeout = null
  }
  isAnimating.value = false
}

function nextStop() {
  if (isAnimating.value || currentStop.value >= stops.value.length - 1) return
  animateToNextStop()
}

function prevStop() {
  if (currentStop.value <= 0) return
  stopAnimation()
  currentStop.value--
  trainProgress.value = 0
  updateMap()
}

function autoPlay() {
  if (playing.value) {
    playing.value = false
    stopAnimation()
    return
  }
  playing.value = true
  if (currentStop.value >= stops.value.length - 1) {
    currentStop.value = 0
    trainProgress.value = 0
    updateMap()
  }
  animateToNextStop()
}

function handleResize() {
  chart?.resize()
}

onMounted(() => {
  loadCities()
  loadPresets()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  stopAnimation()
  chart?.dispose()
})
</script>

<style scoped>
.travel-route {
  position: relative;
  width: 100%;
  height: calc(100vh - 80px);
  overflow: hidden;
}

/* 左侧折叠窄条 */
.sidebar-toggle {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 100;
  width: 50px;
  height: 80px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 0 8px 8px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 2px 0 8px rgba(0,0,0,0.06);
  transition: all 0.2s;

  &:hover { background: #ecf5ff; }

  .toggle-text {
    writing-mode: vertical-rl;
    font-size: 13px;
    color: #666;
    margin-top: 4px;
  }
}

/* 抽屉（覆盖在地图上） */
.route-drawer {
  position: absolute;
  left: 0;
  top: 0;
  width: 340px;
  height: 100%;
  background: #fff;
  z-index: 99;
  box-shadow: 4px 0 16px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;

  .drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    border-bottom: 1px solid #f0f0f0;
    font-weight: 600;
  }

  .preset-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .preset-item {
    padding: 12px;
    border-radius: 8px;
    cursor: pointer;
    margin-bottom: 8px;
    border: 1px solid #eee;
    transition: all 0.2s;

    &:hover { background: #f5f7fa; }
    &.active { border-color: #409eff; background: #ecf5ff; }

    .preset-name { font-weight: 500; font-size: 14px; }
    .preset-route { font-size: 12px; color: #999; margin-top: 4px; }
    .preset-actions { margin-top: 4px; text-align: right; }
  }
}

/* 滑入动画 */
.slide-enter-active, .slide-leave-active {
  transition: transform 0.3s ease;
}
.slide-enter-from, .slide-leave-to {
  transform: translateX(-100%);
}

/* 地图全屏 */
.map-container {
  width: 100%;
  height: 100%;
  position: relative;

  .route-map {
    width: 100%;
    height: 100%;
  }

  /* 空状态提示 */
  .empty-hint {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    z-index: 10;

    .empty-icon { font-size: 64px; margin-bottom: 16px; }
    .empty-text { font-size: 16px; color: #999; margin-bottom: 16px; }
  }

  /* 控制栏 */
  .map-controls {
    position: absolute;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: #fff;
    padding: 8px 16px;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    display: flex;
    align-items: center;
    gap: 12px;
    z-index: 10;

    .current-stop {
      font-size: 16px;
      font-weight: 600;
      min-width: 100px;
      text-align: center;
    }
  }
}

/* 弹窗中的目的地编辑 */
.destination-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  background: #f9fafb;
  padding: 8px;
  border-radius: 8px;
}
.drag-handle {
  cursor: grab;
  color: #999;
  font-size: 18px;
  user-select: none;
}
.dest-order {
  width: 24px;
  height: 24px;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
</style>
