<!--
  配餐配方编辑弹窗

  一顿饭不是一种东西，但也不是「必须凑齐」：
    · 主食位（staple）——同一位下多种食材**互相替代** → 餐数相加
    · 必配位（required）——缺一不可 → 取最小值（木桶效应只在这里成立）
  所以这里要选「餐位」，而不是把所有食材平铺成一行。

  v3.59.13：每一行多了一个「来源」——**一件物品**，或**一个组合**。
    组合 = 「分开登记、一起下锅」的声明（燕麦米 + 绿豆 + 薏仁 + 紫米）。

  🔴 组合行在配方里**占一行**，刻意不展开成四行：
    ① 挂主食位时，展开四行与一行**数学等价**（min-of-min = min），
       等价性有用例钉住（`TestComboEqualsExpansion`）——
       所以「不展开」是**展示层的选择**，不是算法上的妥协；
    ② 展开后「这四件是一锅的」这个事实就消失了，看报表的人没法还原现场；
    ③ 最要命的是：改组合时已展开的四行**不会跟着改**，会静默分叉。

  ⚠️ 组合行**没有「每餐用量」**：用量已经写在每一件上了（建组合时填）。
     这里再给一个倍率，就是「两个数相乘」的形状 —— 两个数各自看着都正常，
     乘起来才错，而界面上看不出来（本项目踩过：一份能用几次 × 数量 = 45,000 天）。

  ⚠️ 至少要有一样主食：没有主食的配方算不出「能撑多少顿」，
     与其让它算出一个空值，不如在保存时拦下来。**物品行与组合行一起判**
     （只看物品行的话，一个「只挂组合」的配方会被放过去）。
