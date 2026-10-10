<!--
  必需品基准项：新增 / 编辑（v3.59.7）

  ⚠️ 这里填的是「一个人生活**本该**有什么」，**不含数量**。
     数量在它关联的那件物品上（物品清单页填）——
     把数量塞进本表就等于把「认知」与「库存」重新揉成一件事，
     而这件事之所以拆开，是因为「没录入」必须能被表达出来。
-->
<template>
  <el-dialog
    :model-value="modelValue"
    :title="row ? '编辑基准项' : '新增基准项'"
    width="560px"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @open="onOpen"
  >
    <el-form ref="formRef" :model="form" label-width="96px">
      <el-form-item
        label="必需品名称"
        prop="name"
        :rules="[{ required: true, message: '请填名称', trigger: 'blur' }]"
      >
        <el-input v-model="form.name" placeholder="如：牙膏" maxlength="100" show-word-limit />
      </el-form-item>

      <el-form-item
        label="归属类别"
        prop="category_id"
        :rules="[{ required: true, message: '请选类别', trigger: 'change' }]"
      >
        <el-select v-model="form.category_id" placeholder="选一个类别" class="dialog__field">
          <el-option
            v-for="cat in store.categories"
            :key="cat.id"
            :label="cat.name"
            :value="cat.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="性质">
        <el-radio-group v-model="form.scope">
          <el-radio-button
            v-for="opt in scopes"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </el-radio-button>
        </el-radio-group>
        <div class="dialog__tip">
          底线必需 = 缺了影响健康 / 卫生 / 体面；改善型 = 只是「有更好」。
          只有底线必需才会拦住「对账已闭环」的结论。
        </div>
      </el-form-item>

      <el-form-item label="建议单位">
        <el-input
          v-model="form.unit_name"
          placeholder="如：支 / 包"
          maxlength="20"
          class="dialog__field"
        />
        <div class="dialog__tip">仅作录入提示，不参与任何计算 —— 实际单位以对应物品为准。</div>
      </el-form-item>

      <el-form-item label="对应物品">
        <el-select
          v-model="form.item_ids"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          filterable
          placeholder="留空表示还没录入"
          class="dialog__field"
        >
          <el-option
            v-for="it in itemOptions"
            :key="it.id"
            :label="it.name"
            :value="it.id"
          />
        </el-select>
        <div class="dialog__tip">
          <b>可以挂多件</b>：睡衣分夏 / 秋 / 冬，卫生巾分日用 / 夜用，
          鞋分室内 / 室外 —— 这几件并列、缺一不可，系统按<b>最短的那件</b>算
          「还能撑多久」（冬天没睡衣，夏季那件囤十件也不解决）。
          一件都不挂就是缺口，会在对账里被点名。
          <br />
          <b>已经挂在别的基准项上的物品不会出现在这个列表里</b>——一件只能挂一处。
          要把某件改挂到这条，先去原来那条取消；
          已勾选的那几件始终留着，随时能取消。
          <template v-if="hiddenClaimedCount">
            （本类别已隐藏 <b>{{ hiddenClaimedCount }}</b> 件）
          </template>
        </div>
      </el-form-item>

      <el-form-item label="录入提示">
        <el-input
          v-model="form.hint"
          type="textarea"
          :rows="2"
          maxlength="200"
          placeholder="帮自己回忆消耗节奏的一句话，如「一支约 90 次，每天早晚各一次」"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="store.saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { useSurvivalStore } from '../../stores/survivalStore'
import type { SurvivalEssential, SurvivalEssentialScope } from '../../types/survivalTypes'

const props = defineProps<{
  modelValue: boolean
  row: SurvivalEssential | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved'): void
}>()

const store = useSurvivalStore()
const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  category_id: undefined as number | undefined,
  scope: 'core' as SurvivalEssentialScope,
  unit_name: '',
  hint: '',
  /** 关联物品可以挂多件（v3.59.12）；空数组 = 一件都不挂 = 缺口 */
  item_ids: [] as number[],
})

/** 性质选项来自 meta，前端不硬编码文案 */
const scopes = computed(() => store.meta?.essential_scopes ?? [])

