<template>
  <div class="stop-row">
    <!-- 站头：城市 / 天数 / 到达 / 本站合计 / 四类计数 -->
    <div class="stop-head">
      <span class="stop-order">{{ index + 1 }}</span>
      <span class="stop-city">
        {{ stop.city_input }}
        <el-tooltip
          v-if="!stop.located"
          content="城市名没在坐标表里找到，地图上不显示；改个常见写法（如「泉州」）试试"
          placement="top"
        >
          <el-tag size="small" type="warning" effect="plain">未定位</el-tag>
        </el-tooltip>
      </span>
      <span class="stop-meta">{{ daysLabel(stop.days) }}</span>
      <span class="stop-meta">{{ arriveLabel(stop.arrive_date) }}</span>
      <span class="stop-subtotal">¥{{ fmt(stop.subtotal) }}</span>
      <span class="stop-counts">
        <span v-for="c in countChips(stop)" :key="c.key" class="count-chip">{{ c.icon }}{{ c.n }}</span>
      </span>
      <span class="stop-actions">
        <el-tooltip content="上移一站" placement="top">
          <el-button link :disabled="index === 0" @click="$emit('move', -1)">
            <el-icon><Top /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="下移一站" placement="top">
          <el-button link :disabled="index === total - 1" @click="$emit('move', 1)">
            <el-icon><Bottom /></el-icon>
          </el-button>
        </el-tooltip>
        <el-button link @click="startEdit">编辑</el-button>
        <el-button link type="danger" @click="$emit('remove')">删除</el-button>
        <el-button link @click="expanded = !expanded">
          <el-icon class="expand-icon" :class="{ expanded }"><ArrowDown /></el-icon>
        </el-button>
      </span>
    </div>

    <!-- 行内编辑：只改「城市 + 待几天」 -->
    <div v-if="editing" class="stop-edit">
      <el-input v-model="editForm.city" size="small" placeholder="城市，如：泉州" class="edit-city" />
      <el-input-number
        v-model="editForm.days"
        :min="0"
        :precision="0"
        size="small"
        controls-position="right"
        placeholder="待几天"
        class="edit-days"
      />
      <span class="edit-hint">留空 = 天数待定；0 = 路过不过夜</span>
      <el-button size="small" @click="editing = false">取消</el-button>
      <el-button size="small" type="primary" :loading="saving" @click="saveEdit">保存</el-button>
    </div>

    <!-- 条目 -->
    <div v-if="expanded" class="stop-body">
      <PlanItemRow
        v-for="item in stop.items || []"
        :key="item.id"
        :item="item"
        :move-targets="moveTargets"
        @toggle="$emit('toggle-item', item)"
        @remove="$emit('remove-item', item)"
        @move-to="(target: number | null) => $emit('move-item', item, target)"
      />
      <div v-if="!stop.items || stop.items.length === 0" class="no-items">
        这一站还没有条目 —— 在下面加「吃什么 / 打卡哪 / 住哪 / 当地交通」
      </div>

      <div class="add-item-row">
        <el-select v-model="newItem.item_type" size="small" class="new-type">
          <el-option v-for="t in TRAVEL_PLAN_ITEM_TYPES" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-input
          v-model="newItem.name"
          size="small"
          placeholder="名称，如：牛肉清汤粉"
          class="new-name"
          @keyup.enter="submitItem"
        />
        <el-input-number
          v-model="newItem.estimate_cost"
          :min="0"
          :precision="2"
          size="small"
          controls-position="right"
          class="new-cost"
        />
        <el-button size="small" type="primary" :loading="adding" @click="submitItem">添加</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, Bottom, Top } from '@element-plus/icons-vue'
import { apiErrorText } from '@/shared/utils/apiError'
import { formatAmount } from '@/shared/utils/format'
import PlanItemRow from './PlanItemRow.vue'
import * as api from '../../api/travelApi'
import { arriveLabel, countChips, daysLabel } from '../../utils/stopText'
import {
  TRAVEL_PLAN_ITEM_TYPES,
  type TravelPlanItem,
  type TravelPlanItemType,
  type TravelPlanStop,
} from '../../types/travelTypes'

const props = defineProps<{
  planId: number
  stop: TravelPlanStop
  index: number
  total: number
  /** 条目「挪到别站」的可选目标（整条路线的站，序号 + 城市名） */
  moveTargets?: { id: number; label: string }[]
}>()

