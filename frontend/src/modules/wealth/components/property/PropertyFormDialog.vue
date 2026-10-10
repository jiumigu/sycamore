<!--
  物件资产 · 新增 / 编辑弹窗（v3.60.0）

  分组与「必填 / 选填」的划分照设计文档 §6.1：
    必填    名称 / 类别 / 状态 / 状况
    金额与时间  购买金额 / 购买日期 / 计划使用年限
    选填    品牌型号 / 存放位置 / 备注 / 标签
    报废（仅状态=已报废时出现）  报废日期 / 处置备注

  🔴 保存前试算那一块不是装饰，它是本模块的**主要防呆手段**。
     表单从来没把「已用 / 计划」与净值摆出来，用户就只能在保存后才发现
     「哦，年限填成 8 个月了」。所以这里实时显示：

        空调  计划用 8 年 · 已用 10 年 2 月 · 已超期 2 年 2 月
        月折旧 ¥312.50 · 当前净值 ¥0（已折完）

     ⚠️ 净值那个 ¥0 有三种来路，括号里必须说清是哪一种：
        「（算不出）」缺数据 · 「（已折完）」用够年限了 · 「（损坏归 0）」半道坏了。
        勾上「损坏」时试算**当场**就会跳成 ¥0 —— 让人在还看着这一屏时就知道。

     ⚠️ 走**后端同一个接口**（`/items/preview/`），绝不在这里自己除一遍 ——
        那份公式与 `property_calc` 迟早分叉，而**分叉是静默的**：
        试算说 ¥1,520、保存后写着 ¥1,480，两边都像一个正常的数。
     ⚠️ 试算是**护栏、不是闸门**：它自己失败只收起提示，绝不阻断保存。

  🔴 状态改回「在用 / 闲置」时，报废日期与处置备注**由服务端清空**，
     但这里也同步清一次：不清的话，折叠起来的那一格留着旧值，
     用户改完状态再展开会看到「状态是在用、却带着报废日期」的自相矛盾。

  ⚠️ 分类下拉旁边就是「+ 新建类别」：没有它，第一次录入就被卡死
     （同 `SurvivalUnitQuickAdd` 的理由）。

  ⚠️ 这里**没有**体型档 / 价值档 / 重要度 —— 用户问过要不要加，答了不加。
     类别只装「用途」（家电 / 家具 / 数码…）。「大」与「贵」用列表排序表达，
     那两件事都不需要落库（设计文档 §4.3 专条）。
