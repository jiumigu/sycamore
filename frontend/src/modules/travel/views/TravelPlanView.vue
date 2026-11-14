<template>
  <div class="travel-plan">
    <!-- 归档提示（仅在当前仍处于归档状态时显示，重新启用后自动消失） -->
    <el-alert v-if="ready && isArchived" title="此模块已归档，随时可重新启用" type="info" show-icon :closable="false" class="archive-banner" />
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1><span class="header-icon">🧳</span> 旅行计划</h1>
        <p class="header-desc">一条路线串起几座城：每站各自的预算、要吃要看的清单</p>
      </div>
      <div class="header-actions">
        <!-- v3.63.8：这两个都不再占菜单项，改成「旅行计划」页内入口 -->
        <el-button @click="$router.push('/travel/wishes')">⭐ 旅行心愿单</el-button>
        <el-button @click="$router.push('/travel/route')">🚂 路线推演</el-button>
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon> 新建计划
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value">{{ stats?.total_plans ?? 0 }}</div>
          <div class="stat-label">计划总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value text-warning">{{ fmt(stats?.total_estimate) }}</div>
          <div class="stat-label">总预估费用</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value text-success">{{ stats?.completed_plans ?? 0 }}</div>
          <div class="stat-label">已完成</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value">{{ plans.length - (stats?.completed_plans ?? 0) }}</div>
          <div class="stat-label">计划中</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 计划列表 -->
    <el-card class="plans-card" shadow="never">
      <template #header>📋 旅行计划列表</template>
      <div v-if="loading" v-loading="true" class="list-loading" />
      <div v-else-if="plans.length === 0" class="empty">
        <el-empty description="还没有旅行计划，点击右上角新建" />
      </div>
      <div v-for="plan in plans" :key="plan.id" class="plan-card">
        <div class="plan-header">
          <div class="plan-info" @click="togglePlan(plan)">
            <span class="plan-name">{{ plan.name }}</span>
            <!-- 路线串：站点顺序就是这条路线，不再是单个「目的地」 -->
            <el-tooltip :content="fullRoute(plan)" :disabled="plan.stops.length <= 3" placement="top">
              <span class="plan-route">{{ routeText(plan) }}</span>
            </el-tooltip>
            <el-tag :type="getStatusType(plan.status)" size="small">{{ plan.status }}</el-tag>
            <span class="plan-meta">{{ metaText(plan) }}</span>
            <span class="plan-date">{{ plan.start_date || '未定日期' }}</span>
            <el-icon class="expand-icon" :class="{ expanded: expandedPlanId === plan.id }"><ArrowDown /></el-icon>
          </div>
          <div class="plan-actions" @click.stop>
            <el-button size="small" @click="openPlanMap(plan)">🗺 地图</el-button>
            <el-button size="small" @click="editPlan(plan)">✏️ 编辑</el-button>
            <el-button size="small" :loading="copyingId === plan.id" @click="copyPlan(plan)">📋 复制</el-button>
            <el-button size="small" type="danger" @click="deletePlan(plan.id)">🗑️ 删除</el-button>
          </div>
        </div>

        <!-- 展开：站点层（每站自己的预算与清单 + 路上） -->
        <div v-if="expandedPlanId === plan.id" v-loading="expandedLoading" class="plan-detail">
          <PlanStopList v-if="expandedPlan" :plan="expandedPlan" @changed="refreshExpanded" />
        </div>
      </div>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingPlanId ? '编辑旅行计划' : '新建旅行计划'"
      width="680px"
      append-to-body
    >
      <el-form :model="createForm" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="计划名称" required>
              <el-input v-model="createForm.name" placeholder="如：闽粤沿海线" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="出发日期">
              <el-date-picker
                v-model="createForm.start_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="决定每站到达日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 站点只在新建时填：建完以后在列表里就地加/改/调序（一处入口） -->
        <template v-if="!editingPlanId">
          <el-divider>路线（按顺序填，出发地不用填）</el-divider>
          <div v-for="(s, index) in createForm.stops" :key="index" class="stop-edit-row">
            <span class="stop-index">{{ index + 1 }}</span>
            <el-input
              v-model="s.city"
              size="small"
              placeholder="城市，如：泉州"
              class="stop-city-input"
              @keyup.enter="addStopRow"
            />
            <el-input-number
              v-model="s.days"
              :min="0"
              :precision="0"
              size="small"
              controls-position="right"
              placeholder="待几天"
              class="stop-days-input"
            />
            <el-button
              size="small"
              type="danger"
              circle
              :disabled="createForm.stops.length === 1"
              @click="createForm.stops.splice(index, 1)"
            >✕</el-button>
          </div>
          <el-button size="small" class="add-item-btn" @click="addStopRow">
            <el-icon><Plus /></el-icon> 加一站
          </el-button>
          <p class="form-hint">天数可以留空（显示「天数待定」），0 表示路过不过夜。</p>
        </template>
        <p v-else class="form-hint">站点调整在列表里做：展开计划后可加站、改天数、上下移、删站。</p>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePlan">{{ editingPlanId ? '保存' : '创建计划' }}</el-button>
      </template>
    </el-dialog>

    <!-- 计划内地图：按站序连线，点城市看这一站的预算与清单 -->
    <el-drawer
      v-model="mapVisible"
      :title="mapTitle"
      size="82%"
      append-to-body
      destroy-on-close
      class="map-drawer"
    >
      <div v-loading="mapLoading" class="map-body">
        <PlanRouteMap v-if="mapPlan" :plan="mapPlan" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { apiErrorText } from '@/shared/utils/apiError'
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, ArrowDown } from '@element-plus/icons-vue'
import * as api from '../api/travelApi'
import { formatAmount } from '@/shared/utils/format'
import { useMenuArchive } from '@/shared/composables/useMenuArchive'
import PlanStopList from '../components/plan/PlanStopList.vue'
import PlanRouteMap from '../components/plan/PlanRouteMap.vue'
import type { TravelPlan, TravelPlanInput, TravelPlanItemInput, TravelPlanStats } from '../types/travelTypes'

