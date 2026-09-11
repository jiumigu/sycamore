<template>
  <div class="wish-page">
    <!-- 顶部统计 -->
    <div class="stats-row">
      <div class="stat-chip">
        <span class="stat-num">{{ stats.total }}</span>
        <span class="stat-label">总心愿</span>
      </div>
      <div class="stat-chip status-want">
        <span class="stat-num">{{ stats.by_status['想去'] || 0 }}</span>
        <span class="stat-label">想去</span>
      </div>
      <div class="stat-chip status-planned">
        <span class="stat-num">{{ stats.by_status['已列入计划'] || 0 }}</span>
        <span class="stat-label">已列入计划</span>
      </div>
      <div class="stat-chip status-done">
        <span class="stat-num">{{ stats.by_status['已打卡'] || 0 }}</span>
        <span class="stat-label">已打卡</span>
      </div>
      <div class="stat-chip">
        <span class="stat-num">{{ stats.located }}</span>
        <span class="stat-label">已定位</span>
      </div>
      <el-button type="primary" class="add-btn" @click="openCreate">＋ 新增心愿</el-button>
    </div>

    <!-- 地图 -->
    <el-card shadow="never" class="map-card">
      <template #header>
        <div class="card-header">
          <span>🗺️ 心愿地图</span>
          <span class="legend">
            <span class="dot" style="background: #e6a23c" />想去
            <span class="dot" style="background: #409eff" />已列入计划
            <span class="dot" style="background: #67c23a" />已打卡
          </span>
        </div>
      </template>
      <div ref="mapRef" class="map-box" />
    </el-card>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="filterCategory" placeholder="全部分类" clearable style="width: 140px">
        <el-option v-for="(label, key) in CATEGORY_LABELS" :key="key" :label="label" :value="key" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 140px">
        <el-option label="想去" value="想去" />
        <el-option label="已列入计划" value="已列入计划" />
        <el-option label="已打卡" value="已打卡" />
      </el-select>
      <el-select v-model="filterProvince" placeholder="全部省份" clearable filterable style="width: 130px" @change="onProvinceChange">
        <el-option v-for="p in provinceList" :key="p" :label="p" :value="p" />
      </el-select>
      <el-select v-model="filterCity" placeholder="全部城市" clearable filterable style="width: 130px" :disabled="!filterProvince" @change="onCityChange">
        <el-option v-for="c in cityList" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="filterDistrict" placeholder="全部区县" clearable filterable style="width: 130px" :disabled="!filterCity">
        <el-option v-for="d in districtList" :key="d" :label="d" :value="d" />
      </el-select>
      <el-input v-model="searchText" placeholder="搜索心愿名称" clearable style="width: 200px" prefix-icon="Search" />
      <span class="filter-count">共 {{ filteredWishes.length }} 条</span>
    </div>

    <!-- 按省份分组列表 -->
    <div v-if="!loading" class="wish-groups">
      <div v-for="group in groupedWishes" :key="group.province" class="wish-group">
        <div class="group-header">
          <span class="group-title">{{ group.province || '未定位' }}</span>
          <span class="group-count">{{ group.items.length }} 条 · 打卡 {{ group.done }} </span>
        </div>
        <div class="wish-grid">
          <div
            v-for="w in group.items"
            :key="w.id"
            class="wish-card"
            :class="{ 'is-done': w.status === '已打卡' }"
            @click="openEdit(w)"
          >
            <div class="wish-top">
              <span class="wish-cat">{{ CATEGORY_LABELS[w.category] || '📌' }}</span>
              <span class="wish-name" :title="w.name">{{ w.name }}</span>
            </div>
            <div class="wish-meta">
              <span>{{ [w.city, w.district].filter(Boolean).join(' · ') || w.province || '—' }}</span>
              <span class="wish-status" :class="statusClass(w.status)">{{ w.status }}</span>
            </div>
            <div class="wish-actions" @click.stop>
              <el-button
                size="small"
                :type="w.status === '已打卡' ? 'warning' : 'success'"
                plain
                @click="toggleVisited(w)"
              >
                {{ w.status === '已打卡' ? '取消打卡' : '✓ 打卡' }}
              </el-button>
              <el-button
                size="small"
                type="primary"
                plain
                :disabled="w.status === '已打卡'"
                @click="openAddToPlan(w)"
              >
                加入计划
              </el-button>
              <el-popconfirm title="确定删除该心愿？" width="180" @confirm="removeWish(w)">
                <template #reference>
                  <el-button size="small" type="danger" plain>删除</el-button>
                </template>
              </el-popconfirm>
            </div>
            <div v-if="w.visited_at" class="wish-visited">🗓️ {{ w.visited_at }}</div>
          </div>
        </div>
      </div>
      <el-empty v-if="filteredWishes.length === 0" description="没有符合条件的心愿" />
    </div>
    <div v-else class="loading-box" v-loading="loading" />

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="editVisible" :title="editingId ? '编辑心愿' : '新增心愿'" width="460px">
      <el-form label-width="70px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" placeholder="如：中山陵 / 蛋烘糕" maxlength="200" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editForm.category" style="width: 100%">
            <el-option v-for="(label, key) in CATEGORY_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="城市">
          <el-input v-model="editForm.city" placeholder="如：成都（留空则按名称自动定位）" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveWish">保存</el-button>
      </template>
    </el-dialog>

    <!-- 加入计划弹窗 -->
    <el-dialog v-model="planVisible" title="加入旅行计划" width="480px">
      <div v-if="planWish" class="plan-wish-name">
        {{ CATEGORY_LABELS[planWish.category] || '📌' }} {{ planWish.name }}
        <span class="plan-wish-city">{{ planWish.city || planWish.province }}</span>
      </div>
      <el-radio-group v-model="planMode" class="plan-mode">
        <el-radio value="existing">加入已有计划</el-radio>
        <el-radio value="new">新建计划</el-radio>
      </el-radio-group>
      <template v-if="planMode === 'existing'">
        <el-empty v-if="activePlans.length === 0" description="暂无进行中的计划，请选择新建" :image-size="60" />
        <el-select v-else v-model="planId" style="width: 100%" placeholder="选择计划">
          <el-option v-for="p in activePlans" :key="p.id" :label="`${p.name}（${p.destination || '未定'} · ${p.status}）`" :value="p.id" />
        </el-select>
      </template>
      <template v-else>
        <el-form label-width="80px">
          <el-form-item label="计划名称">
            <el-input v-model="newPlan.name" placeholder="如：云南之旅" />
          </el-form-item>
          <el-form-item label="目的地">
            <el-input v-model="newPlan.destination" placeholder="如：大理" />
          </el-form-item>
          <el-form-item label="出发日期">
            <el-date-picker v-model="newPlan.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="planVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingPlan" @click="confirmAddToPlan">加入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import betterEchartsMaps from 'better-echarts-maps/dist/china.js'
