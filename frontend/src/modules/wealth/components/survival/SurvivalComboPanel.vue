<!--
  组合（v3.59.13）—— 「分开登记、一起下锅」

  用户的原话：燕麦米、绿豆、薏仁、紫米是**分开登记**的（各自算数量、各自算保质期），
  但烹饪时**一起下锅**。登记与「一起用」是两件事 —— 这一块只管后者。

  三条展示判据：

  ① **组内取最小**（并列缺一不可）：能煮几顿看最先耗尽的那件。
     口径整个在后端（`calc.compute_combo_line`），这里一个除法都不做。
  ② **被引用就不能删** —— `recipe_ref_count > 0` 时删除按钮直接禁用，
     并把「先从配方里移除」写出来。让人点一次再收一句报错，是最没必要的一步。
  ③ **改组合的影响面要写在脸上**：组合是可复用的，改它会同时改掉
     引用它的几个配方算出来的天数。这不是 bug，但必须提前说。

  ⚠️ 组合刻意**不带餐位**：同一锅粥在早餐配方里可能是必配位、在别处可能是主食位。
     餐位是配方行的属性 —— 列表里因此也不显示餐位。
-->
<template>
  <div class="survival-combo">
    <div class="survival-combo__head">
      <div class="survival-combo__title-wrap">
        <span class="survival-combo__title">组合</span>
        <span class="survival-combo__subtitle">
          几件东西「一起用」的声明（杂粮粥 = 燕麦米 + 绿豆 + 薏仁 + 紫米）。
          物品各自登记、各自算库存，这里只声明搭配与每餐用量
        </span>
      </div>
      <el-button
        size="small"
        type="primary"
        plain
        :disabled="!categoryId"
        @click="openDialog(null)"
      >
        <el-icon><Plus /></el-icon>新建组合
      </el-button>
    </div>

    <div v-if="!rows.length" class="survival-combo__empty">
      还没有组合。分开登记的东西如果要<b>一起下锅</b>，就在这里把它们声明成一组 ——
      <b>配方行可以直接引用一个组合</b>，而不必逐件挂一遍。
    </div>

    <div v-for="row in rows" :key="row.id" class="survival-combo__item">
      <div class="survival-combo__item-head">
        <span class="survival-combo__name">{{ row.name }}</span>
        <el-tag size="small" effect="plain">{{ row.member_count }} 件</el-tag>
        <el-tag v-if="row.recipe_ref_count" type="info" size="small" effect="plain">
          被 {{ row.recipe_ref_count }} 个配方引用
        </el-tag>
        <span class="survival-combo__actions">
          <el-button link size="small" @click="openDialog(row.id)">编辑</el-button>
          <el-button
            link
            size="small"
            type="danger"
            :disabled="row.recipe_ref_count > 0"
            @click="remove(row)"
          >
            删除
          </el-button>
        </span>
      </div>

      <div class="survival-combo__members">
        <span v-for="member in row.members" :key="member.item_id" class="survival-combo__member">
          {{ member.item_name }}
          <b>{{ member.quantity_per_serving }}</b>
          {{ member.unit_name || member.item_unit_name || '—' }}
        </span>
      </div>

      <div v-if="row.note" class="survival-combo__note">{{ row.note }}</div>
      <div v-if="row.recipe_ref_count" class="survival-combo__hint">
        改这个组合会<b>同步影响引用它的配方</b>算出来的天数；要删它请先从配方里移除
      </div>
    </div>

    <SurvivalComboDialog
      v-model:visible="dialogVisible"
      :category-id="categoryId"
      :combo-id="editingId"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import SurvivalComboDialog from './SurvivalComboDialog.vue'
import type { SurvivalCombo } from '../../types/survivalTypes'

const props = defineProps<{
  categoryId: number | null
}>()

const store = useSurvivalStore()

/**
 * 只显示**当前类别**的组合。
 *
 * 后端也支持 `?category_id=`，但这里不做二次请求：`refreshAll` 已经把全量取回来了，
 * 再发一次只会出现「列表与弹窗里的那份不是同一个时刻」的错位。
 * ⚠️ 筛选条件必须与后端那条**完全一致**（都按 `category_id`），
 *    否则会出现「配方里能选到、列表里看不见」的组合。
 */
const rows = computed<SurvivalCombo[]>(() => (
  props.categoryId === null
    ? []
    : store.combos.filter((combo) => combo.category_id === props.categoryId)
))

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

function openDialog(id: number | null) {
  editingId.value = id
  dialogVisible.value = true
}

async function remove(row: SurvivalCombo) {
  try {
    await ElMessageBox.confirm(
      `确定删除组合「${row.name}」吗？这只会去掉这条搭配声明，` +
        '里面的物品与库存都不受影响。',
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeCombo(row.id)
    ElMessage.success('已删除')
  } catch (e: unknown) {
    ElMessage.error(extractMessage(e, '删除失败'))
  }
}

function extractMessage(e: unknown, fallback: string): string {
  const data = (e as { response?: { data?: Record<string, unknown> } })?.response?.data
  if (data && typeof data.detail === 'string') return data.detail
  if (data) {
    const first = Object.values(data)[0]
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string') return first
  }
  return fallback
}
</script>

<style scoped>
.survival-combo {
  margin-top: 16px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.survival-combo__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.survival-combo__title-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.survival-combo__title {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}
.survival-combo__subtitle {
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.survival-combo__empty {
  font-size: 12px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);
  padding: 6px 0;
}
.survival-combo__item {
  padding: 8px 0;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.survival-combo__item-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.survival-combo__name {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}
.survival-combo__actions {
  margin-left: auto;
}
.survival-combo__members {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.survival-combo__member b {
  color: var(--el-text-color-primary);
}
.survival-combo__note,
.survival-combo__hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.survival-combo__hint b {
  color: var(--el-text-color-regular);
}
</style>
