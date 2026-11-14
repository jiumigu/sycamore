<template>
  <div class="stop-list">
    <!-- 站点：按 order 排好的路线 -->
    <PlanStopRow
      v-for="(stop, i) in plan.stops"
      :key="stop.id"
      :plan-id="plan.id"
      :stop="stop"
      :index="i"
      :total="plan.stops.length"
      :move-targets="moveTargets"
      @changed="$emit('changed')"
      @move="moveStop(stop.id, $event)"
      @remove="removeStop(stop)"
      @toggle-item="toggleItem"
      @remove-item="removeItem"
      @move-item="relocateItem"
    />
    <div v-if="plan.stops.length === 0" class="empty-stops">
      这条路线还没有站 —— 在下面加第一站，比如「泉州」
    </div>

    <!-- 加一站 -->
    <div class="add-stop-row">
      <el-input
        v-model="newStop.city"
        size="small"
        placeholder="加一站，如：泉州"
        class="add-city"
        @keyup.enter="submitStop"
      />
      <el-input-number
        v-model="newStop.days"
        :min="0"
        :precision="0"
        size="small"
        controls-position="right"
        placeholder="待几天"
        class="add-days"
      />
      <el-button size="small" type="primary" :loading="addingStop" @click="submitStop">加一站</el-button>
      <span class="add-hint">天数留空也能加，之后在站上补</span>
    </div>

    <!-- 路上（城际交通） -->
    <div class="transfer-block">
      <div class="transfer-head">
        <span class="transfer-title">🚄 路上（城际交通）</span>
        <span class="transfer-cost">¥{{ fmt(plan.transfer_total) }}</span>
        <span class="transfer-hint">不归属任何城市，不计入各站合计</span>
      </div>
      <PlanItemRow
        v-for="item in plan.transfer_items"
        :key="item.id"
        :item="item"
        :move-targets="moveTargets"
        @toggle="toggleItem(item)"
        @remove="removeItem(item)"
        @move-to="(target: number | null) => relocateItem(item, target)"
      />
      <div v-if="plan.transfer_items.length === 0" class="no-transfer">
        没有城际交通条目 —— 高铁 / 机票 / 自驾过路费记在这里，各站数字才干净
      </div>
      <div class="add-transfer-row">
        <el-select v-model="newTransfer.item_type" size="small" class="transfer-type">
          <el-option v-for="t in TRAVEL_PLAN_ITEM_TYPES" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-input
          v-model="newTransfer.name"
          size="small"
          placeholder="如：宁德→泉州 高铁"
          class="transfer-name"
          @keyup.enter="submitTransfer"
        />
        <el-input-number
          v-model="newTransfer.estimate_cost"
          :min="0"
          :precision="2"
          size="small"
          controls-position="right"
          class="transfer-cost-input"
        />
        <el-button size="small" :loading="addingTransfer" @click="submitTransfer">添加</el-button>
      </div>
    </div>

    <!-- 三层合计：各站 + 路上 = 全程（就是总额，别处不再加一遍） -->
    <div class="totals-bar">
      <span>各站合计 <b>¥{{ fmt(plan.stops_total) }}</b></span>
      <span class="op">＋</span>
      <span>路上 <b>¥{{ fmt(plan.transfer_total) }}</b></span>
      <span class="op">＝</span>
      <span>全程 <b class="grand">¥{{ fmt(plan.total_estimate) }}</b></span>
    </div>

    <!-- 打卡录入：整份列表只留一个弹窗（每个条目一个会白挂 100 多个实例） -->
    <el-dialog v-model="visitVisible" title="打卡记录" width="460px" :close-on-click-modal="false" append-to-body>
      <div v-if="visitItem" class="visit-item-name">{{ iconOf(visitItem.item_type) }} {{ visitItem.name }}</div>
      <p class="visit-tip">记录后会自动写入「旅行足迹 → 行程日志」，也可跳过只打卡。</p>
      <el-form label-width="90px">
        <el-form-item label="打卡日期">
          <el-date-picker v-model="visitForm.visited_at" type="date" value-format="YYYY-MM-DD" placeholder="默认今天" style="width: 100%" />
        </el-form-item>
        <el-form-item label="评分">
          <el-rate v-model="visitForm.visit_rating" :texts="RATE_TEXTS" show-text clearable />
        </el-form-item>
        <el-form-item label="打卡评价">
          <el-input v-model="visitForm.visit_notes" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="味道 / 体验 / 值不值得排队的真实感受…" />
        </el-form-item>
        <el-form-item label="值得反复">
          <el-switch v-model="visitForm.worth_revisit" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visitVisible = false">取消</el-button>
        <el-button :loading="visitSaving" @click="confirmVisit(false)">只打卡</el-button>
        <el-button type="primary" :loading="visitSaving" @click="confirmVisit(true)">打卡并记录</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiErrorText } from '@/shared/utils/apiError'