import {
  getWishes, createWish, updateWish, deleteWish,
  getWishStats, markWishVisited, addWishToPlan, getTravelPlans,
} from '../api/travelApi'
import type { TravelWish, WishStats, TravelPlanOption } from '../types/travelTypes'

const CATEGORY_LABELS: Record<string, string> = {
  景点: '📍 景点', 美食: '🍽️ 美食', 古镇: '🏘️ 古镇', 寺庙: '🛕 寺庙',
  自然: '⛰️ 自然', 大学: '🎓 大学', 书店: '📚 书店', 街区: '🏙️ 街区',
  夜市: '🍢 夜市', 路线: '🚶 路线', 其他: '📌 其他',
}

const STATUS_COLOR: Record<string, string> = {
  想去: '#e6a23c',
  已列入计划: '#409eff',
  已打卡: '#67c23a',
}

const loading = ref(true)
const saving = ref(false)
const savingPlan = ref(false)
const wishes = ref<TravelWish[]>([])
const stats = ref<WishStats>({ total: 0, located: 0, by_status: {}, by_category: {} })

const filterCategory = ref('')
const filterStatus = ref('')
const filterProvince = ref('')
const filterCity = ref('')
const filterDistrict = ref('')
const searchText = ref('')

// ===== 地图 =====
const mapRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function renderMap() {
  if (!chart) return
  const located = filteredWishes.value.filter(w => w.lng != null && w.lat != null)
  const seriesByStatus = (status: string) => located
    .filter(w => w.status === status)
    .map(w => ({ name: w.name, value: [w.lng, w.lat], city: w.city, category: w.category }))
  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (p: { name: string; data: { city: string; category: string } }) =>
        `${p.name}<br/>${p.data?.city || ''}`,
    },
    geo: {
      map: 'china',
      roam: true,
      zoom: 1.1,
      itemStyle: { areaColor: '#f5f7fa', borderColor: '#dcdfe6' },
      emphasis: { itemStyle: { areaColor: '#e8f0fe' } },
      scaleLimit: { min: 0.8, max: 8 },
    },
    series: (['想去', '已列入计划', '已打卡'] as const).map(s => ({
      name: s,
      type: 'scatter',
      coordinateSystem: 'geo',
      data: seriesByStatus(s),
      symbolSize: 8,
      itemStyle: { color: STATUS_COLOR[s], opacity: 0.85 },
    })),
  }, true)
}