-->
<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑物件' : '新增物件'"
    width="720px"
    :close-on-click-modal="false"
    append-to-body
  >
    <el-form :model="form" label-width="104px" size="small" class="property-form">
      <!-- ── 必填 ── -->
      <el-form-item label="物件名称" required>
        <el-input v-model="form.name" placeholder="海尔冰箱 / 格力空调 / 实木书桌" maxlength="100" />
      </el-form-item>

      <el-form-item label="类别" required>
        <div class="property-form__cat-row">
          <el-select v-model="form.category_id" placeholder="选一个类别" class="property-form__cat">
            <el-option
              v-for="option in store.categories"
              :key="option.id"
              :label="option.name"
              :value="option.id"
            />
          </el-select>
          <el-button size="small" plain @click="quickAddVisible = true">
            <el-icon><Plus /></el-icon>新建类别
          </el-button>
        </div>
      </el-form-item>

      <el-form-item label="状态">
        <el-radio-group v-model="form.status" @change="onStatusChange">
          <el-radio-button
            v-for="option in store.statusOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </el-radio-button>
        </el-radio-group>
        <span class="property-form__suffix">回答「我还要不要它」</span>
      </el-form-item>

      <el-form-item label="状况">
        <el-radio-group v-model="form.condition">
          <el-radio-button
            v-for="option in store.conditionOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </el-radio-button>
        </el-radio-group>
        <span class="property-form__suffix">
          回答「它现在好不好使」—— 与状态是两个问题，<b>标了「损坏」净值就按 ¥0 计</b>
        </span>
      </el-form-item>

      <!-- ── 金额与时间 ── -->
      <el-form-item label="购买金额">
        <span class="property-form__prefix">¥</span>
        <el-input-number
          v-model="form.purchase_amount"
          :min="0"
          :max="9999999999"
          :precision="2"
          :controls="false"
          placeholder="留空 = 想不起来了"
          class="property-form__amount"
        />
        <span class="property-form__suffix">整件的总价；留空时净值显示「—」，<b>不按 0 算</b></span>
      </el-form-item>

      <el-form-item label="购买日期">
        <el-date-picker
          v-model="form.purchase_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          clearable
          class="property-form__date"
        />
      </el-form-item>

      <el-form-item label="计划使用年限">
        <el-input-number
          v-model="lifespanYears"
          :min="0.1"
          :max="100"
          :step="0.5"
          :precision="1"
          :controls="false"
          placeholder="留空 = 不填"
          class="property-form__years"
        />
        <span class="property-form__suffix">年（可填小数，8.5 = 8 年 6 月）</span>
        <el-button
          v-if="categoryDefaultMonths"
          link
          size="small"
          type="primary"
          @click="applyCategoryDefault"
        >
          用类别默认值 {{ formatMonths(categoryDefaultMonths) }}
        </el-button>
        <div class="property-form__hint">
          由你自己填，系统不发明 —— 填的是你接受的标准，不是这件东西的固有属性。
          留空则净值算不出。
        </div>
      </el-form-item>

      <!-- ── 选填 ── -->
      <el-form-item label="品牌 / 型号">
        <el-input v-model="form.spec" placeholder="海尔 BCD-216" maxlength="100" />
      </el-form-item>

      <el-form-item label="存放位置">
        <el-input v-model="form.location" placeholder="厨房 / 卧室 / 老家" maxlength="50" />
      </el-form-item>

      <el-form-item label="标签">
        <el-select
          v-model="form.tags"
          multiple
          filterable
          allow-create
          default-first-option
          :reserve-keyword="false"
          placeholder="输入后回车新增，如 大件 / 待修"
          class="property-form__tags"
        />
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="form.note" type="textarea" :rows="2" placeholder="选填" />
      </el-form-item>

      <!-- ── 报废（仅状态=已报废） ── -->
      <template v-if="form.status === 'scrapped'">
        <el-form-item label="报废日期">
          <el-date-picker
            v-model="form.scrapped_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="默认今天，可改可清空"
            class="property-form__date"
          />
          <span class="property-form__suffix">不强制填 —— 记不得日期不该卡住人</span>
        </el-form-item>
        <el-form-item label="处置备注">
          <el-input
            v-model="form.dispose_note"
            placeholder="送人 / 以旧换新 / 坏了"
            maxlength="200"
          />
        </el-form-item>
      </template>
    </el-form>

    <!-- 保存前试算 —— 见文件头。数字全部来自后端，这里一句都不重算。 -->
    <div v-if="preview" class="property-form__preview">
      <div class="property-form__preview-title">
        保存后会是这样
        <span class="property-form__preview-note">按后端同一段算法试算，未写库</span>
      </div>
      <div class="property-form__preview-line">
        <b>{{ preview.name || '这件物件' }}</b>
        {{ formatPlannedLifespan(preview.lifespan_months) }}
        <template v-if="preview.age_months !== null">
          · 已用 {{ formatMonths(preview.age_months) }}
        </template>
        <template v-if="preview.is_overdue">
          · {{ formatOverdue(preview.overdue_months) }}
        </template>
        <template v-else-if="preview.remaining_months !== null">
          · 还剩 {{ formatMonths(preview.remaining_months) }}
        </template>
      </div>
      <div class="property-form__preview-line">
        月折旧 {{ formatMoneyOrDash(preview.monthly_depreciation) }}
        · 当前净值 {{ formatMoneyOrDash(preview.current_value) }}{{ valueSuffix }}
      </div>
      <!-- 算不出就把原因并排念出来 —— 一个没有出口的「—」等于没说 -->
      <div v-if="preview.issues.length" class="property-form__preview-issues">
        {{ preview.issues.map((issue) => issue.label).join('；') }}
      </div>
    </div>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button size="small" type="primary" :loading="store.saving" @click="submit">
        保存
      </el-button>
    </template>

    <!-- 就地新增类别：建完自动选中，本表单一个字段都不用重填 -->
    <PropertyQuickAddCategory
      v-model:visible="quickAddVisible"
      @created="onCategoryCreated"
    />
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import PropertyQuickAddCategory from './PropertyQuickAddCategory.vue'
import { usePropertyStore } from '../../stores/propertyStore'
import { extractApiMessage } from '../../utils/propertyError'
import {
  formatMoneyOrDash, formatMonths, formatOverdue, formatPlannedLifespan,
  formatZeroReason, monthsToYears, toNumberOrNull, yearsToMonths,
} from '../../utils/propertyFormat'
import type {
  PropertyCategory, PropertyCondition, PropertyItem, PropertyItemFormData, PropertyStatus,
} from '../../types/propertyTypes'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  /** null = 新增；有值 = 编辑那一件 */
  itemId: number | null
  /** 新增时的默认类别（从清单当前筛的那一类带过来），可改 */
  defaultCategoryId?: number | null
}>()

