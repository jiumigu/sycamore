<!--
  组合编辑弹窗（v3.59.13）

  「燕麦米、绿豆、薏仁、紫米是**分开登记**的，但烹饪时**一起下锅**。」

  这里只声明三件事：有哪几件、每餐各用多少、叫什么名字。

  ⚠️ 刻意**没有**「份数 / 倍数」这一格：用量已经写在每一件上了，再加一个倍率
     就是「两个数相乘」的形状 —— 两个数各自看着都正常，乘起来才错，
     而界面上看不出来（本项目踩过：「一份能用几次」× 数量 = 45,000 天）。
     要加量请改对应那一行的「每餐用量」。

  ⚠️ 也刻意**没有餐位**（主食位 / 必配位）：同一锅粥在早餐配方里可能是必配位、
     在别处可能是主食位。餐位是**配方行的属性**，锁死在组合上就表达不了。
-->
<template>
  <el-dialog
    v-model="visible"
    :title="comboId ? '编辑组合' : '新建组合'"
    width="720px"
    :close-on-click-modal="false"
    @open="onOpen"
  >
    <el-form ref="formRef" :model="form" label-width="96px" size="small">
      <el-form-item
        label="组合名称"
        prop="name"
        :rules="[{ required: true, message: '请填名称', trigger: 'blur' }]"
      >
        <el-input v-model="form.name" placeholder="如：杂粮粥 / 洗漱包" maxlength="50" />
      </el-form-item>

      <el-form-item label="说明">
        <el-input v-model="form.note" maxlength="200" placeholder="选填" />
      </el-form-item>
    </el-form>

    <el-divider>组合里一起用的东西</el-divider>

    <div class="combo-dialog__roles">
      <el-tag type="warning" effect="plain" size="small">
        组内取最小 · 缺一不可，看最先耗尽的那件
      </el-tag>
      <el-tag type="info" effect="plain" size="small">
        用量写在每一件上，没有「份数」这一格
      </el-tag>
    </div>

    <div v-for="(row, index) in form.members" :key="index" class="combo-dialog__row">
      <el-select
        v-model="row.item_id"
        placeholder="选择物品"
        size="small"
        filterable
        class="combo-dialog__row-item"
      >
        <el-option
          v-for="option in itemOptionsFor(index)"
          :key="option.id"
          :label="`${option.name}（剩 ${option.quantity} ${option.unit_name}）`"
          :value="option.id"
        />
      </el-select>

      <el-input-number
        v-model="row.quantity_per_serving"
        :min="0.0001"
        :step="1"
        :precision="4"
        size="small"
        controls-position="right"
        class="combo-dialog__row-qty"
      />

      <el-select
        v-model="row.unit_id"
        placeholder="跟随物品单位"
        size="small"
        clearable
        class="combo-dialog__row-unit"
      >
        <el-option
          v-for="unit in unitOptions"
          :key="unit.id"
          :label="unit.name"
          :value="unit.id"
        />
      </el-select>

      <el-button link size="small" type="danger" @click="form.members.splice(index, 1)">
        移除
      </el-button>
    </div>

    <el-button size="small" plain @click="addMember">
      <el-icon><Plus /></el-icon>添加一件
    </el-button>

    <div class="combo-dialog__hint">
      <p class="combo-dialog__hint-title">怎么填才不出错</p>
      <p>
        <b>「每餐用量」= 这一顿下锅多少</b>（燕麦米 40 克、绿豆 30 克…）。
        能煮几顿由<b>最先耗尽的那件</b>决定 —— 所以这里<b>不填「份数」</b>，
        要加量就改对应那一行的用量。
      </p>
      <p>
        物品必须属于<b>当前类别</b>，且<b>分开登记、各自算库存与保质期</b> ——
        组合只是「一起用」的声明，<b>不会合并数量、也不新建库存</b>。
      </p>
      <p v-if="recipeRefCount">
        ⚠️ 这个组合已经被 <b>{{ recipeRefCount }} 个配方</b>引用：
        改它会<b>同步影响那些配方</b>算出来的天数。
      </p>
    </div>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button size="small" type="primary" :loading="store.saving" @click="submit">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import type { SurvivalCombo, SurvivalComboMemberFormData } from '../../types/survivalTypes'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  categoryId: number | null
  /** 传 null = 新建 */
  comboId: number | null
}>()