// ===== 数据 =====
async function loadAll() {
  loading.value = true
  try {
    const [wRes, sRes] = await Promise.all([getWishes(), getWishStats()])
    wishes.value = wRes.data || []
    stats.value = sRes.data || stats.value
    await nextTick()
    renderMap()
  } catch {
    ElMessage.error('心愿数据加载失败')
  } finally {
    loading.value = false
  }
}

async function refresh() {
  const [wRes, sRes] = await Promise.all([getWishes(), getWishStats()])
  wishes.value = wRes.data || []
  stats.value = sRes.data || stats.value
  renderMap()
}

// ===== 筛选与分组 =====
const provinceList = computed(() =>
  [...new Set(wishes.value.map(w => w.province).filter(Boolean))].sort()
)

const cityList = computed(() => {
  const pool = filterProvince.value
    ? wishes.value.filter(w => w.province === filterProvince.value)
    : wishes.value
  return [...new Set(pool.map(w => w.city).filter(Boolean))].sort()
})

const districtList = computed(() => {
  let pool = wishes.value
  if (filterProvince.value) pool = pool.filter(w => w.province === filterProvince.value)
  if (filterCity.value) pool = pool.filter(w => w.city === filterCity.value)
  return [...new Set(pool.map(w => w.district).filter(Boolean))].sort()
})

function onProvinceChange() {
  filterCity.value = ''
  filterDistrict.value = ''
}

function onCityChange() {
  filterDistrict.value = ''
}

const filteredWishes = computed(() =>
  wishes.value.filter(w => {
    if (filterCategory.value && w.category !== filterCategory.value) return false
    if (filterStatus.value && w.status !== filterStatus.value) return false
    if (filterProvince.value && w.province !== filterProvince.value) return false
    if (filterCity.value && w.city !== filterCity.value) return false
    if (filterDistrict.value && w.district !== filterDistrict.value) return false
    if (searchText.value && !w.name.includes(searchText.value.trim())) return false
    return true
  })
)

