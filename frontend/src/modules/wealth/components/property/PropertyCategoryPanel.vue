<!--
  物件资产 · 类别维护面板（v3.60.0）

  类别是轻量主数据：用户可随时增删改。这一页只回答「我的家当分了哪几类」。

  🔴 「删除」是本模块**唯一**会失败的操作，而且失败是**正常的**：
     其下还有物件时后端返回 400 + 「「家电」下还有 2 件物件，不能直接删除…」。
     ⇒ 那句 `detail` 必须原样弹出来（`extractApiMessage`），
       换成一句「删除失败」就把「下一步该干什么」也一起丢掉了。
     ⇒ **绝不级联删除**：删掉一个建错的空类别，与删掉整柜家当，
       不该走同一个按钮 —— 代价完全不对称且不可逆。

  ⚠️ 表里有一列「物件数」，它不是装饰：它就是「为什么这个类别删得掉 / 删不掉」
     的答案。没有它，用户只会看到一个时灵时不灵的删除按钮。

  🔴 「初始化默认类别」的确认里必须写清**会冲掉什么**：
     它只覆盖图标、说明与排序（`PROPERTY_CATEGORY_SEEDS` 里那三样），
     **不会**碰用户改过的使用年限、更不会碰任何物件。
     把这些说清楚，一次确认才不是一次静默覆盖。
-->

<template>
  <div class="property-categories">
    <div class="property-categories__head">
      <div class="property-categories__title-wrap">
        <span class="property-categories__title">类别</span>
        <span class="property-categories__subtitle">
          只装「用途」—— 家电 / 家具 / 数码；「大」与「贵」用列表排序表达
        </span>
      </div>
      <div class="property-categories__actions">
        <el-button size="small" :loading="store.saving" @click="onSeed">
          初始化默认类别
        </el-button>
        <el-button size="small" type="primary" plain @click="emit('new')">
          <el-icon><Plus /></el-icon>新增类别
        </el-button>
      </div>
    </div>

    <el-empty
      v-if="!store.categories.length"
      description="还没有任何类别 —— 点「初始化默认类别」一次补齐六个，或自己建"
      :image-size="60"
    />

    <el-table v-else :data="store.categories" size="small" row-key="id">
      <el-table-column prop="name" label="类别名称" min-width="120">
        <template #default="{ row }">
          <span class="property-categories__name">{{ row.name }}</span>
        </template>
      </el-table-column>

      <el-table-column label="默认使用年限" width="130">
        <template #default="{ row }">
          <span v-if="row.default_lifespan_months !== null">
            {{ formatMonths(row.default_lifespan_months) }}
          </span>
          <!-- 留空 = 不预填。它是**正常状态**，不是缺失，所以是灰字而不是警告 -->
          <span v-else class="property-categories__muted">不预填</span>
        </template>
      </el-table-column>

      <el-table-column label="说明" min-width="200">
        <template #default="{ row }">
          <span v-if="row.note">{{ row.note }}</span>
          <span v-else class="property-categories__muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="物件数" width="90" align="right">
        <template #default="{ row }">
          <span :class="{ 'property-categories__muted': !row.property_count }">
            {{ row.property_count }} 件
          </span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link size="small" @click="emit('edit', row)">编辑</el-button>
          <el-button link size="small" type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="property-categories__foot">
      ⚠️ 类别的「默认使用年限」只用来预填新增表单，<b>绝不作为任何计算依据</b>——
      物件自己没填年限时净值算不出，不会拿它顶上。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { usePropertyStore } from '../../stores/propertyStore'
import { extractApiMessage } from '../../utils/propertyError'
import { formatMonths } from '../../utils/propertyFormat'
import type { PropertyCategory } from '../../types/propertyTypes'

const emit = defineEmits<{
  new: []
  edit: [category: PropertyCategory]
}>()

const store = usePropertyStore()

async function onDelete(category: PropertyCategory) {
  try {
    await ElMessageBox.confirm(
      `确认删除类别「${category.name}」？`
      + (category.property_count
        ? `它下面还有 ${category.property_count} 件物件，会被后端拦下 —— `
          + '请先把这些物件改到别的类别，或逐件删除。'
        : '这个类别下没有物件，可以安全删除。'),
      '删除类别',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeCategory(category.id)
    ElMessage.success(`已删除类别「${category.name}」`)
  } catch (e: unknown) {
    // 🔴 400 里那句话带着「还有 N 件、该怎么办」，原样弹出来
    ElMessage.error(extractApiMessage(e, '删除失败'))
  }
}

/**
 * 初始化默认类别（幂等，**不预设任何物件**）。
 *
 * 两段式：先跑一次只补缺的；如果六个都已在（`created === 0`），
 * 再问一次要不要把图标 / 说明 / 排序覆盖成当前默认值。
 * ⚠️ 「已有类别可覆盖口径」这句暗示不发出来，它就看起来像一次无害的补齐。
 */
async function onSeed() {
  let created = 0
  try {
    const result = await store.seedCategories() as { created?: number } | undefined
    created = result?.created ?? 0
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '初始化失败'))
    return
  }
  if (created) {
    ElMessage.success(`已建好 ${created} 个默认类别（家电 / 家具 / 数码 / 交通 / 家装 / 其他）`)
    return
  }
  try {
    await ElMessageBox.confirm(
      '六个默认类别都已存在，刚才只补齐了缺的。'
      + '要把已有类别的图标、说明与排序恢复成当前默认值吗？'
      + '（会冲掉你改过的说明与自定义排序；不会碰你设的默认使用年限，也不会碰任何物件）',
      '覆盖类别说明与排序',
      { type: 'warning', confirmButtonText: '覆盖', cancelButtonText: '保持现状' },
    )
  } catch {
    return
  }
  try {
    const result = await store.seedCategories(true) as { updated?: number } | undefined
    ElMessage.success(`已覆盖 ${result?.updated ?? 0} 个类别的说明与排序`)
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '覆盖失败'))
  }
}
</script>

<style scoped>
.property-categories__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.property-categories__title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.property-categories__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.property-categories__subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-categories__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.property-categories__name {
  font-weight: 600;
}
.property-categories__muted {
  color: var(--el-text-color-placeholder);
}
.property-categories__foot {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}
</style>