-->
<template>
  <el-dialog
    v-model="visible"
    :title="recipeId ? '编辑配餐配方' : '新建配餐配方'"
    width="860px"
    :close-on-click-modal="false"
  >
    <el-form :model="form" label-width="96px" size="small">
      <el-form-item label="配方名称">
        <el-input v-model="form.name" placeholder="一餐 / 早餐 / 正餐" maxlength="50" />
      </el-form-item>
      <el-form-item label="每日餐数">
        <el-input-number v-model="form.meals_per_day" :min="0.5" :step="1" :precision="1" />
        <span class="survival-recipe-dialog__suffix">
          <b>这个配方一天占几顿</b> —— 不是一天总共吃几顿
        </span>
      </el-form-item>
      <el-form-item label="说明">
        <el-input v-model="form.note" maxlength="200" placeholder="选填" />
      </el-form-item>
    </el-form>

    <el-divider>配方组成</el-divider>

    <div class="survival-recipe-dialog__roles">
      <el-tag type="success" effect="plain" size="small">主食位 · 可替代，餐数相加</el-tag>
      <el-tag type="info" effect="plain" size="small">必配位 · 缺一不可，取最小（没有就留空）</el-tag>
    </div>

    <div v-for="(row, index) in form.rows" :key="index" class="survival-recipe-dialog__line">
      <!-- 来源：这一行是「一件东西」，还是「一组一起下锅的东西」 -->
      <el-radio-group
        v-model="row.source"
        size="small"
        class="survival-recipe-dialog__line-source"
        @change="onSourceChange(row)"
      >
        <el-radio-button value="item">物品</el-radio-button>
        <el-radio-button value="combo">组合</el-radio-button>
      </el-radio-group>

      <el-select
        v-if="row.source === 'item'"
        v-model="row.item_id"
        placeholder="选择食材"
        size="small"
        filterable
        class="survival-recipe-dialog__line-item"
      >
        <el-option
          v-for="item in itemOptions"
          :key="item.id"
          :label="`${item.name}（剩 ${item.quantity} ${item.unit_name}）`"
          :value="item.id"
        />
      </el-select>

      <el-select
        v-else
        v-model="row.combo_id"
        placeholder="选择组合"
        size="small"
        filterable
        class="survival-recipe-dialog__line-item"
      >
        <el-option
          v-for="combo in comboOptions"
          :key="combo.id"
          :label="`${combo.name}（${combo.member_count} 件一起用）`"
          :value="combo.id"
        />
        <!-- 就地新建组合：建完写回**这一行**，不必退出配方编辑再去别处建 -->
        <template #footer>
          <el-button link size="small" type="primary" @click.stop="openComboQuickAdd(index)">
            <el-icon><Plus /></el-icon>新建组合
          </el-button>
        </template>
      </el-select>

      <el-select v-model="row.role" size="small" class="survival-recipe-dialog__line-role">
        <el-option
          v-for="role in roleOptions"
          :key="role.value"
          :label="role.label"
          :value="role.value"
        />
      </el-select>

      <template v-if="row.source === 'item'">
        <el-input-number
          v-model="row.quantity_per_serving"
          :min="0.0001"
          :step="1"
          :precision="4"
          size="small"
          controls-position="right"
          class="survival-recipe-dialog__line-qty"
        />

        <el-select
          v-model="row.unit_id"
          placeholder="跟随物品单位"
          size="small"
          clearable
          class="survival-recipe-dialog__line-unit"
        >
          <el-option
            v-for="unit in unitOptions"
            :key="unit.id"
            :label="unit.name"
            :value="unit.id"
          />
          <!-- 就地新增单位：建完写回**这一行**，不必退出配方编辑 -->
          <template #footer>
            <el-button link size="small" type="primary" @click.stop="openQuickAdd(index)">
              <el-icon><Plus /></el-icon>新建单位
            </el-button>
          </template>
        </el-select>
      </template>

      <!--
        组合行没有「一个数」可填 —— 用量在组内每一件上。
        ⚠️ 这里**不能留空**：空白会被读成「还没填」，而这个格子的正确状态就是「没有」。
           也**不能显示 0**：0 会让人以为这一行不消耗。
      -->
      <span v-else class="survival-recipe-dialog__line-noqty">用量见组内各件</span>

      <el-button link size="small" type="danger" @click="form.rows.splice(index, 1)">移除</el-button>
    </div>

    <!-- 两个按钮分开：组合是个可复用的东西，不该逼人「先加一行、再翻开关」才找得到 -->
    <div class="survival-recipe-dialog__actions">
      <el-button size="small" plain @click="addRow('item')">
        <el-icon><Plus /></el-icon>添加食材行
      </el-button>
      <el-button size="small" plain @click="addRow('combo')">
        <el-icon><Plus /></el-icon>引用一个组合
      </el-button>
    </div>

    <div class="survival-recipe-dialog__hint">
      <p class="survival-recipe-dialog__hint-title">怎么填才不出错</p>
      <p>
        <b>「每日餐数」= 这个配方一天吃掉几顿</b>，不是一天总共吃几顿：
      </p>
      <ul>
        <li>
          一天三顿、早 / 午 / 晚<b>各建一个配方</b> → <b>三个都填 1</b>（合计 3 顿）
        </li>
        <li>
          只建一个「一天饭菜」配方 → 填 <b>3</b>
        </li>
      </ul>
      <p>
        三档的「<b>省 {{ mealScenarios.optimistic }} / 常 {{ mealScenarios.likely }} /
        放 {{ mealScenarios.pessimistic }}</b>」说的是<b>全天总顿数</b>的三种假设
        （省着吃 / 照常吃 / 放开吃），系统按同一比例折算到每个配方上。
        所以某个配方填 1 时，「省」档相当于一天只吃掉它 2/3 顿 —— 天数因此比「常」档长，
        这是<b>同一个消耗速率的三种假设</b>，不是三个互相独立的天数。
      </p>
      <p>
        <b>「餐位」怎么分：</b>同一顿里<b>可以互相替代</b>的全放主食位
        （早餐的八宝粥 / 拌米粉 / 水煮蛋 / 水饺 = 四选一 → 都放主食位，餐数相加）；
        <b>每天必须吃到、缺一不可</b>的才放必配位。<b>没有这类东西就不必配必配位</b>，
        不影响结论，列表里会显示「无必配项」。
      </p>
      <p>
        <b>「每餐用量」按食材自己的单位填</b>（八宝粥 1 罐、米粉 100 克、水煮蛋 2 个）。
        库存与用量单位不是同一基准时后端会报「单位不可比」，不会猜一个换算率。
      </p>
      <p>
        <b>「组合」是一行、不是一堆：</b>燕麦米 + 绿豆 + 薏仁 + 紫米分开登记、一起下锅，
        就把它们建一个组合，配方里<b>引用这个组合占一行</b>。
        这一行能撑几顿看<b>组内最先耗尽的那件</b>（所以短板会点名具体物品，不是组合名）。
        <b>组合行不用填用量</b> —— 用量写在组合里每一件上，这里再乘一次就会算错。
      </p>
    </div>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button size="small" type="primary" :loading="store.saving" @click="submit">
        保存
      </el-button>
    </template>

    <!-- 一个共享的就地新增单位弹窗：记住是哪一行触发的，建完写回那一行 -->
    <SurvivalUnitQuickAdd
      v-model:visible="quickAddVisible"
      :category-id="categoryId"
      :category-name="categoryName"
      @created="onUnitCreated"
    />

    <!-- 就地新建组合：建完把新组合填回触发它的那一行 -->
    <SurvivalComboDialog
      v-model:visible="comboQuickAddVisible"
      :category-id="categoryId"
      :combo-id="null"
      @created="onComboCreated"
    />
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import SurvivalUnitQuickAdd from './SurvivalUnitQuickAdd.vue'
import SurvivalComboDialog from './SurvivalComboDialog.vue'
import type { SurvivalCombo, SurvivalUnit } from '../../types/survivalTypes'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  categoryId: number | null
  /** 传 null = 新建 */
  recipeId: number | null
}>()

