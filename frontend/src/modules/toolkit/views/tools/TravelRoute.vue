<template>
  <div class="travel-route">
    <el-row :gutter="16">
      <el-col :span="7">
        <!-- 已保存路线 -->
        <el-card class="preset-card" shadow="never">
          <template #header>
            <div class="preset-header">
              <span>📋 已保存路线</span>
              <el-button @click="saveAsPreset" size="small" type="primary" plain>+ 新建路线</el-button>
            </div>
          </template>
          <div v-if="presets.length === 0" class="preset-empty">暂无保存的路线</div>
          <div v-for="p in presets" :key="p.id" class="preset-item" @click="loadPreset(p)">
            <div class="preset-info">
              <span class="preset-name">{{ p.name }}</span>
              <span class="preset-summary">{{ p.origin }} → {{ p.destinations.join('→') }}</span>
            </div>
            <div class="preset-actions" @click.stop>
              <el-button @click="editPreset(p)" size="small" circle>✏️</el-button>
              <el-button @click="removePreset(p.id)" size="small" type="danger" circle>🗑️</el-button>
            </div>
          </div>
        </el-card>

        <el-card class="input-card" shadow="never">
          <el-form label-width="70px">
            <el-form-item label="出发地">
              <el-autocomplete
                v-model="origin"
                :fetch-suggestions="queryCities"
                :trigger-on-focus="false"
                placeholder="如：福州"
                clearable
                @select="onOriginSelect"
              />
            </el-form-item>
            <el-form-item label="目的地">
              <div v-for="(d, i) in destinations" :key="i" class="dest-row">
                <el-autocomplete
                  v-model="destinations[i]"
                  :fetch-suggestions="queryCities"
                  :trigger-on-focus="false"
                  :placeholder="`第${i + 1}站`"
                  clearable
                  style="flex:1"
                  @select="(item: any) => onDestSelect(i, item)"
                />
                <el-button @click="removeDest(i)" type="danger" size="small" circle>✕</el-button>
              </div>
              <el-button @click="addDest" size="small">+ 添加目的地</el-button>
            </el-form-item>
            <el-form-item>
              <el-button @click="saveAsPreset" size="small">💾 保存为预设路线</el-button>
              <el-button type="primary" @click="startJourney" :loading="loadingCities">🚂 出发</el-button>
              <el-button @click="reset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 站点列表 -->
        <el-card v-if="started" class="stop-list-card" shadow="never">
          <template #header><span>📍 行程站点</span></template>
          <div v-for="(s, i) in stops" :key="i" class="stop-item" :class="{
            'stop-passed': i < currentStop,
            'stop-current': i === currentStop,
            'stop-future': i > currentStop,
          }">
            <span class="stop-index">
              <span v-if="i < currentStop" class="stop-check">✅</span>
              <span v-else-if="i === currentStop" class="stop-train">🚂</span>
              <span v-else class="stop-dot">●</span>
            </span>
            <span class="stop-name">{{ s }}</span>
            <span v-if="hasCity(s)" class="stop-coord">✓ 已定位</span>
            <span v-else class="stop-coord warn">⚠ 无坐标</span>
          </div>
        </el-card>
      </el-col>

      <el-col :span="17">
        <el-card v-if="started" class="map-card" shadow="never">
          <div ref="chartRef" class="map-container" />
          <div class="controls">
            <el-button @click="prevStop" :disabled="currentStop === 0">⏮ 上一站</el-button>
            <span class="current-info">
              <template v-if="currentStop < stops.length">{{ stops[currentStop] }} 🚂</template>
              <template v-else>终点 🏁</template>
            </span>
            <el-button @click="nextStop" :disabled="currentStop >= stops.length - 1 || isAnimating">下一站 ⏭</el-button>
            <el-button @click="autoPlay" :type="playing ? 'warning' : 'primary'">
              {{ playing ? '⏸ 暂停' : '▶ 自动播放' }}
            </el-button>
          </div>
        </el-card>

        <el-card v-else class="placeholder-card" shadow="never">
          <div class="placeholder-content">
            <div class="placeholder-icon">🚂</div>
            <p class="placeholder-text">输入出发地和目的地，点击「出发」在地图上查看路线</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

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
          <div class="destination-list">
            <draggable
              v-model="presetForm.destinations"
              item-key="index"
              handle=".drag-handle"
              :animation="200"
            >
              <template #item="{ element, index }">
                <div class="destination-item">
                  <span class="drag-handle">⋮⋮</span>
                  <span class="dest-order">{{ index + 1 }}</span>
                  <el-autocomplete
                    v-model="presetForm.destinations[index]"
                    :fetch-suggestions="dialogQueryCities"
                    :trigger-on-focus="false"
                    placeholder="搜索城市"
                    style="flex:1"
                    clearable
                  />
                  <el-button @click="removePresetDest(index)" circle size="small" type="danger">✕</el-button>
                </div>
              </template>
            </draggable>
          </div>
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
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import betterEchartsMaps from 'better-echarts-maps/dist/china.js'
import draggable from 'vuedraggable'

