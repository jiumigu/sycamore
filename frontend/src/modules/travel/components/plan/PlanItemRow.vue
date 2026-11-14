<template>
  <div class="item-row" :class="{ completed: item.is_completed }">
    <el-checkbox :model-value="item.is_completed" @change="$emit('toggle')" />
    <span class="item-icon">{{ icon }}</span>
    <span class="item-name">{{ item.name }}</span>
    <el-tooltip v-if="item.wish" content="由旅行心愿单带入；勾完成时会问你要不要顺手记录打卡" placement="top">
      <span class="item-wish-tag">心愿</span>
    </el-tooltip>
    <span class="item-cost">¥{{ fmt(item.estimate_cost) }}</span>
    <!-- 挪到别站：删站被条目挡住时提示「先挪走」，这里就是那个出口 -->
    <!-- ⚠️ trigger 只放一个按钮：外面再包 el-tooltip 会让下拉拿不到定位锚点 -->
    <span class="item-move" @click.stop>
      <el-dropdown trigger="click" placement="bottom-end" @command="onMove">
        <el-button link class="move-btn" title="挪到别站 / 挪到路上">
          <el-icon><Sort /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="t in moveTargets"
              :key="t.id"
              :command="t.id"
              :disabled="t.id === item.stop"
            >
              {{ t.label }}<span v-if="t.id === item.stop" class="here">（就在这）</span>
            </el-dropdown-item>
            <el-dropdown-item v-if="item.stop != null" command="on-the-way" divided>
              🚄 挪到路上（城际交通）
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </span>
    <el-tooltip content="删除这条" placement="top">
      <el-button link class="item-remove" @click="$emit('remove')">
        <el-icon><Close /></el-icon>
      </el-button>
    </el-tooltip>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Close, Sort } from '@element-plus/icons-vue'
import { formatAmount } from '@/shared/utils/format'
import { TRAVEL_PLAN_ITEM_TYPES, type TravelPlanItem } from '../../types/travelTypes'

const props = defineProps<{
  item: TravelPlanItem
  /** 可挪去的站（含序号的城市名）；空数组 = 这计划只有一站，不显示挪动入口 */
  moveTargets?: { id: number; label: string }[]
}>()

const emit = defineEmits<{ toggle: []; remove: []; 'move-to': [target: number | null] }>()

const fmt = (n: unknown) => formatAmount(Number(n ?? 0), 2)

const icon = computed(() => {
  const hit = TRAVEL_PLAN_ITEM_TYPES.find((t) => t.value === props.item.item_type)
  return hit ? hit.label.split(' ')[0] : '📌'
})

/** `on-the-way` 是字符串指令（站 id 是数字，不会撞） */
function onMove(cmd: number | string) {
  const target = cmd === 'on-the-way' ? null : Number(cmd)
  // 挪到自己身上等于没动：不打扰后端
  if (target === props.item.stop) return
  emit('move-to', target)
}
</script>

<style scoped lang="scss">
.item-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px 6px 0;

  &.completed .item-name { color: #9ca3af; text-decoration: line-through; }
  &.completed .item-cost { color: #c0c4cc; }

  .item-icon { font-size: 15px; }
  .item-name { flex: 1; font-size: 14px; color: #1f2937; }

  .item-wish-tag {
    font-size: 11px;
    color: #909399;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    padding: 0 6px;
  }

  .item-cost { font-size: 13px; font-weight: 600; color: #606266; }

  // 低频动作默认淡出，悬停整行才显形（常驻一排图标会让清单像表格）
  .item-move, .item-remove {
    color: #c0c4cc;
    opacity: 0;
    transition: opacity 0.15s;
  }

  &:hover .item-move,
  &:hover .item-remove { opacity: 1; }

  .here { color: #c0c4cc; font-size: 12px; }
}
</style>