const store = useSurvivalStore()

/**
 * 表单里的一行。
 *
 * ⚠️ 用**一个** `rows` 数组而不是 `lines` + `comboLines` 两个：
 *   两个数组在界面上会渲染成两块，而配方本来是一串顺序的行 ——
 *   用户想「第三行换成组合」时得先在一处删、再去另一处加。
 *
 * ⚠️ 也不能保存 `source` 到后端：后端是**两张表**（食材行、组合行），
 *   「来源」在这里只是编辑期的判别式，提交时按它拆回两个数组。
 *   这也是为什么 `line_key` 不能是裸 id —— 两张表的 id 会撞号。
 */
interface RecipeFormRow {
  source: 'item' | 'combo'
  item_id: number | null
  combo_id: number | null
  role: string
  quantity_per_serving: number
  unit_id: number | null
}

const itemOptions = computed(() => (
  store.items.filter((i) => i.category_id === props.categoryId)
))
const unitOptions = computed(() => (
  store.units.filter((u) => u.category_id === props.categoryId)
))
const roleOptions = computed(() => store.meta?.roles ?? [])
const mealScenarios = computed(() => store.meta?.meal_scenarios ?? { optimistic: 2, likely: 3, pessimistic: 4 })

/**
 * 只列**当前类别**的组合。
 *
 * 与 `SurvivalComboPanel` 用同一条判据（都按 `category_id` 过滤）——
 * 过滤条件不一致会出现「配方里选得到、组合列表里看不见」的鬼故事。
 * 后端也拒跨类别的组合行，这里只是别让人走到那一步。
 */
const comboOptions = computed(() => (
  store.combos.filter((c) => c.category_id === props.categoryId)
))

const form = reactive({
  name: '',
  meals_per_day: 3,
  note: '',
  rows: [] as RecipeFormRow[],
})

const quickAddVisible = ref(false)
/** 哪个配方行触发了新建单位 —— 建完只写回这一行 */
const quickAddLineIndex = ref<number | null>(null)

const comboQuickAddVisible = ref(false)
/** 哪个配方行触发了新建组合 —— 建完只写回这一行 */
const comboQuickAddRowIndex = ref<number | null>(null)

const categoryName = computed(
  () => store.categories.find((c) => c.id === props.categoryId)?.name ?? '',
)

function openQuickAdd(index: number) {
  quickAddLineIndex.value = index
  quickAddVisible.value = true
}

function onUnitCreated(unit: SurvivalUnit) {
  const index = quickAddLineIndex.value
  const row = index === null ? null : form.rows[index]
  if (row) row.unit_id = unit.id
}

function openComboQuickAdd(index: number) {
  comboQuickAddRowIndex.value = index
  comboQuickAddVisible.value = true
}

/** 新组合建好了 —— 直接把这一行切成「组合」并选中它，不留「建完还要自己找」的一步 */
function onComboCreated(combo: SurvivalCombo) {
  const index = comboQuickAddRowIndex.value
  const row = index === null ? null : form.rows[index]
  if (!row) return
  row.source = 'combo'
  row.item_id = null
  row.combo_id = combo.id
}

/**
 * 切换来源时把两边的选择都重置。
 *
 * 只清对侧、自动选中同侧的**第一项**：留着一个隐藏的 `item_id`/`combo_id`
 * 会让人以为「切回去还是原来那件」，但那一行提交的其实是当前这一侧的值。
 */
function onSourceChange(row: RecipeFormRow) {
  const toItem = row.source === 'item'
  row.item_id = toItem ? (itemOptions.value[0]?.id ?? null) : null
  row.combo_id = toItem ? null : (comboOptions.value[0]?.id ?? null)
}

function addRow(source: 'item' | 'combo') {
  form.rows.push({
    source,
    item_id: source === 'item' ? (itemOptions.value[0]?.id ?? null) : null,
    combo_id: source === 'combo' ? (comboOptions.value[0]?.id ?? null) : null,
    role: 'staple',
    quantity_per_serving: 1,
    unit_id: null,
  })
}