// 归档横幅的判据唯一实现在 useMenuArchive（存档态含用户偏好，非写死的 defaultArchived）
const { ready, isArchived } = useMenuArchive('travel')

const plans = ref<TravelPlan[]>([])
const stats = ref<TravelPlanStats | null>(null)
const loading = ref(false)
const expandedPlanId = ref<number | null>(null)
/** 展开的那条计划的**详情**（带站点条目）；列表数据里没有条目 */
const expandedPlan = ref<TravelPlan | null>(null)
const expandedLoading = ref(false)
const copyingId = ref<number | null>(null)

/** 计划地图抽屉（点「🗺 地图」）：详情单独持有一份，与展开面板互不影响 */
const mapVisible = ref(false)
const mapLoading = ref(false)
const mapPlan = ref<TravelPlan | null>(null)
const mapTitle = computed(() => (mapPlan.value ? `🗺 ${mapPlan.value.name}` : '🗺 路线地图'))

const showCreateDialog = ref(false)
const saving = ref(false)
const editingPlanId = ref<number | null>(null)
const createForm = reactive<{
  name: string
  start_date: string | null
  stops: { city: string; days: number | null }[]
}>({
  name: '',
  start_date: null,
  stops: [],
})

function fmt(n: unknown): string {
  return formatAmount(Number(n ?? 0), 2)
}

function getStatusType(status: string): string {
  if (status === '进行中') return 'warning'
  if (status === '已完成') return 'success'
  if (status === '已取消') return 'info'
  return ''
}

/** 完整路线串（悬浮提示用） */
function fullRoute(plan: TravelPlan): string {
  const cities = plan.stops.map((s) => s.city_input)
  if (!cities.length) return plan.destination || '还没排站'
  return cities.join(' → ')
}

/** 折叠后的路线串：超过 3 站只留首尾 —— 一行塞 5 个城市会把状态标签挤走 */
function routeText(plan: TravelPlan): string {
  const cities = plan.stops.map((s) => s.city_input)
  if (cities.length === 0) return plan.destination || '还没排站'
  if (cities.length <= 3) return cities.join(' → ')
  return `${cities[0]} → ${cities[1]} → … → ${cities[cities.length - 1]}`
}

/** `5 站 · 8 天 · ¥4,860`；某站天数没填时「天数待定」，不把 null 当 0 加 */
function metaText(plan: TravelPlan): string {
  const stops = `${plan.stops.length} 站`
  const days = plan.total_days === null ? '天数待定' : `${plan.total_days} 天`
  return `${stops} · ${days} · ¥${fmt(plan.total_estimate)}`
}

// ===== 弹窗 =====
function addStopRow() {
  createForm.stops.push({ city: '', days: null })
}

function resetCreateForm() {
  createForm.name = ''
  createForm.start_date = null
  createForm.stops = []
}

function openCreateDialog() {
  resetCreateForm()
  editingPlanId.value = null
  addStopRow()
  showCreateDialog.value = true
}

function editPlan(plan: TravelPlan) {
  resetCreateForm()
  editingPlanId.value = plan.id
  createForm.name = plan.name
  createForm.start_date = plan.start_date
  showCreateDialog.value = true
}

/**
 * 复制计划：一次请求把整条路线（站 + 条目）带过去。
 *
 * ⚠️ 刻意**不弹表单**让你改一遍再存：复制是最不需要思考的动作，
 *    而弹窗里改站点会让条目的 `stop_index` 与站点错位（400 或挂错城市）。
 *    想改名复制完点「编辑」即可。
 */
