<!--
  单件盘点（v3.60.2）

  存在的理由：**真实用法就是一次盘一两件。**

  实测（2026-09-29，7 天内 6 次盘点、共 8 行）：平均每次 1.3 行，
  其中 4 次只盘了 1 件。而优化之前，想改其中一件的数量只有两条路：

    ① 走「编辑物品」—— 那是改**主数据**（名称 / 单位 / 类别 / 保质期 /
       计量口径 / 补货线…），为了改一个数字要开一张大表单，且容易误改别的字段；
    ② 打开「实盘盘点」弹窗，在一张 43 行的表里把它找出来。

  ⇒ 「改库存」是日常动作、「改主数据」是配置动作，两者不该共用一个入口
     （同「一个字段只承担一件事」）。

  ⚠️ 它与批量弹窗共用同一套铁律，一条都没放宽：

  ① **提交即校准**。提交之后这件的库存会**直接变成实盘数**。
     这句话写在按钮上方，并在确认框里再说一次。
  ② **账面是打开时读的**，真实写入时服务端会**再读一次** ——
     所以这里的账面是参考，不是将要写进历史的值；盈亏一律以后端返回为准。
  ③ **删记录不回滚库存**（写在确认框里，同批量弹窗）。

  ⚠️ 只提交**这一件**：`lines` 永远只有一行。不必也不该顺带写别的物品 ——
     用户只数了这一件，多写一行就等于替他宣称「另一件我也数过了」。
-->

<template>
  <el-dialog
    v-model="visible"
    :title="`盘一下 · ${name || '—'}`"
    width="440px"
    :close-on-click-modal="false"
    @open="onOpen"
  >
    <el-skeleton v-if="loading" :rows="2" animated />

    <template v-else>
      <div class="quick-stocktake__row">
        <div class="quick-stocktake__cell">
          <div class="quick-stocktake__label">账面（系统记的）</div>
          <div class="quick-stocktake__book">
            {{ formatQuantity(bookQuantity, unitName) }}
          </div>
        </div>
        <el-icon class="quick-stocktake__arrow"><Right /></el-icon>
        <div class="quick-stocktake__cell">
          <div class="quick-stocktake__label">实盘（我数出来的）</div>
          <el-input-number
            v-model="actual"
            :min="0"
            :step="1"
            :precision="2"
            size="small"
            controls-position="right"
            class="quick-stocktake__input"
            @keyup.enter="submit"
          />
        </div>
      </div>

      <div class="quick-stocktake__delta">
        <span class="quick-stocktake__delta-label">盈亏</span>
        <el-tag :type="deltaKindType(deltaKind)" size="small" effect="plain">
          {{ formatStocktakeDelta(delta) }}
        </el-tag>
        <span v-if="delta === 0" class="quick-stocktake__delta-hint">
          与账面一致 —— 库存不变，但会留下这次核对记录
        </span>
      </div>

      <!-- 低于补货线只**预告**，不在这里改库存 —— 补货是另一件事 -->
      <el-alert
        v-if="belowThreshold"
        type="warning"
        :closable="false"
        show-icon
        class="quick-stocktake__alert"
        :title="`改完之后会低于补货线（${restockThreshold} ${unitName}），物品清单里会标「该补货」—— 补货请去那里改数量。`"
      />

      <div class="quick-stocktake__extra">
        <el-date-picker
          v-model="date"
          type="date"
          size="small"
          value-format="YYYY-MM-DD"
          placeholder="盘点日期（默认今天）"
          class="quick-stocktake__date"
        />
        <el-input
          v-model="note"
          size="small"
          maxlength="200"
          placeholder="备注（选填）"
          class="quick-stocktake__note"
        />
      </div>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="quick-stocktake__alert"
        :title="calibrateWarning"
      />
    </template>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button
        size="small"
        type="primary"
        :loading="store.saving"
        :disabled="loading"
        @click="submit"
      >
        提交校准
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Right } from '@element-plus/icons-vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import {
  deltaKindType, formatQuantity, formatStocktakeDelta,
} from '../../utils/survivalFormat'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  /** 要盘的那一件；null = 没打开 */
  itemId: number | null
  /** 父级已经知道的名称与账面 —— 先渲染出来，再等接口回来的更准的值 */
  fallbackName: string
  fallbackBookQuantity: number | null
  fallbackUnitName: string
  fallbackRestockThreshold: number | null
}>()

const emit = defineEmits<{
  submitted: []
}>()