const emit = defineEmits<{ saved: [] }>()

const store = usePropertyStore()

const isEdit = computed(() => props.itemId !== null)

const form = reactive<{
  category_id: number | null
  name: string
  spec: string
  location: string
  purchase_amount: number | null
  purchase_date: string | null
  status: PropertyStatus
  condition: PropertyCondition
  scrapped_date: string | null
  dispose_note: string
  note: string
  tags: string[]
}>({
  category_id: null,
  name: '',
  spec: '',
  location: '',
  purchase_amount: null,
  purchase_date: null,
  status: 'in_use',
  condition: 'normal',
  scrapped_date: null,
  dispose_note: '',
  note: '',
  tags: [],
})

/**
 * 年限在界面上是「年」、接口按「月」收发。
 *
 * ⚠️ 与 `form` 分开是为了让「留空」是一个**真的空**：
 *    塞进 form 再统一 `?? 0` 会把「不填年限」变成「年限是 0」，
 *    而后者会让「金额 ÷ 年限」除零 —— 后端会 400，但那是绕远路报错。
 */
const lifespanYears = ref<number | null>(null)

const preview = ref<PropertyItem | null>(null)
const quickAddVisible = ref(false)

/** 当前类别预设的默认年限（只用来**预填**，不是任何计算的输入） */
const categoryDefaultMonths = computed<number | null>(() => {
  if (form.category_id === null) return null
  return store.categoryById[form.category_id]?.default_lifespan_months ?? null
})

/**
 * 净值后面那个括号 —— 三件事必须分开说：
 *   「算不出」是缺数据（要去补金额 / 日期 / 年限）；
 *   「已折完」是计划年限真的用完了（该考虑换新）；
 *   「损坏归 0」是还没到期就坏了（该修或者该扔）。
 *
 * 🔴 后两个都取 `zero_reason`（后端下发），**不在这里拿 condition 判** ——
 *    在前端判就是第二份口径，下次改口径时被漏掉的一定是它。
 *    这里正是踩过一次的地方：原先只按「值等于 0」判，
 *    于是损坏归 0 的物件会被写上一句「已折完」——
 *    把「坏了」说成「用够了」，两句话看着都通顺，错得毫无声响。
 */
const valueSuffix = computed(() => {
  const row = preview.value
  if (!row) return ''
  if (row.current_value === null) return '（算不出）'
  const reason = formatZeroReason(row.zero_reason)
  return reason ? `（${reason}）` : ''
})

// ─── 开弹窗时装载 ───

watch(visible, (open) => {
  if (!open) return
  preview.value = null
  const existing = props.itemId !== null
    ? store.items.find((candidate) => candidate.id === props.itemId)
    : null

  if (existing) {
    form.category_id = existing.category_id
    form.name = existing.name
    form.spec = existing.spec
    form.location = existing.location
    form.purchase_amount = toNumberOrNull(existing.purchase_amount)
    form.purchase_date = existing.purchase_date
    form.status = existing.status
    form.condition = existing.condition
    form.scrapped_date = existing.scrapped_date
    form.dispose_note = existing.dispose_note
    form.note = existing.note
    form.tags = [...(existing.tags ?? [])]
    lifespanYears.value = monthsToYears(existing.lifespan_months)
    return
  }

  // 新增：类别默认值只作**默认落点**，页面已经在维护它自己该是什么
  form.category_id = props.defaultCategoryId
    ?? store.categories[0]?.id
    ?? null
  form.name = ''
  form.spec = ''
  form.location = ''
  form.purchase_amount = null
  form.purchase_date = null
  form.status = 'in_use'
  form.condition = 'normal'
  form.scrapped_date = null
  form.dispose_note = ''
  form.note = ''
  form.tags = []
  lifespanYears.value = null
})

