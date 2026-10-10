<!--
  生存资源盘点 · 类别明细面板

  两类内容按消耗模式切换，**不按类别名判断**（把「吃」改名成「口粮」仍然走配餐路径）：
    · 配餐供餐（meal）→ 配方卡：主食位求和 / 必配位取最小 / 保质期封顶都摊开
    · 折旧 · 按需 · 时间 → 物品表：一件能用多久、三档天数、保质期

  「这个数是怎么来的」必须点得开：每个配方都能展开看每一行食材单独能撑多少顿，
  每件物品都能看到三档是怎么来的。看不见推导过程的数字，没法判断可不可信。
-->
<template>
  <div v-if="!category" class="survival-detail__empty">
    先选一个类别
  </div>

  <div v-else class="survival-detail">
    <!-- 配餐类：配方 -->
    <template v-if="category.consume_mode === 'meal'">
      <div class="survival-detail__toolbar">
        <div class="survival-detail__hint">
          主食位内多种食材互相替代（求和）；跨餐位缺一不可（取最小）
        </div>
        <el-button size="small" type="primary" plain @click="$emit('new-recipe')">
          <el-icon><Plus /></el-icon>新建配方
        </el-button>
      </div>

      <el-empty
        v-if="!category.recipes.length"
        description="还没有配餐配方 —— 没有配方就不算出「能撑多少顿」"
        :image-size="80"
      >
        <el-button size="small" @click="$emit('seed-and-new')">先建一个「一餐」配方</el-button>
      </el-empty>

      <div v-for="recipe in category.recipes" :key="recipe.recipe_id" class="survival-recipe">
        <div class="survival-recipe__head">
          <span class="survival-recipe__name">{{ recipe.recipe_name }}</span>
          <el-tag size="small" effect="plain">{{ recipe.per_day_reference }} 餐/天</el-tag>
          <el-tag v-if="!recipe.trustworthy" type="warning" size="small" effect="plain">
            配置不全，结果不可信
          </el-tag>
          <span class="survival-recipe__actions">
            <el-button link size="small" @click="$emit('edit-recipe', recipe.recipe_id)">编辑</el-button>
            <el-button link size="small" type="danger" @click="$emit('delete-recipe', recipe.recipe_id)">
              删除
            </el-button>
          </span>
        </div>

        <div class="survival-recipe__metrics">
          <div class="survival-recipe__metric">
            <span class="survival-recipe__metric-label">主食位（求和）</span>
            <span class="survival-recipe__metric-value">{{ formatMeals(recipe.staple_servings) }}</span>
          </div>
          <div class="survival-recipe__metric">
            <span class="survival-recipe__metric-label">必配位（取最小）</span>
            <span
              class="survival-recipe__metric-value"
              :class="{ 'survival-recipe__metric-value--muted': !recipe.required_line_count }"
            >{{ requiredText(recipe) }}</span>
          </div>
          <div class="survival-recipe__metric survival-recipe__metric--strong">
            <span class="survival-recipe__metric-label">配方可支撑</span>
            <span class="survival-recipe__metric-value">{{ formatMeals(recipe.meals) }}</span>
          </div>
          <div class="survival-recipe__metric">
            <span class="survival-recipe__metric-label">≈ 天数</span>
            <span class="survival-recipe__metric-value">{{ formatDays(recipe.expected) }}</span>
          </div>
        </div>

        <div class="survival-recipe__line">
          <span>三档：{{ rangeText(recipe.days) }}</span>
          <span v-if="recipe.bottleneck_item" class="survival-recipe__bottleneck">
            短板：{{ recipe.bottleneck_item }}
          </span>
          <span v-if="recipe.capped_by_expiry" class="survival-recipe__cap">
            受保质期封顶（最早 {{ recipe.expiry_cap_days }} 天后到期）
          </span>
        </div>

        <el-collapse class="survival-recipe__collapse">
          <el-collapse-item :name="String(recipe.recipe_id)">
            <template #title>
              <span class="survival-recipe__collapse-title">
                展开每一行食材的算法（{{ recipe.lines.length }} 行）
              </span>
            </template>
            <el-table :data="recipe.lines" size="small" class="survival-table">
              <!-- 组合行是**一行**，组内明细摊在它下面 —— 不展开成四行是刻意的：
                   列表膨胀四倍，而且「这四件是一锅的」这个事实会消失 -->
              <el-table-column label="食材 / 组合" min-width="220">
                <template #default="{ row }">
                  <div class="survival-line__main">
                    <span>
                      {{ row.item_name }}
                      <el-tag
                        v-if="row.line_kind === 'combo'"
                        size="small"
                        type="warning"
                        effect="plain"
                      >组合</el-tag>
                    </span>
                    <span
                      v-if="row.line_kind === 'combo'"
                      class="survival-line__members"
                    >{{ comboMembersText(row) }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="餐位" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="roleTagType(row.role)" effect="plain">
                    {{ row.role === 'staple' ? '主食位' : '必配位' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="每餐用量" width="120">
                <template #default="{ row }">
                  <!-- 组合行的用量在**成员**上，这里没有「一个数」可显示。
                       写 0 或留空都会让人以为没配 —— 直接说清楚它写在哪。 -->
                  <span v-if="row.line_kind === 'combo'" class="survival-line__muted">
                    见组内各件
                  </span>
                  <span v-else>{{ row.quantity_per_serving }} {{ row.unit_name || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="库存" width="110">
                <template #default="{ row }">
                  <span v-if="row.line_kind === 'combo'" class="survival-line__muted">—</span>
                  <span v-else>{{ row.stock }} {{ row.stock_unit_name }}</span>
                </template>
              </el-table-column>
              <el-table-column label="单独可撑" width="100">
                <template #default="{ row }">{{ formatMeals(row.servings) }}</template>
              </el-table-column>
              <el-table-column label="到期" width="110">
                <template #default="{ row }">
                  <span v-if="row.line_kind === 'combo'" class="survival-line__muted">
                    {{ row.expire_cap_days === null ? '—' : `${row.expire_cap_days} 天` }}
                  </span>
                  <template v-else>
                    {{ row.expire_date || '—' }}
                    <span v-if="row.expire_cap_days !== null" class="survival-table__cap">
                      （{{ row.expire_cap_days }} 天）
                    </span>
                  </template>
                </template>
              </el-table-column>
              <el-table-column label="问题" min-width="180">
                <template #default="{ row }">
                  <span v-for="issue in row.issues" :key="issue.code" class="survival-table__issue">
                    {{ issue.message }}
                    <span v-if="issue.detail" class="survival-table__issue-detail">{{ issue.detail }}</span>
                  </span>
                  <span v-if="!row.issues.length" class="survival-table__ok">正常</span>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>
    </template>

    <!-- 非配餐类：物品 -->
    <template v-else>
      <div class="survival-detail__toolbar">
        <div class="survival-detail__hint">
          {{ modeHint }}
        </div>
        <el-button size="small" type="primary" plain @click="$emit('new-item')">
          <el-icon><Plus /></el-icon>新增物品
        </el-button>
      </div>

      <el-empty
        v-if="!category.items.length"
        description="这个类别下还没有物品"
        :image-size="80"
      />

      <el-table v-else :data="category.items" size="small" class="survival-table">
        <el-table-column prop="name" label="物品" min-width="130" />
        <el-table-column label="数量" width="110">
          <template #default="{ row }">{{ row.quantity }} {{ row.unit_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="计量口径" min-width="150">
          <template #default="{ row }">
            <el-tag v-if="row.life_mode === 'cycle'" size="small" effect="plain">按次</el-tag>
            <el-tag v-else-if="row.life_mode === 'day'" size="small" effect="plain">按天</el-tag>
            <el-tag v-else size="small" type="info" effect="plain">未填</el-tag>
            <span v-if="row.life_mode === 'cycle'" class="survival-table__cycle">
              {{ formatUseCycle(row.use_cycle_num, cycleUnitLabel(row.use_cycle_unit), row.use_times) }}
            </span>
          </template>
        </el-table-column>
        <!-- ⚠️ 显示 `days_per_unit_effective` 而不是 `days_per_unit`：
             按次计量的物品后者是空的，直接读会把它显示成「未填」，
             而它其实能算 —— 那是把「换了个填法」说成「没填」 -->
        <el-table-column label="一份可用" width="100">
          <template #default="{ row }">{{ formatDays(row.days_per_unit_effective, '未填') }}</template>
        </el-table-column>
        <el-table-column label="三档" width="150">
          <template #default="{ row }">{{ rangeText(row.days) }}</template>
        </el-table-column>
        <el-table-column label="期望" width="90">
          <template #default="{ row }">
            <span class="survival-table__strong">{{ formatDays(row.expected) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="可读时长" width="100">
          <template #default="{ row }">{{ formatHours(row.hours_total, '—') }}</template>
        </el-table-column>
        <!-- 上次盘点取自**盘点工作表**（它带着随时间变的列），
             不在这里自己从历史里推 —— 「没设周期就不催」那条规则在后端 -->
        <el-table-column label="上次盘点" width="150">
          <template #default="{ row }">
            {{ formatLastStocktake(lastStocktake(row.item_id).date, lastStocktake(row.item_id).days) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">{{ row.status === 'expired' ? '已过期' : '在用' }}</template>
        </el-table-column>
        <el-table-column label="到期封顶" width="110">
          <template #default="{ row }">
            {{ row.expire_cap_days === null ? '—' : `${row.expire_cap_days} 天` }}
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="160">
          <template #default="{ row }">
            <span v-for="issue in row.issues" :key="issue.code" class="survival-table__issue">
              {{ issue.message }}
            </span>
            <span v-if="!row.issues.length" class="survival-table__ok">
              {{ row.grade === 'first' ? '一等' : row.grade === 'second' ? '二等' : '—' }}
            </span>
          </template>
        </el-table-column>
        <!--
          单件盘点入口（v3.60.2）—— 与「编辑」分开：
          「改库存」是日常动作，「改主数据」是配置动作，两者不该共用一个入口。
          实测用法是一次盘一两件，而在那之前只能开一张 43 行的弹窗去找它。
        -->
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button link size="small" @click="$emit('stocktake-one', row.item_id)">
              盘一下
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <!--
      组合（v3.59.13）—— 对所有类别都显示，**不按类别名判断**

      用户拍板「其他类别也要组合」：只给配餐类做就等于把一份可复用的搭配声明
      锁死在一个消耗模式上（某个类别改成配餐模式，组合却建不了）。
      配方目前只出现在配餐类下，所以非配餐类里这一块是「先备着」——
      文案必须说清它服务于谁，否则看起来像一个建了没用的功能。
    -->
    <SurvivalComboPanel :category-id="category.category_id" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import SurvivalComboPanel from './SurvivalComboPanel.vue'
import {
  formatDays, formatHours, formatLastStocktake, formatMeals, formatUseCycle, roleTagType,
} from '../../utils/survivalFormat'
import type {
  SurvivalCategoryResult, SurvivalLineDetail, SurvivalRecipeResult, SurvivalScenarioTriple,
} from '../../types/survivalTypes'

const props = defineProps<{
  category: SurvivalCategoryResult | null
}>()

defineEmits<{
  'new-recipe': []
  'edit-recipe': [id: number]
  'delete-recipe': [id: number]
  'new-item': []
  'seed-and-new': []
  /** 单件盘点（v3.60.2）—— 只盘这一件 */
  'stocktake-one': [itemId: number]
}>()

const store = useSurvivalStore()

/** 每种消耗模式该填什么，一句话说清 —— 「聚合口径」这种词没人猜得出来 */
const MODE_HINTS: Record<string, string> = {
  depreciation: '填「一件还能穿多少天」：一件大衣还能穿 3 年就填 1095',
  on_demand: '天天用的填「一份能用多少天」（一包纸巾用 10 天填 10）；'
    + '不是天天用的切到「按次」填「一份能用几次 × 多久用一次」',
  time_based: '填「一册按我的节奏能读多少天」，另可填每册需要多少小时',
}

const modeHint = computed(() => (
  MODE_HINTS[props.category?.consume_mode ?? ''] ?? '填「一件还能用多少天」'
))

/** 周期单位的显示名 —— 取后端下发的同一份枚举，不硬编码「天/周/月」 */
function cycleUnitLabel(value: string): string {
  return store.meta?.use_cycle_units.find((u) => u.value === value)?.label ?? '天'
}

/**
 * 上次盘点是哪天、距今天多少天。
 *
 * ⚠️ 两处都要能返回「没有」：工作表里可能根本没有这件物品
 *    （没建单位之类），那时是**从未盘点**，不是「今天刚盘过」——
 *    `days` 必须保持 null，`formatLastStocktake` 才会说「从未盘点」。
 */
function lastStocktake(itemId: number): { date: string | null; days: number | null } {
  const row = store.worksheet.find((r) => r.item_id === itemId)
  if (!row) return { date: null, days: null }
  return { date: row.last_stocktake_date, days: row.days_since_stocktake }
}

function rangeText(days: SurvivalScenarioTriple): string {
  const { optimistic: o, pessimistic: p } = days
  if (o === null || p === null) return '算不出来'
  return `${formatDays(p)} ~ ${formatDays(o)}`
}

/**
 * 必配位三态 —— **「没配」不能显示成「算不出来」**
 *
 * 后端 `required_servings` 为 null 有两种完全不同的来由，靠 `required_line_count` 分开：
 *   · 一行都没配 → 「无必配项」⇒ **无约束，不参与结论**，是正常配置
 *   · 配了但每行都算不出来 → 「算不出来」⇒ 真有问题，`issues` 会点名是哪件食材
 *
 * 一律显示「算不出来」会造成自相矛盾：旁边「配方可支撑」明明算得好好的。
 * 使用者会以为自己的配置错了，而其实什么都没错。
 */
function requiredText(recipe: SurvivalRecipeResult): string {
  if (recipe.required_servings !== null) return formatMeals(recipe.required_servings)
  return recipe.required_line_count ? formatMeals(null) : '无必配项'
}

/**
 * 组合行下面那行浅字：把组内各件摊开。
 *
 * 「燕麦米 + 绿豆 + 薏仁 + 紫米 是一锅」这个事实**就是用户建组合的理由**，
 * 折叠掉等于把组合变成一个黑箱名字 —— 而这一行算出来的是组内**最先耗尽的那件**，
 * 不把组员列出来，就没法理解为什么是 6 顿。
 *
 * ⚠️ 组内为空要**说出来**，不能渲染成空白：空白和「还在加载」长得一样。
 */
function comboMembersText(row: SurvivalLineDetail): string {
  const members = row.members ?? []
  if (!members.length) return '组内没有物品'
  return members
    .map((m) => `${m.item_name} ${m.quantity_per_serving} ${m.unit_name || '—'}`)
    .join(' · ')
}
</script>

<style scoped>
.survival-detail__empty {
  padding: 40px;
  text-align: center;
  color: var(--el-text-color-secondary);
}
.survival-detail__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.survival-detail__hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-recipe {
  padding: 12px 14px;
  margin-bottom: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.survival-recipe__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.survival-recipe__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.survival-recipe__actions {
  margin-left: auto;
}
.survival-recipe__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}
.survival-recipe__metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.survival-recipe__metric-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-recipe__metric-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.survival-recipe__metric--strong .survival-recipe__metric-value {
  color: var(--el-color-primary);
}
/* 「无必配项」是**正常配置**，不是错误 —— 弱化但不报警 */
.survival-recipe__metric-value--muted {
  font-size: 13px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
}
.survival-recipe__line {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.survival-recipe__bottleneck {
  color: var(--el-color-danger);
}
.survival-recipe__cap {
  color: var(--el-color-warning);
}
.survival-recipe__collapse {
  margin-top: 6px;
  border-top: none;
}
.survival-recipe__collapse-title {
  font-size: 12px;
  color: var(--el-color-primary);
}
.survival-table {
  width: 100%;
}
.survival-table__strong {
  font-weight: 600;
}
.survival-table__ok {
  color: var(--el-text-color-secondary);
}
.survival-table__issue {
  display: block;
  color: var(--el-color-warning);
  font-size: 12px;
}
.survival-table__issue-detail {
  color: var(--el-text-color-secondary);
}
.survival-table__cap {
  color: var(--el-color-warning);
}
.survival-table__cycle {
  margin-left: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
/* 组合行：名字在上、组员在下 —— 组员是这行的**解释**，不是次要信息 */
.survival-line__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.survival-line__members {
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
/* 「见组内各件」「—」：明确表示「这里没有单一的数」，
   弱化但不是空白 —— 空白和加载中长得一样 */
.survival-line__muted {
  color: var(--el-text-color-secondary);
}
</style>