const groupedWishes = computed(() => {
  const map = new Map<string, TravelWish[]>()
  for (const w of filteredWishes.value) {
    const key = w.province || '未定位'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(w)
  }
  return [...map.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .map(([province, items]) => ({
      province,
      items,
      done: items.filter(w => w.status === '已打卡').length,
    }))
})

function statusClass(s: string) {
  return { 'st-done': s === '已打卡', 'st-planned': s === '已列入计划', 'st-want': s === '想去' }
}

// ===== 打卡 =====
async function toggleVisited(w: TravelWish) {
  try {
    const res = await markWishVisited(w.id)
    const updated: TravelWish = res.data
    w.status = updated.status
    w.visited_at = updated.visited_at
    await refresh()
    ElMessage.success(w.status === '已打卡' ? `已打卡：${w.name}` : `已取消打卡：${w.name}`)
  } catch {
    ElMessage.error('操作失败')
  }
}

// ===== 新增 / 编辑 =====
const editVisible = ref(false)
const editingId = ref<number | null>(null)
const editForm = ref({ name: '', category: '景点', city: '', notes: '' })

function openCreate() {
  editingId.value = null
  editForm.value = { name: '', category: '景点', city: '', notes: '' }
  editVisible.value = true
}

function openEdit(w: TravelWish) {
  editingId.value = w.id
  editForm.value = { name: w.name, category: w.category, city: w.city, notes: w.notes }
  editVisible.value = true
}

async function saveWish() {
  if (!editForm.value.name.trim()) {
    ElMessage.warning('请填写心愿名称')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateWish(editingId.value, { ...editForm.value })
    } else {
      await createWish({ ...editForm.value })
    }
    editVisible.value = false
    await refresh()
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function removeWish(w: TravelWish) {
  try {
    await deleteWish(w.id)
    await refresh()
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

// ===== 加入计划 =====
const planVisible = ref(false)
const planWish = ref<TravelWish | null>(null)
const planMode = ref<'existing' | 'new'>('existing')
const planId = ref<number | null>(null)
const plans = ref<TravelPlanOption[]>([])
const newPlan = ref({ name: '', destination: '', start_date: '' })

const activePlans = computed(() => plans.value.filter(p => p.status === '计划中' || p.status === '进行中'))

async function openAddToPlan(w: TravelWish) {
  planWish.value = w
  planMode.value = 'existing'
  planId.value = null
  newPlan.value = {
    name: w.city ? `${w.city}之旅` : '未命名行程',
    destination: w.city || w.province || '',
    start_date: '',
  }
  try {
    const res = await getTravelPlans()
    plans.value = res.data?.results || res.data || []
  } catch { /* 静默 */ }
  planVisible.value = true
}

async function confirmAddToPlan() {
  if (!planWish.value) return
  if (planMode.value === 'existing' && !planId.value) {
    ElMessage.warning('请选择计划')
    return
  }
  savingPlan.value = true
  try {
    await addWishToPlan(planWish.value.id, planMode.value === 'existing'
      ? { plan_id: planId.value! }
      : { ...newPlan.value })
    planVisible.value = false
    await refresh()
    ElMessage.success(`「${planWish.value.name}」已加入计划`)
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error
    ElMessage.error(msg || '加入计划失败')
  } finally {
    savingPlan.value = false
  }
}

onMounted(async () => {
  // 与 ChinaHeatmap 一致：提取 GeoJSON 再注册（直接注册模块对象会导致边界碎裂）
  const chinaPkg = betterEchartsMaps as unknown as { China?: Array<[string, object]> }
  const chinaGeoJSON = chinaPkg.China?.[0]?.[1] ?? (betterEchartsMaps as unknown as object)
  echarts.registerMap('china', chinaGeoJSON as never)
  chart = echarts.init(mapRef.value!)
  window.addEventListener('resize', onResize)
  await loadAll()
})

function onResize() {
  chart?.resize()
}

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.wish-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.stats-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.stat-chip {
  background: var(--el-fill-color-light);
  border-radius: 10px;
  padding: 8px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 76px;
}

.stat-chip.status-want { background: #fdf6ec; }
.stat-chip.status-planned { background: #ecf5ff; }
.stat-chip.status-done { background: #f0f9eb; }

.stat-num {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.add-btn {
  margin-left: auto;
}

.map-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.legend {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-left: 8px;
}

.map-box {
  height: 420px;
}

.filter-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.filter-count {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.wish-group {
  margin-bottom: 20px;
}

.group-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 6px;
}

.group-title {
  font-size: 15px;
  font-weight: 700;
}

.group-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.wish-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
}

.wish-card {
  background: var(--el-fill-color-lighter);
  border-radius: 10px;
  padding: 10px 12px;
  cursor: pointer;
  transition: box-shadow 0.2s;
  position: relative;
}

.wish-card:hover {
  box-shadow: var(--el-box-shadow-light);
}

.wish-card.is-done {
  opacity: 0.75;
}

.wish-top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.wish-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wish-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 4px 0 8px;
}

.wish-status {
  padding: 1px 8px;
  border-radius: 8px;
  font-size: 11px;
}

.wish-status.st-want { background: #fdf6ec; color: #e6a23c; }
.wish-status.st-planned { background: #ecf5ff; color: #409eff; }
.wish-status.st-done { background: #f0f9eb; color: #67c23a; }

.wish-actions {
  display: flex;
  gap: 6px;
}

.wish-actions .el-button {
  margin-left: 0;
}

.wish-visited {
  font-size: 11px;
  color: var(--el-color-success);
  margin-top: 6px;
}

.plan-wish-name {
  font-weight: 600;
  margin-bottom: 12px;
}

.plan-wish-city {
  color: var(--el-text-color-secondary);
  font-weight: normal;
  margin-left: 8px;
  font-size: 13px;
}

.plan-mode {
  margin-bottom: 12px;
}

.loading-box {
  height: 300px;
}

@media (max-width: 768px) {
  .map-box {
    height: 300px;
  }
}
</style>