/**
 * 状态离开「已报废」时，把那两个字段**就地清掉**。
 *
 * ⚠️ 服务端也会清（`_clear_scrap_fields_if_needed`），这里清是为了界面：
 *    不然折叠起来的那一格留着旧值，用户改完状态再展开会看到
 *    「状态是在用、却带着报废日期」的自相矛盾。
 * ⚠️ 进入「已报废」时默认今天 —— 但**不强制**（记不得日期不该卡住人），
 *    所以只是预填，清得掉。
 */
function onStatusChange(value: string | number | boolean | undefined) {
  if (value === 'scrapped') {
    if (!form.scrapped_date) form.scrapped_date = todayString()
    return
  }
  form.scrapped_date = null
  form.dispose_note = ''
}

function todayString(): string {
  const now = new Date()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function onCategoryCreated(category: PropertyCategory) {
  form.category_id = category.id
}

/** 只把类别预设值搬进输入框 —— 显式动作，不静默覆盖已填的值 */
function applyCategoryDefault() {
  if (categoryDefaultMonths.value === null) return
  lifespanYears.value = monthsToYears(categoryDefaultMonths.value)
}

// ─── 试算 ───

/**
 * 组装入参；缺最必要的两项（类别 / 名称）时返回 null —— 那种时候试算没有意义。
 *
 * ⚠️ 派生列一律不送（后端自己算）。送过去也不会被用，但会让「谁是真源」
 *    在代码里看不出来。
 */
function buildPayload(): PropertyItemFormData | null {
  if (form.category_id === null || !form.name.trim()) return null
  return {
    category_id: form.category_id,
    name: form.name.trim(),
    spec: form.spec.trim(),
    location: form.location.trim(),
    purchase_amount: form.purchase_amount,
    purchase_date: form.purchase_date,
    lifespan_months: yearsToMonths(lifespanYears.value),
    status: form.status,
    condition: form.condition,
    // 状态不是在用/闲置时后端会归零；这里照送，让「发出去什么」一目了然
    scrapped_date: form.scrapped_date,
    dispose_note: form.dispose_note,
    note: form.note,
    tags: form.tags,
  }
}

let previewTimer: ReturnType<typeof setTimeout> | null = null

async function runPreview() {
  const payload = buildPayload()
  if (!payload) {
    preview.value = null
    return
  }
  try {
    preview.value = await store.previewItem(payload)
  } catch {
    // 🔴 试算是护栏、不是闸门：它自己失败只收起提示，绝不阻断保存
    preview.value = null
  }
}

/** 输入时防抖 400ms —— 每敲一个字打一次接口既没必要，也会让数字乱跳 */
function schedulePreview() {
  if (previewTimer) clearTimeout(previewTimer)
  previewTimer = setTimeout(runPreview, 400)
}

watch(
  () => [
    form.category_id, form.name, form.purchase_amount, form.purchase_date,
    form.status, form.condition, form.scrapped_date, form.dispose_note,
    lifespanYears.value,
  ],
  schedulePreview,
)

watch(visible, (open) => {
  if (open) schedulePreview()
  else if (previewTimer) clearTimeout(previewTimer)
})

// ─── 保存 ───

async function submit() {
  const payload = buildPayload()
  if (!payload) {
    ElMessage.warning(form.category_id === null ? '先选一个类别' : '物件名称不能为空')
    return
  }
  try {
    await store.saveItem(payload, props.itemId ?? undefined)
    ElMessage.success(isEdit.value ? '已更新' : `已新增「${payload.name}」`)
    visible.value = false
    emit('saved')
  } catch (e: unknown) {
    // 400 的 detail 里带着「报废日期不能早于购买日期」这类**可照做**的话，原样弹出来
    ElMessage.error(extractApiMessage(e, '保存失败'))
  }
}
</script>

<style scoped>
.property-form__suffix {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-form__prefix {
  margin-right: 4px;
  color: var(--el-text-color-secondary);
}
.property-form__hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.property-form__cat-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.property-form__cat {
  width: 200px;
}
.property-form__amount,
.property-form__years {
  width: 150px;
}
.property-form__date {
  width: 170px;
}
.property-form__tags {
  width: 100%;
}
.property-form__preview {
  margin-top: 4px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-light);
  font-size: 13px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
}
.property-form__preview-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}
.property-form__preview-note {
  font-weight: 400;
  color: var(--el-text-color-secondary);
}
.property-form__preview-issues {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