import { formatAmount } from '@/shared/utils/format'
import { todayLocal } from '@/shared/utils/datetime'
import PlanItemRow from './PlanItemRow.vue'
import PlanStopRow from './PlanStopRow.vue'
import * as api from '../../api/travelApi'
import {
  TRAVEL_PLAN_ITEM_TYPES,
  type TravelPlan,
  type TravelPlanItem,
  type TravelPlanItemType,
  type TravelPlanStop,
} from '../../types/travelTypes'

const props = defineProps<{ plan: TravelPlan }>()
const emit = defineEmits<{ changed: [] }>()

const fmt = (n: unknown) => formatAmount(Number(n ?? 0), 2)

function iconOf(type: string): string {
  const hit = TRAVEL_PLAN_ITEM_TYPES.find((t) => t.value === type)
  return hit ? hit.label.split(' ')[0] : '📌'
}

/** 后端 400 里带的 `blocking`（挡着删除的那几条）也读出来，不只剩一句「失败」 */
function errText(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: { error?: string; blocking?: { name: string }[] } } })
    ?.response?.data
  if (!data?.error) return apiErrorText(err, fallback)
  const names = (data.blocking || []).map((b) => b.name).join('、')
  return names ? `${data.error}：${names}…（先挪走或删掉再删站）` : data.error
}

// ===== 加站 =====
const addingStop = ref(false)
const newStop = reactive<{ city: string; days: number | null }>({ city: '', days: null })

/** 条目「挪到别站」的可选目标：整条路线一份，逐行传下去 */
const moveTargets = computed(() =>
  props.plan.stops.map((s, i) => ({ id: s.id, label: `${i + 1}. ${s.city_input}` })),
)

/**
 * 把条目挪到别站 / 挪到路上。
 *
 * 删站被条目挡住时（后端 400），提示语里让用户「先挪走」—— 这里就是那个出口，
 * 没有它，唯一的选择是删掉条目，等于强迫用户丢数据。
 */
async function relocateItem(item: TravelPlanItem, target: number | null) {
  const to = target === null
    ? '路上（城际交通）'
    : (props.plan.stops.find((s) => s.id === target)?.city_input ?? '另一站')
  try {
    await api.movePlanItem(props.plan.id, item.id, target)
    ElMessage.success(`「${item.name}」已挪到${to}`)
    emit('changed')
  } catch (err) {
    ElMessage.error(apiErrorText(err, '挪动失败'))
  }
}

async function submitStop() {
  const city = newStop.city.trim()
  if (!city) {
    ElMessage.warning('先填城市名')
    return
  }
  addingStop.value = true
  try {
    await api.addPlanStop(props.plan.id, { city, days: newStop.days })
    newStop.city = ''
    newStop.days = null
    ElMessage.success(`已加一站：${city}`)
    emit('changed')
  } catch (err) {
    ElMessage.error(apiErrorText(err, '加站失败'))
  } finally {
    addingStop.value = false
  }
}

// ===== 顺序 =====
async function moveStop(stopId: number, delta: number) {
  const ids = props.plan.stops.map((s) => s.id)
  const from = ids.indexOf(stopId)
  const to = from + delta
  if (from < 0 || to < 0 || to >= ids.length) return
  ;[ids[from], ids[to]] = [ids[to], ids[from]]
  try {
    // 🔴 整份给 id：只给一半会留下空洞顺序，下次加站又得猜一次 order
    await api.reorderPlanStops(props.plan.id, ids)
    emit('changed')
  } catch (err) {
    ElMessage.error(apiErrorText(err, '调整顺序失败'))
  }
}