/**
 * 已被**别的**基准项挂走的物品 → `item_id → 挂在哪个基准项上`
 *
 * 一件物品只能挂一处（后端也会硬拒）。物品越增越多时，把已经关联过的
 * 混在候选里是一种持续干扰：每次都要先排除一遍自己已经挂好的那几件。
 *
 * ⚠️ `exclude` 自己这一条 —— 否则「编辑自己」时候选里没有自己已勾的那几件，
 *    连取消勾选都点不到（这个坑在「一件只挂一处」的服务层校验里已经踩过一次）。
 */
const claimedElsewhere = computed(() => {
  const taken = new Map<number, string>()
  for (const row of store.essentials) {
    if (row.essential_id === props.row?.essential_id) continue
    for (const it of row.items ?? []) {
      if (!taken.has(it.item_id)) taken.set(it.item_id, row.name)
    }
  }
  return taken
})

/**
 * 对应物品的候选。
 *
 * ① **按归属类别收窄** —— 跨类别关联基本都是选错了（把「牙膏」挂到医药类物品上）。
 *    类别还没选时给全量，让用户能先看一眼柜子里有什么。
 * ② **去掉已挂在别处的** —— 就是这一条在治「列表越长越吵」。
 * ③ **自己已勾的无论如何留着** —— 包括跨类别、以及存量里已经挂了两处的。
 *    候选里没有它时 `el-select` 会把值当标签显示，界面上冒出一个裸 id（如 `42`），
 *    看起来像数据坏了。宁可照实显示名字 + 由后端在保存时拦下来。
 */
const itemOptions = computed(() => {
  const scope = form.category_id === undefined
    ? store.items
    : store.items.filter((it) => it.category_id === form.category_id)
  const taken = claimedElsewhere.value
  const picked = new Set(form.item_ids)
  const options = scope.filter((it) => !taken.has(it.id) || picked.has(it.id))
  for (const id of picked) {
    if (options.some((it) => it.id === id)) continue
    const fallback = store.items.find((it) => it.id === id)
    if (fallback) options.push(fallback)
  }
  return options
})

/**
 * 被过滤掉的件数（当前类别范围内）。
 *
 * 过滤本身必须**可见**：候选里少了几件却没有任何解释，看起来像数据丢了。
 * 报个数，人就知道「不是没有，是已经挂好了」。
 */
const hiddenClaimedCount = computed(() => {
  const scope = form.category_id === undefined
    ? store.items
    : store.items.filter((it) => it.category_id === form.category_id)
  const taken = claimedElsewhere.value
  const picked = new Set(form.item_ids)
  return scope.filter((it) => taken.has(it.id) && !picked.has(it.id)).length
})

function onOpen() {
  store.fetchMeta()
  if (!store.items.length) store.fetchItems()
  if (!store.categories.length) store.fetchCategories()
  // 候选过滤要用「哪件已经被挂走了」，所以这份清单必须先在手上。
  // ⚠️ 只在**空**的时候取：带参取一次会把清单页当前的排序一起改掉
  //    （两处用同一个 ref），那不是这个弹窗该干的事。
  if (!store.essentials.length) store.fetchEssentials()

  if (props.row) {
    form.name = props.row.name
    form.category_id = props.row.category_id ?? undefined
    form.scope = props.row.scope
    form.unit_name = props.row.unit_name
    form.hint = props.row.hint
    // ⚠️ 取 `items` 而不是顶层的 `item_id` —— 后者是**代表件**，
    //    拿它回填会把另外几件静默丢掉，用户一保存就少了两个季节的睡衣。
    form.item_ids = props.row.items.map((it) => it.item_id)
    return
  }
  form.name = ''
  form.category_id = store.activeCategoryId ?? store.categories[0]?.id
  form.scope = 'core'
  form.unit_name = ''
  form.hint = ''
  form.item_ids = []
}

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (form.category_id === undefined) {
    ElMessage.warning('请选一个归属类别')
    return
  }
  try {
    await store.saveEssential(
      {
        name: form.name.trim(),
        category_id: form.category_id,
        scope: form.scope,
        unit_name: form.unit_name.trim(),
        hint: form.hint.trim(),
        // 送空数组而不是省略 —— 「一件都不挂」是一次真实的意图，
        // 省略会被后端读成「这次不动它」，取消勾选后保存就会静默无效
        item_ids: form.item_ids,
      },
      props.row?.essential_id,
    )
    ElMessage.success('已保存')
    emit('saved')
    close()
  } catch (e) {
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
.dialog__field {
  width: 100%;
}
.dialog__tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  margin-top: 4px;
}
</style>