import * as api from '../../api/toolkitApi'
import type { CityCoordinate, TravelRoutePreset } from '../../types/toolkitTypes'

const origin = ref('福州')
const destinations = ref(['泉州', '厦门', '漳州'])
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

function loadPreset(p: TravelRoutePreset) {
  origin.value = p.origin
  destinations.value = [...p.destinations]
  startJourney()
}

function saveAsPreset() {
  editingPreset.value = null
  presetForm.value = {
    name: '',
    origin: origin.value,
    destinations: destinations.value.filter(d => d.trim()),
    description: '',
  }
  showPresetDialog.value = true
}

async function savePreset() {
  const data = { ...presetForm.value }
  if (!data.name.trim() || !data.origin.trim() || data.destinations.filter(d => d.trim()).length === 0) {
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

async function removePreset(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该路线？', '确认删除', { type: 'warning' })
    await api.deleteTravelRoute(id)
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
    cb([])
    return
  }
  const q = query.trim()
  const results = cityList.value
    .filter(c => c.name.includes(q) || (c.pinyin && c.pinyin.includes(q.toLowerCase())))
    .slice(0, 10)
    .map(c => ({ value: c.name, ...c }))
  cb(results)
}

function dialogQueryCities(query: string, cb: (results: any[]) => void) {
  if (!query.trim()) {
    cb(cityList.value.slice(0, 10).map(c => ({ value: c.name, ...c })))
    return
  }
  queryCities(query, cb)
}

function onOriginSelect(item: any) {
  origin.value = item.value
}

function onDestSelect(i: number, item: any) {
  destinations.value[i] = item.value
}

function getCoords(name: string): [number, number] {
  const c = cityMap.value[name]
  return c ? [c.lng, c.lat] : [118.3, 25.5]
}

function addDest() {
  destinations.value.push('')
}

function removeDest(i: number) {
  destinations.value.splice(i, 1)
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
.travel-route { padding: 4px; }

.dest-row { display: flex; gap: 8px; margin-bottom: 8px; }

.input-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

.preset-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 12px; }
.preset-header { display: flex; justify-content: space-between; align-items: center; }
.preset-empty { color: #9ca3af; font-size: 13px; text-align: center; padding: 12px 0; }
.preset-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 10px; cursor: pointer; border-radius: 6px; transition: background 0.15s;
}
.preset-item:hover { background: #f3f4f6; }
.preset-info { display: flex; flex-direction: column; overflow: hidden; flex: 1; }
.preset-name { font-size: 13px; font-weight: 600; color: #1f2937; }
.preset-summary { font-size: 11px; color: #9ca3af; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preset-actions { display: flex; gap: 4px; flex-shrink: 0; }

.map-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.map-container { width: 100%; height: 600px; border-radius: 8px; }

.stop-list-card { margin-top: 16px; border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.stop-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 0; border-bottom: 1px solid #f3f4f6;
  font-size: 14px;
}
.stop-item:last-child { border-bottom: none; }
.stop-index { width: 28px; text-align: center; font-size: 16px; }
.stop-name { flex: 1; font-weight: 500; color: #1f2937; }
.stop-coord { font-size: 11px; color: #52c41a; }
.stop-coord.warn { color: #f59e0b; }
.stop-passed .stop-name { color: #52c41a; }
.stop-current .stop-name { color: #ff9800; font-weight: 700; }
.stop-future .stop-name { color: #9ca3af; }
.stop-dot { color: #d1d5db; }
.stop-train { font-size: 18px; }
.stop-check { font-size: 14px; }

.controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 16px;
}

.current-info {
  font-size: 22px;
  font-weight: 600;
  min-width: 140px;
  text-align: center;
}

.placeholder-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); min-height: 500px; display: flex; align-items: center; justify-content: center; }

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
.placeholder-content { text-align: center; }
.placeholder-icon { font-size: 64px; margin-bottom: 16px; }
.placeholder-text { font-size: 15px; color: #9CA3AF; margin: 0; }
</style>