const emit = defineEmits<{
  changed: []
  move: [delta: number]
  remove: []
  'toggle-item': [item: TravelPlanItem]
  'remove-item': [item: TravelPlanItem]
  'move-item': [item: TravelPlanItem, target: number | null]
}>()

/** 只有第一站默认展开：一进来全部摊开，5 站 × 20 条会看不到路线本身 */
const expanded = ref(props.index === 0)

const fmt = (n: unknown) => formatAmount(Number(n ?? 0), 2)

// 天数 / 到达日期 / 四类计数的文案与图标统一在 utils/stopText（地图侧栏共用一份）


// ===== 站点行内编辑 =====
const editing = ref(false)
const saving = ref(false)
const editForm = reactive<{ city: string; days: number | null }>({ city: '', days: null })

function startEdit() {
  // 🔴 回填用 `city_input`（用户填的原样），用 `city` 会把「泉州」改成「泉州市」
  editForm.city = props.stop.city_input
  editForm.days = props.stop.days
  editing.value = true
}

async function saveEdit() {
  const city = editForm.city.trim()
  if (!city) {
    ElMessage.warning('城市名不能为空')
    return
  }
  if (city === props.stop.city_input && editForm.days === props.stop.days) {
    editing.value = false
    return
  }
  saving.value = true
  try {
    await api.updatePlanStop(props.planId, props.stop.id, { city, days: editForm.days })
    editing.value = false
    ElMessage.success('已保存')
    emit('changed')
  } catch (err) {
    ElMessage.error(apiErrorText(err, '保存失败'))
  } finally {
    saving.value = false
  }
}

// ===== 加条目 =====
const adding = ref(false)
const newItem = reactive<{
  item_type: TravelPlanItemType
  name: string
  estimate_cost: number | null
}>({ item_type: 'food', name: '', estimate_cost: null })

async function submitItem() {
  const name = newItem.name.trim()
  if (!name) {
    ElMessage.warning('先写一下名称')
    return
  }
  adding.value = true
  try {
    // 🔴 显式带 `stop`：多站计划里不写它就会掉进「路上」，钱跑到城际交通里
    await api.addPlanItem(props.planId, {
      item_type: newItem.item_type,
      name,
      estimate_cost: newItem.estimate_cost ?? 0,
      stop: props.stop.id,
    })
    newItem.name = ''
    newItem.estimate_cost = null
    ElMessage.success('已添加')
    emit('changed')
  } catch (err) {
    ElMessage.error(apiErrorText(err, '添加失败'))
  } finally {
    adding.value = false
  }
}
</script>

<style scoped lang="scss">
.stop-row {
  border-bottom: 1px dashed #eef0f3;

  &:last-child { border-bottom: none; }

  .stop-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 16px 8px 12px;
    font-size: 13px;

    &:hover { background: #f7f9fc; }

    .stop-order {
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

    .stop-city {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 14px;
      font-weight: 600;
      color: #1f2937;
      min-width: 76px;
    }

    .stop-meta { color: #6b7280; flex-shrink: 0; }

    .stop-subtotal {
      font-size: 14px;
      font-weight: 700;
      color: #e6a23c;
      min-width: 76px;
    }

    .stop-counts {
      display: flex;
      gap: 6px;
      flex: 1;
      min-width: 0;

      .count-chip {
        font-size: 12px;
        color: #606266;
        background: #f3f4f6;
        border-radius: 9px;
        padding: 0 7px;
        line-height: 18px;
      }
    }

    .stop-actions {
      display: flex;
      align-items: center;
      gap: 2px;
      flex-shrink: 0;

      .expand-icon {
        color: #9ca3af;
        transition: transform 0.2s;
        &.expanded { transform: rotate(180deg); }
      }
    }
  }

  .stop-edit {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px 10px 42px;
    background: #fafbfc;

    .edit-city { width: 160px; }
    .edit-days { width: 120px; }
    .edit-hint { font-size: 12px; color: #9ca3af; flex: 1; }
  }

  .stop-body {
    padding: 2px 0 10px 42px;
    background: #fafbfc;

    .no-items {
      padding: 8px 0;
      font-size: 12px;
      color: #9ca3af;
    }

    .add-item-row {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px 0 0;

      .new-type { width: 104px; flex-shrink: 0; }
      .new-name { flex: 1; min-width: 140px; }
      .new-cost { width: 120px; flex-shrink: 0; }
    }
  }
}
</style>