const store = useSurvivalStore()

const loading = ref(false)
const actual = ref<number>(0)
const note = ref('')
const date = ref<string>('')

/** 接口回来之后以最新的为准；没回来就用父级传的那份先渲染 */
const sheetRow = ref<{
  name: string
  book_quantity: number | null
  unit_name: string
  restock_threshold: number | null
} | null>(null)

const name = computed(() => sheetRow.value?.name ?? props.fallbackName)
const unitName = computed(() => sheetRow.value?.unit_name ?? props.fallbackUnitName)
const bookQuantity = computed(
  () => sheetRow.value?.book_quantity ?? props.fallbackBookQuantity,
)
const restockThreshold = computed(
  () => sheetRow.value?.restock_threshold ?? props.fallbackRestockThreshold,
)

const delta = computed(() =>
  Number(((actual.value ?? 0) - (bookQuantity.value ?? 0)).toFixed(2)),
)

/** 与后端同一个三态语义：0 是核对无误，不是「差异为零」 */
const deltaKind = computed(() => {
  if (delta.value > 0) return 'surplus'
  if (delta.value < 0) return 'deficit'
  return 'flat'
})

const belowThreshold = computed(
  () => restockThreshold.value !== null && (actual.value ?? 0) <= restockThreshold.value,
)

const calibrateWarning = computed(() => {
  if (delta.value === 0) {
    return `提交后这件的库存仍是 ${formatQuantity(actual.value, unitName.value)}（与账面一致），`
      + '但会留下这次核对记录。'
  }
  return `提交后这件的库存会被直接改成 ${formatQuantity(actual.value, unitName.value)}（盘点即校准）。`
})

/**
 * 打开时只为**这一件**取最新一行。
 *
 * ⚠️ 走 `fetchWorksheetRows()` 而不是 `fetchWorksheet()`：
 *    后者会把共享的全量工作表替换成一行，清单页的「上次盘点」列
 *    随即整片落空 —— 而且界面不会报错（见 store 里的说明）。
 * ⚠️ 取不到（网络抖动 / 这件已被别处删掉）就退回父级那份，
 *    不让一次读失败挡住「把它数下来」这件事。
 */
async function onOpen() {
  note.value = ''
  date.value = ''
  actual.value = props.fallbackBookQuantity ?? 0
  sheetRow.value = null
  if (props.itemId === null) return
  loading.value = true
  try {
    const rows = await store.fetchWorksheetRows([props.itemId])
    const row = rows[0]
    if (row) {
      sheetRow.value = {
        name: row.name,
        book_quantity: row.book_quantity,
        unit_name: row.unit_name,
        restock_threshold: row.restock_threshold,
      }
      // 拿到新账面之后重设默认值 —— 默认「与账面一致」是最常见的结论
      actual.value = row.book_quantity ?? 0
    }
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (props.itemId === null) return
  try {
    await ElMessageBox.confirm(
      `「${name.value}」的库存会被改成你填的实盘数，不是只读核对。`
      + '记录会留档；之后删掉它也不会把库存改回来（要改数量请回到这里再盘一次）。确认提交？',
      '提交即校准库存',
      { type: 'warning', confirmButtonText: '提交', cancelButtonText: '再核一遍' },
    )
  } catch {
    return
  }
  try {
    await store.submitStocktake({
      date: date.value || null,
      note: note.value.trim(),
      source: 'manual',
      // ⚠️ 永远只有一行 —— 用户只数了这一件
      lines: [{ item_id: props.itemId, actual_quantity: actual.value ?? 0 }],
    })
    ElMessage.success(`已盘点「${name.value}」，库存已按实盘校准`)
    emit('submitted')
    visible.value = false
  } catch (e: unknown) {
    ElMessage.error(extractMessage(e, '盘点失败'))
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
.quick-stocktake__row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.quick-stocktake__cell {
  flex: 1;
  min-width: 0;
}
.quick-stocktake__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.quick-stocktake__book {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.quick-stocktake__arrow {
  color: var(--el-text-color-placeholder);
  margin-top: 16px;
}
.quick-stocktake__input {
  width: 100%;
}
.quick-stocktake__delta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.quick-stocktake__delta-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.quick-stocktake__delta-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.quick-stocktake__alert {
  margin-top: 10px;
}
.quick-stocktake__extra {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}
.quick-stocktake__date {
  width: 175px;
}
.quick-stocktake__note {
  flex: 1;
}
</style>