// ===== 删站 =====
async function removeStop(stop: TravelPlanStop) {
  try {
    await ElMessageBox.confirm(
      `删除「${stop.city_input}」这一站？站下的 ${stop.items?.length ?? 0} 条条目会先拦住删除。`,
      '确认删除站点',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await api.deletePlanStop(props.plan.id, stop.id)
    ElMessage.success('已删除该站')
    emit('changed')
  } catch (err) {
    ElMessage.error(errText(err, '删除失败'))
  }
}

// ===== 条目：勾完成 / 删除 =====
const RATE_TEXTS = ['踩雷', '一般', '还行', '不错', '值得专程去']
const visitVisible = ref(false)
const visitSaving = ref(false)
const visitItem = ref<TravelPlanItem | null>(null)
const visitForm = reactive({
  visited_at: '',
  visit_rating: 0,
  visit_notes: '',
  worth_revisit: false,
})

function toggleItem(item: TravelPlanItem) {
  // 未完成 → 完成 且带心愿：先问打卡详情（可跳过），保证行程日志字段完整
  if (!item.is_completed && item.wish) {
    visitItem.value = item
    visitForm.visited_at = todayLocal()
    visitForm.visit_rating = 0
    visitForm.visit_notes = ''
    visitForm.worth_revisit = false
    visitVisible.value = true
    return
  }
  void doToggle(item)
}

async function doToggle(item: TravelPlanItem) {
  try {
    await api.toggleTravelPlanItem(props.plan.id, item.id)
    emit('changed')
  } catch {
    ElMessage.error('操作失败')
  }
}

async function confirmVisit(withRecord: boolean) {
  const item = visitItem.value
  if (!item) return
  visitSaving.value = true
  try {
    if (withRecord && item.wish) {
      await api.recordWishVisit(item.wish, {
        visited_at: visitForm.visited_at || todayLocal(),
        visit_rating: visitForm.visit_rating || null,
        visit_notes: visitForm.visit_notes,
        worth_revisit: visitForm.worth_revisit,
      })
    }
    await api.toggleTravelPlanItem(props.plan.id, item.id)
    visitVisible.value = false
    ElMessage.success(withRecord ? '已打卡并记录' : '已打卡')
    emit('changed')
  } catch (e: unknown) {
    ElMessage.error(apiErrorText(e, '打卡失败'))
  } finally {
    visitSaving.value = false
  }
}

async function removeItem(item: TravelPlanItem) {
  try {
    await ElMessageBox.confirm(`删除「${item.name}」？`, '确认删除条目', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await api.deletePlanItem(props.plan.id, item.id)
    ElMessage.success('已删除')
    emit('changed')
  } catch (err) {
    ElMessage.error(apiErrorText(err, '删除失败'))
  }
}

// ===== 城际交通 =====
const addingTransfer = ref(false)
const newTransfer = reactive<{
  item_type: TravelPlanItemType
  name: string
  estimate_cost: number | null
}>({ item_type: 'transport', name: '', estimate_cost: null })

async function submitTransfer() {
  const name = newTransfer.name.trim()
  if (!name) {
    ElMessage.warning('先写一下名称')
    return
  }
  addingTransfer.value = true
  try {
    // 🔴 显式 `stop: null` = 路上。少传这个键会被默认挂到唯一的站上（单站计划）
    await api.addPlanItem(props.plan.id, {
      item_type: newTransfer.item_type,
      name,
      estimate_cost: newTransfer.estimate_cost ?? 0,
      stop: null,
    })
    newTransfer.name = ''
    newTransfer.estimate_cost = null
    ElMessage.success('已添加')
    emit('changed')
  } catch (err) {
    ElMessage.error(apiErrorText(err, '添加失败'))
  } finally {
    addingTransfer.value = false
  }
}
</script>

<style scoped lang="scss">
.stop-list {
  border-top: 1px solid #f0f0f0;
  background: #fafbfc;
  padding-bottom: 8px;

  .empty-stops {
    padding: 18px 16px;
    font-size: 13px;
    color: #9ca3af;
  }

  .add-stop-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-top: 1px dashed #eef0f3;

    .add-city { width: 200px; }
    .add-days { width: 120px; }
    .add-hint { font-size: 12px; color: #9ca3af; }
  }

  .transfer-block {
    margin: 4px 16px 0;
    border: 1px solid #f0f0f0;
    border-radius: 8px;
    background: #fff;
    padding: 8px 12px 10px;

    .transfer-head {
      display: flex;
      align-items: center;
      gap: 10px;
      padding-bottom: 4px;

      .transfer-title { font-size: 13px; font-weight: 600; color: #1f2937; }
      .transfer-cost { font-size: 14px; font-weight: 700; color: #e6a23c; }
      .transfer-hint { font-size: 12px; color: #9ca3af; }
    }

    .no-transfer {
      padding: 4px 0;
      font-size: 12px;
      color: #9ca3af;
    }

    .add-transfer-row {
      display: flex;
      align-items: center;
      gap: 8px;
      padding-top: 6px;

      .transfer-type { width: 104px; flex-shrink: 0; }
      .transfer-name { flex: 1; min-width: 140px; }
      .transfer-cost-input { width: 120px; flex-shrink: 0; }
    }
  }

  .totals-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 10px 16px 2px;
    padding: 8px 12px;
    background: #f5f7fa;
    border-radius: 8px;
    font-size: 13px;
    color: #606266;

    b { color: #303133; font-weight: 600; }
    .grand { color: #e6a23c; font-size: 15px; }
    .op { color: #9ca3af; }
  }
}

.visit-item-name {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 500;
  color: #1f2937;
}

.visit-tip {
  margin: 6px 0 16px;
  font-size: 12px;
  color: #9ca3af;
}
</style>
