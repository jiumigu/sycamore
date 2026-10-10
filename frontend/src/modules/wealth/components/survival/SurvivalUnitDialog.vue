<!--
  消耗单位维护弹窗（全程可维护：新增 / 改 / 删）

  单位不只是标签，**必须能换算到同一基准单位**，否则跨单位求和是错的：
  「20 罐 + 3000 克」在数学上无意义，而错误结果是静默的 ——
  它会给出一个看着完全合理的生存天数，没人会去查。

  所以这里除了名称，还要填「基准单位」与「换算率」：
  库存按袋、配方按克时，1 袋 = 5000 克 就是让这两者能相除的唯一依据。
  两边的基准不同时，后端会报「单位不可比」而不是猜一个换算率。

  ⚠️ 顶部**带类别切换器**。单位是「每类别一套」的，原先只能维护当前激活类别，
     于是「想给『穿』加个『双』」得先回页面切 Tab 再进来 ——
     维护入口不该要求用户先导航到别处。
-->
<template>
  <el-dialog
    v-model="visible"
    title="消耗单位维护"
    width="720px"
    :close-on-click-modal="false"
  >
    <div class="survival-unit__picker">
      <span class="survival-unit__picker-label">类别</span>
      <el-select v-model="localCategoryId" size="small" class="survival-unit__picker-select">
        <el-option
          v-for="category in store.categories"
          :key="category.id"
          :label="category.name"
          :value="category.id"
        />
      </el-select>
      <span class="survival-unit__picker-note">
        单位按类别各存一套 —— 同一类别内基准一致就能互相换算
      </span>
    </div>

    <div class="survival-unit__hint">
      基准单位 = 这个类别里用哪个单位做「公分母」。同一类别内只要基准一致就能互相换算；
      留空表示这个单位自成一系（不与别的单位换算）。
    </div>

    <el-table :data="units" size="small" class="survival-unit__table">
      <el-table-column prop="name" label="单位" width="100" />
      <el-table-column prop="base_unit" label="基准单位" width="110">
        <template #default="{ row }">{{ row.base_unit || row.name }}</template>
      </el-table-column>
      <el-table-column label="换算率" width="150">
        <template #default="{ row }">1 {{ row.name }} = {{ row.to_base_rate }}</template>
      </el-table-column>
      <el-table-column label="可作一餐" width="90">
        <template #default="{ row }">{{ row.is_serving_unit ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link size="small" @click="startEdit(row)">编辑</el-button>
          <el-button link size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="survival-unit__empty">
          这个类别还没有任何单位 —— 在下面加一个（如「件」「个」），
          否则物品没有计量口径，跨单位求和会被判为不可比。
        </div>
      </template>
    </el-table>

    <el-divider>{{ editingId ? '编辑单位' : '新增单位' }}</el-divider>

    <el-form :model="form" label-width="90px" size="small">
      <el-form-item label="单位名称">
        <el-input v-model="form.name" placeholder="罐 / 克 / 袋 / 件 / 顿" maxlength="20" />
      </el-form-item>
      <el-form-item label="基准单位">
        <el-input v-model="form.base_unit" placeholder="留空 = 自成一系；如 克 / 件 / 册" maxlength="20" />
      </el-form-item>
      <el-form-item label="换算率">
        <el-input-number v-model="form.to_base_rate" :min="0.0001" :step="1" :precision="4" />
        <span class="survival-unit__suffix">
          1 {{ form.name || '本单位' }} = {{ form.to_base_rate }} {{ form.base_unit || form.name || '基准' }}
        </span>
      </el-form-item>
      <el-form-item label="可作一餐">
        <el-switch v-model="form.is_serving_unit" />
        <span class="survival-unit__suffix">如「顿」—— 可以直接当作一餐的计数单位</span>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button v-if="editingId" size="small" @click="resetForm">取消编辑</el-button>
      <el-button size="small" @click="visible = false">关闭</el-button>
      <el-button size="small" type="primary" :loading="store.saving" @click="submit">
        {{ editingId ? '保存修改' : '新增' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSurvivalStore } from '../../stores/survivalStore'
import type { SurvivalUnit } from '../../types/survivalTypes'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  categoryId: number | null
  categoryName: string
}>()

const store = useSurvivalStore()

/** 弹窗内的当前类别 —— 打开时跟随外层，之后可以自己切 */
const localCategoryId = ref<number | null>(props.categoryId)

const units = computed(() => (
  store.units.filter((u) => u.category_id === localCategoryId.value)
))

/** 切类别时把编辑态清掉：跨类别继续编辑同一个单位会让基准单位对不上 */
watch(localCategoryId, () => resetForm())

const editingId = ref<number | null>(null)

const form = reactive({
  name: '',
  base_unit: '',
  to_base_rate: 1,
  is_serving_unit: false,
})

function resetForm() {
  editingId.value = null
  form.name = ''
  form.base_unit = ''
  form.to_base_rate = 1
  form.is_serving_unit = false
}

function startEdit(row: SurvivalUnit) {
  editingId.value = row.id
  form.name = row.name
  form.base_unit = row.base_unit
  form.to_base_rate = row.to_base_rate
  form.is_serving_unit = row.is_serving_unit
}

watch(visible, (open) => {
  if (!open) return
  localCategoryId.value = props.categoryId ?? store.categories[0]?.id ?? null
  resetForm()
})

async function submit() {
  if (!localCategoryId.value) {
    ElMessage.warning('先选一个类别')
    return
  }
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('单位名称不能为空')
    return
  }
  const duplicate = store.units.find(
    (u) => u.category_id === localCategoryId.value && u.name === name && u.id !== editingId.value,
  )
  if (duplicate) {
    ElMessage.warning(`这个类别下已经有「${name}」了`)
    return
  }
  try {
    await store.saveUnit({
      category_id: localCategoryId.value,
      name,
      base_unit: form.base_unit.trim(),
      to_base_rate: form.to_base_rate,
      is_serving_unit: form.is_serving_unit,
    }, editingId.value ?? undefined)
    ElMessage.success(editingId.value ? '已保存' : '已新增')
    resetForm()
  } catch (e: unknown) {
    ElMessage.error(extractMessage(e, '保存失败'))
  }
}

async function remove(row: SurvivalUnit) {
  try {
    await ElMessageBox.confirm(
      `确认删除单位「${row.name}」？被物品或配方引用的单位删不掉，系统会告诉你还被谁用着。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeUnit(row.id)
    ElMessage.success('已删除')
  } catch (e: unknown) {
    // 后端会把「仍被 N 件物品引用」的原因放在 detail 里 —— 照原样透出，
    // 不要换成「删除失败」这种看不出下一步的提示
    ElMessage.error(extractMessage(e, '删除失败'))
  }
}

/** 取出后端 detail —— 它是**能照做的提示**，不能吞掉换成通用文案 */
function extractMessage(e: unknown, fallback: string): string {
  const resp = (e as { response?: { data?: Record<string, unknown> } })?.response
  const data = resp?.data
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
.survival-unit__picker {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.survival-unit__picker-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.survival-unit__picker-select {
  width: 160px;
}
.survival-unit__picker-note {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-unit__empty {
  padding: 12px 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}
.survival-unit__hint {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}
.survival-unit__table {
  width: 100%;
}
.survival-unit__suffix {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