/**
 * 新建成功后把**刚建好的那条**抛出去。
 *
 * 配方弹窗用它把新组合写回当前行（就地新建）；列表页不监听，白白多一个事件也不会坏事。
 */
const emit = defineEmits<{
  created: [combo: SurvivalCombo]
}>()

const store = useSurvivalStore()
const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  note: '',
  members: [] as SurvivalComboMemberFormData[],
})

/** 被几个配方引用 —— 改之前要让人知道影响面（与列表页同一个数） */
const recipeRefCount = computed(() => (
  store.combos.find((c) => c.id === props.comboId)?.recipe_ref_count ?? 0
))

const allItemOptions = computed(() => (
  store.items.filter((it) => it.category_id === props.categoryId)
))
const unitOptions = computed(() => (
  store.units.filter((u) => u.category_id === props.categoryId)
))

/**
 * 候选物品 —— 排除**本组合里已经选过**的那几件
 *
 * 同一件在一个组合里出现两次是一种**隐性倍率**（两行长得一样、用量却翻倍），
 * 后端也会拒；与其让人填完再收一句报错，不如让那一项根本选不出来。
 * ⚠️ 本行已选的那件要留着，否则取消选择都点不到。
 */
function itemOptionsFor(index: number) {
  const picked = new Set(
    form.members
      .filter((_, i) => i !== index)
      .map((row) => row.item_id)
      .filter((id) => !!id),
  )
  return allItemOptions.value.filter((it) => !picked.has(it.id))
}

function addMember() {
  const picked = new Set(form.members.map((row) => row.item_id))
  const first = allItemOptions.value.find((it) => !picked.has(it.id))
  form.members.push({
    item_id: first ? first.id : 0,
    quantity_per_serving: 1,
    unit_id: null,
  })
}

function onOpen() {
  if (!store.items.length) store.fetchItems()
  if (!store.categories.length) store.fetchCategories()

  const combo = props.comboId ? store.combos.find((c) => c.id === props.comboId) : null
  if (combo) {
    form.name = combo.name
    form.note = combo.note
    // 取 `members` 而不是顶层的 `member_count` —— 后者只是个计数，
    // 用它回填会得到一个空组合，用户一保存就把内容清空了。
    form.members = (combo.members ?? []).map((member) => ({
      item_id: member.item_id,
      quantity_per_serving: member.quantity_per_serving,
      unit_id: member.unit_id,
    }))
    if (!form.members.length) addMember()
    return
  }
  form.name = ''
  form.note = ''
  form.members = []
  addMember()
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!props.categoryId) {
    ElMessage.warning('先选一个类别')
    return
  }
  const members = form.members.filter((row) => row.item_id)
  if (!members.length) {
    ElMessage.warning('组合至少要有一件物品 —— 空组合会让配方里那一行变成无约束')
    return
  }
  try {
    const created = await store.saveCombo({
      category_id: props.categoryId,
      name: form.name.trim(),
      note: form.note.trim(),
      members,
    }, props.comboId ?? undefined)
    ElMessage.success('已保存')
    visible.value = false
    // 只有「新建」才有值得回填的东西；编辑时改动的是别处已有的引用
    if (!props.comboId && created) emit('created', created)
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
.combo-dialog__roles {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.combo-dialog__row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.combo-dialog__row-item {
  flex: 0 0 240px;
}
.combo-dialog__row-qty {
  flex: 0 0 140px;
}
.combo-dialog__row-unit {
  flex: 0 0 140px;
}
.combo-dialog__hint {
  margin-top: 12px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.combo-dialog__hint p {
  margin: 0 0 6px;
}
.combo-dialog__hint p:last-child {
  margin-bottom: 0;
}
.combo-dialog__hint-title {
  font-weight: 600;
  color: var(--el-text-color-regular);
}
.combo-dialog__hint b {
  color: var(--el-text-color-primary);
}
</style>