function resetForm() {
  form.name = ''
  form.meals_per_day = 3
  form.note = ''
  form.rows = []
}

watch(visible, (open) => {
  if (!open) return
  if (!store.combos.length) store.fetchCombos()
  resetForm()
  if (!props.recipeId) {
    addRow('item')
    return
  }
  const recipe = store.recipes.find((r) => r.id === props.recipeId)
  if (!recipe) return
  form.name = recipe.name
  form.meals_per_day = recipe.meals_per_day
  form.note = recipe.note
  // ⚠️ 顺序无法还原：后端把食材行与组合行存在**两张表**里，
  //    交叉顺序没有落点，只能「食材行在前、组合行在后」。
  form.rows = [
    ...(recipe.lines ?? []).map((line) => ({
      source: 'item' as const,
      item_id: line.item_id as number | null,
      combo_id: null,
      role: line.role,
      quantity_per_serving: line.quantity_per_serving,
      unit_id: line.unit_id ?? null,
    })),
    ...(recipe.combo_lines ?? []).map((line) => ({
      source: 'combo' as const,
      item_id: null,
      combo_id: line.combo_id,
      role: line.role,
      quantity_per_serving: 1,
      unit_id: null,
    })),
  ]
  if (!form.rows.length) addRow('item')
})

async function submit() {
  if (!props.categoryId) {
    ElMessage.warning('先选一个类别')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('配方名称不能为空')
    return
  }
  const itemRows = form.rows.filter((row) => row.source === 'item' && row.item_id)
  const comboRows = form.rows.filter((row) => row.source === 'combo' && row.combo_id)
  if (!itemRows.length && !comboRows.length) {
    ElMessage.warning('至少要有一行食材或组合')
    return
  }
  // 主食判据**两条线一起看**：只挂组合的配方也必须有主食，
  // 否则它算不出「能撑多少顿」，却会在界面上显示成一个正常配方
  const hasStaple = form.rows.some((row) => {
    if (row.source === 'item') return !!row.item_id && row.role === 'staple'
    return !!row.combo_id && row.role === 'staple'
  })
  if (!hasStaple) {
    ElMessage.warning('至少要有一样主食（主食位）—— 没有主食的配方算不出能撑多少顿')
    return
  }
  try {
    await store.saveRecipe({
      category_id: props.categoryId,
      name: form.name.trim(),
      meals_per_day: form.meals_per_day,
      note: form.note,
      // 两个键**都送** = 以这张表单为准整体覆盖：
      // 在界面上删掉一行组合，就真的从配方里移除；若只送 `lines`，
      // 后端会把「没传」理解成「这次不动它」，删掉的那行会悄悄复活
      lines: itemRows.map((row) => ({
        item_id: row.item_id as number,
        role: row.role,
        quantity_per_serving: row.quantity_per_serving,
        unit_id: row.unit_id,
      })),
      combo_lines: comboRows.map((row) => ({
        combo_id: row.combo_id as number,
        role: row.role,
      })),
    }, props.recipeId ?? undefined)
    ElMessage.success('已保存')
    visible.value = false
  } catch (e: unknown) {
    ElMessage.error(extractMessage(e, '保存失败'))
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
.survival-recipe-dialog__suffix {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-recipe-dialog__roles {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.survival-recipe-dialog__line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.survival-recipe-dialog__line-source {
  flex: 0 0 104px;
}
.survival-recipe-dialog__line-item {
  flex: 0 0 220px;
}
.survival-recipe-dialog__line-role {
  flex: 0 0 104px;
}
.survival-recipe-dialog__line-qty {
  flex: 0 0 120px;
}
.survival-recipe-dialog__line-unit {
  flex: 0 0 130px;
}
/* 组合行没有用量格 —— 用一段说明把这两位**占住**，行与行才对得齐；
   直接留空会让下面的行整体左移，看起来像表单坏了 */
.survival-recipe-dialog__line-noqty {
  flex: 0 0 258px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-recipe-dialog__actions {
  display: flex;
  gap: 8px;
}
.survival-recipe-dialog__hint {
  margin-top: 12px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.survival-recipe-dialog__hint p {
  margin: 0 0 6px;
}
.survival-recipe-dialog__hint p:last-child {
  margin-bottom: 0;
}
.survival-recipe-dialog__hint ul {
  margin: 0 0 6px;
  padding-left: 18px;
}
.survival-recipe-dialog__hint-title {
  font-weight: 600;
  color: var(--el-text-color-regular);
}
.survival-recipe-dialog__hint b {
  color: var(--el-text-color-primary);
}
</style>