async function copyPlan(plan: TravelPlan) {
  copyingId.value = plan.id
  try {
    const detail = (await api.getTravelPlanDetail(plan.id)).data as TravelPlan
    const stops = detail.stops.map((s) => ({ city: s.city_input, days: s.days }))
    const items: TravelPlanItemInput[] = []
    detail.stops.forEach((stop, index) => {
      ;(stop.items || []).forEach((it) => {
        items.push({
          item_type: it.item_type,
          name: it.name,
          estimate_cost: it.estimate_cost,
          notes: it.notes,
          stop_index: index,
        })
      })
    })
    // 城际交通（`stop: null`）：新建时没有站点 id 可指，只能落到「路上」
    detail.transfer_items.forEach((it) => {
      items.push({ item_type: it.item_type, name: it.name, estimate_cost: it.estimate_cost, notes: it.notes })
    })
    const payload: TravelPlanInput = {
      name: `${detail.name}（副本）`,
      start_date: detail.start_date,
      stops,
      items,
    }
    await api.createTravelPlan(payload)
    ElMessage.success('已复制')
    await refreshAfterChange()
  } catch (err) {
    ElMessage.error(apiErrorText(err, '复制失败'))
  } finally {
    copyingId.value = null
  }
}

async function savePlan() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请填写计划名称')
    return
  }
  const stops = createForm.stops
    .map((s) => ({ city: s.city.trim(), days: s.days }))
    .filter((s) => s.city)

  saving.value = true
  try {
    if (editingPlanId.value) {
      // 🔴 用 PATCH：非 partial 的 PUT 会把没传的 `status` / `notes` 重置成默认值
      await api.updateTravelPlan(editingPlanId.value, {
        name: createForm.name.trim(),
        start_date: createForm.start_date,
      })
      ElMessage.success('已更新')
    } else {
      if (stops.length === 0) {
        ElMessage.warning('至少填一站')
        saving.value = false
        return
      }
      await api.createTravelPlan({
        name: createForm.name.trim(),
        start_date: createForm.start_date,
        stops,
      })
      ElMessage.success('已创建')
    }
    showCreateDialog.value = false
    editingPlanId.value = null
    resetCreateForm()
    await refreshAfterChange()
  } catch (err) {
    ElMessage.error(apiErrorText(err, '保存失败'))
  } finally {
    saving.value = false
  }
}

// ===== 列表 =====
/**
 * 拉计划列表 + 统计。
 *
 * `silent` 用于「改完某条计划后刷新」：不带 loading 遮罩 —— 列表页的
 * loading 会在顶部插一块占位，每勾一次条目就跳一下，比不刷新还难看。
 */
async function fetchAll(silent = false) {
  if (!silent) loading.value = true
  try {
    const [planRes, statsRes] = await Promise.all([api.getTravelPlans(), api.getTravelPlanStats()])
    plans.value = planRes.data?.results ?? planRes.data ?? []
    stats.value = statsRes.data
  } catch {
    ElMessage.error('加载旅行计划失败')
  } finally {
    loading.value = false
  }
}

/**
 * 展开计划时才取详情。
 *
 * 🔴 列表接口**不带站点条目**（省掉 100+ 条子项的查询）：直接拿列表数据展开，
 *    每一站都是「还没有条目」，看着像数据丢了。详情与列表是两个接口，别混用。
 */
async function togglePlan(plan: TravelPlan) {
  if (expandedPlanId.value === plan.id) {
    expandedPlanId.value = null
    expandedPlan.value = null
    return
  }
  expandedPlanId.value = plan.id
  expandedPlan.value = null
  expandedLoading.value = true
  try {
    expandedPlan.value = (await api.getTravelPlanDetail(plan.id)).data as TravelPlan
  } catch {
    ElMessage.error('加载计划详情失败')
    expandedPlanId.value = null
  } finally {
    expandedLoading.value = false
  }
}

/** 计划内改完（加站/改天数/勾条目/删条目）⇒ 列表汇总与详情一起刷新 */
async function refreshExpanded() {
  const id = expandedPlanId.value
  await fetchAll(true)
  if (id == null) return
  try {
    expandedPlan.value = (await api.getTravelPlanDetail(id)).data as TravelPlan
  } catch {
    ElMessage.error('刷新计划详情失败')
  }
}

/** 新建/编辑/复制/删除之后：展开中的那条连详情一起刷，否则只刷列表 */
async function refreshAfterChange() {
  if (expandedPlanId.value != null) await refreshExpanded()
  else await fetchAll(true)
}

/**
 * 打开计划地图：按站序连线，点城市看这一站的预算与清单。
 *
 * 🔴 详情**单独取**，不复用 `expandedPlan`：列表对象里根本没有 `items`，
 *    而展开面板可能压根没打开（拿列表数据画图 ⇒ 每一站都「还没排条目」）。
 *    两处各取一份也更安全 —— 地图只读，改数据仍走清单。
 */
async function openPlanMap(plan: TravelPlan) {
  if (!plan.stops.length) {
    ElMessage.warning('该计划还没有站点，先排上城市再看地图')
    return
  }
  mapPlan.value = null
  mapVisible.value = true
  mapLoading.value = true
  try {
    mapPlan.value = (await api.getTravelPlanDetail(plan.id)).data as TravelPlan
  } catch {
    ElMessage.error('加载计划详情失败')
    mapVisible.value = false
  } finally {
    mapLoading.value = false
  }
}

async function deletePlan(id: number) {
  try {
    await ElMessageBox.confirm('确定删除这个旅行计划吗？站点与条目会一起删除。', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await api.deleteTravelPlan(id)
    // 删的正是展开中的那条 ⇒ 一起收起，否则详情面板挂在一条已不存在的计划上
    if (expandedPlanId.value === id) {
      expandedPlanId.value = null
      expandedPlan.value = null
    }
    ElMessage.success('已删除')
    await fetchAll(true)
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(fetchAll)
</script>

<style scoped lang="scss">
.travel-plan {
  padding: 24px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;

    .header-left {
      h1 {
        font-size: 22px;
        font-weight: 700;
        color: #1F2937;
        margin: 0 0 6px 0;

        .header-icon { margin-right: 8px; }
      }
      .header-desc {
        font-size: 13px;
        color: #9CA3AF;
        margin: 0;
      }
    }

    // 两个页内入口 + 主操作并排（align-items:flex-start 下要靠这层统一对齐）
    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }

  .stats-row {
    margin-bottom: 20px;

    .stat-card {
      border: none;
      border-radius: 10px;

      .stat-value {
        font-size: 24px;
        font-weight: 700;
        color: #1F2937;
        text-align: center;
        padding-top: 6px;
      }
      .stat-label {
        font-size: 13px;
        color: #6B7280;
        margin-top: 4px;
        text-align: center;
        padding-bottom: 6px;
      }
      .text-warning { color: #E6A23C; }
      .text-success { color: #67C23A; }
    }
  }

  .plans-card {
    border: none;
    border-radius: 10px;

    .list-loading {
      min-height: 120px;
    }
    .empty {
      padding: 12px 0;
    }

    .plan-card {
      border: 1px solid #f0f0f0;
      border-radius: 8px;
      margin-bottom: 12px;
      overflow: hidden;

      .plan-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        transition: background 0.2s;

        &:hover { background: #f9fafb; }

        .plan-info {
          display: flex;
          align-items: center;
          gap: 12px;
          min-width: 0;
          cursor: pointer;
          flex: 1;

          .plan-name {
            font-size: 15px;
            font-weight: 600;
            color: #1F2937;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 220px;
          }

          // 路线串是内容不是链接：用蓝色会被当成「点这里看路线」（真的点整行是展开）
          .plan-route {
            font-size: 13px;
            color: #606266;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }

          .plan-meta { font-size: 13px; color: #6b7280; white-space: nowrap; }
          .plan-date { font-size: 12px; color: #9CA3AF; white-space: nowrap; }

          .expand-icon {
            color: #9CA3AF;
            transition: transform 0.2s;
            flex-shrink: 0;

            &.expanded { transform: rotate(180deg); }
          }
        }

        .plan-actions {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-shrink: 0;
        }
      }

      // 详情拉取中的占位：不留高度的话，展开瞬间会先塌一下再撑开
      .plan-detail {
        min-height: 64px;
      }
    }
  }
}

/* 站点行在 append-to-body 弹窗内（teleport 到 body），不能依赖 .travel-plan 祖先，需顶层作用域 */
.stop-edit-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  .stop-index {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    line-height: 20px;
    text-align: center;
    border-radius: 50%;
    background: #ecf5ff;
    color: #409eff;
    font-size: 12px;
    font-weight: 600;
  }

  .stop-city-input { flex: 1; min-width: 140px; }
  .stop-days-input { width: 130px; flex-shrink: 0; }
}

.add-item-btn {
  margin-top: 4px;
}

.form-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #9ca3af;
}

/* 地图抽屉 append-to-body（挂到 body 上），样式作用域不能嵌在 .travel-plan 里 */
.map-body {
  flex: 1;
  min-height: 0;
  display: flex;
}
</style>

<style>
/* 🔴 抽屉是 teleport 到 body 的，scoped 的 `:deep(.el-drawer__body)` 够不到
   （.map-drawer 上根本没有 data-v 属性 ⇒ 规则静默失效，画布高度塌成 400px）。
   所以单独一段**非 scoped** 样式，选择器收窄到 .map-drawer，不污染全局。 */
.map-drawer .el-drawer__body {
  padding: 0;
  display: flex;
  overflow: hidden;
}
</style>
