<!--
  实盘盘点弹窗（v3.59.3；v3.60.2 改造：**只列挑中的那几件**）

  ⚠️ 与「记录一次结论」（快照）是**两件事**，不要合并：
     快照 = 系统算出来的结论，点一下就落一份，不需要人动手；
     盘点 = 人填进去的实盘，得一件件数出来。

  ══════════════════════════════════════════════════════════════
  🔴 2026-09-29 改造：「挑选物品」不在这里做了
  ══════════════════════════════════════════════════════════════

  改造前：这个弹窗里有一张**全量 43 行**的表，带勾选框与「搜物品名」。
          而「物品清单」里本来就有一套更完备的挑选（搜名 / 筛类别 / 筛计量口径 /
          只看该盘的 / 只看该补货的，5 个筛选）与一个「盘点选中的 N 件」按钮。

  ⇒ 于是最短的路径是：清单里筛好、勾好 → 打开弹窗 → 弹窗又给一份 43 件全量、
    筛选条件全丢 → **再找一遍那件** → 填数。中间那一段是纯损耗。

  改造后：挑物品**只留清单页一处**（用强的那个，见设计稿 §五 岔路口 1），
          弹窗只负责「确认与提交」：打开即是你刚才勾的那几件，直接填数。

  为什么这样切 —— 实测用法（2026-09-29：7 天内 6 次盘点、共 8 行、平均 1.3 行）：
  用户是**随手抽查一两件**，而弹窗每次都要他为「改一个数字」翻一遍 43 行。

  三条必须让用户看见的事（一条都没放宽）：

  ① **提交即校准**。提交之后库存会**直接变成实盘数**，不是只读核对。
     这句话必须在按钮上方写出来，并在确认框里再说一次 ——
     「我数过了」是改账的动作，不说明就等于悄悄改账。
  ② **账面数是打开弹窗时读的**。真实写入时服务端会**再读一次**（防的是
     盘点页开着半小时、其间库存在别处已经变过这种必然发生的过期读）。
     所以界面上那句「账面」是参考，不是将要写进历史的值。
     盈亏的最终结果一律以后端返回的为准 —— 这里的实时差只是**回显**，
     不是口径。别把这段减法当成第二份真源。
  ③ **默认「不勾 = 不盘」**。没勾的物品不进这次盘点，也不会被校准成 0。
     这是最容易出灾难的地方：把没勾的当成 0 提交，等于一键清空库存。
     服务层只接受显式传来的行，这里也绝不为未勾选的行补默认值。

  ⚠️ 弹窗内的排序**按「最久没盘」**（复用 `sortRowsByStaleness`）：
     数东西时最该先数的是最久没数过的，而不是字母序或建库序。
     注意这只是**排序**，它不改任何标签 —— 「该盘了」仍由后端按
     「设了周期且已到期」判定（见 `utils/survivalStocktake.ts` 的说明）。
-->

<template>
  <el-dialog
    v-model="visible"
    title="实盘盘点"
    width="760px"
    :close-on-click-modal="false"
    @open="onOpen"
  >
    <!-- 防御性分支：入口已保证有预设，正常走不到这里 -->
    <el-alert
      v-if="!presetItemIds.length"
      type="info"
      :closable="false"
      show-icon
      title="没有挑中的物品 —— 盘点从「物品清单」里挑：勾选要数的几件，再点「盘点选中的 N 件」"
    />

    <template v-else>
      <div class="survival-stocktake__bar">
        <el-date-picker
          v-model="date"
          type="date"
          size="small"
          value-format="YYYY-MM-DD"
          placeholder="盘点日期（默认今天）"
          class="survival-stocktake__date"
        />
        <el-button link size="small" :disabled="rows.length === checked.length" @click="selectAll">
          全选
        </el-button>
        <el-button link size="small" :disabled="!checked.length" @click="checked = []">
          全不选
        </el-button>
        <span class="survival-stocktake__count">
          已选 {{ checked.length }} / {{ rows.length }} 件
        </span>
      </div>

      <el-alert
        v-if="missingCount"
        type="info"
        :closable="false"
        show-icon
        class="survival-stocktake__alert"
        :title="`有 ${missingCount} 件在清单里已经找不到了（可能刚被删掉），本次会跳过它们`"
      />

      <el-alert
        v-if="!checked.length"
        type="warning"
        :closable="false"
        show-icon
        class="survival-stocktake__alert"
        title="一件都没勾 —— 没勾的物品不会被盘，库存也不会被动。"
      />

      <el-table
        :data="rows"
        size="small"
        max-height="380"
        class="survival-stocktake__table"
        @row-click="toggle"
      >
        <el-table-column width="46">
          <template #default="{ row }">
            <el-checkbox
              :model-value="checked.includes(row.item_id)"
              @click.stop
              @change="toggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="物品" min-width="130">
          <template #default="{ row }">
            <span class="survival-stocktake__name">{{ row.name }}</span>
            <el-tag v-if="row.stocktake_due" type="warning" size="small" effect="plain">该盘了</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category_name" label="类别" width="80" />
        <el-table-column label="账面" width="110">
          <template #default="{ row }">
            {{ formatQuantity(row.book_quantity, row.unit_name) }}
          </template>
        </el-table-column>
        <el-table-column label="上次盘点" width="150">
          <template #default="{ row }">
            {{ formatLastStocktake(row.last_stocktake_date, row.days_since_stocktake) }}
          </template>
        </el-table-column>
        <el-table-column label="实盘" width="150">
          <template #default="{ row }">
            <el-input-number
              :model-value="actualOf(row)"
              :min="0"
              :step="1"
              :precision="2"
              :disabled="!checked.includes(row.item_id)"
              size="small"
              controls-position="right"
              class="survival-stocktake__input"
              @update:model-value="(value: number | null) => setActual(row, value)"
              @click.stop
            />
          </template>
        </el-table-column>
        <el-table-column label="盈亏" width="90">
          <template #default="{ row }">
            <el-tag
              v-if="checked.includes(row.item_id)"
              :type="deltaKindType(previewKind(row))"
              size="small"
              effect="plain"
            >
              {{ formatStocktakeDelta(previewDelta(row)) }}
            </el-tag>
            <span v-else class="survival-stocktake__muted">不盘</span>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <el-form label-width="70px" size="small" class="survival-stocktake__form">
      <el-form-item label="备注">
        <el-input v-model="note" maxlength="200" placeholder="选填；例如「囤了一箱，本次只点了干货」" />
      </el-form-item>
    </el-form>

    <el-alert
      v-if="checked.length"
      type="warning"
      :closable="false"
      show-icon
      class="survival-stocktake__alert"
      :title="calibrateWarning"
    />

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button
        size="small"
        type="primary"
        :loading="store.saving"
        :disabled="!checked.length"
        @click="submit"
      >
        提交盘点（{{ checked.length }} 件）
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSurvivalStore } from '../../stores/survivalStore'
import {
  deltaKindType, formatLastStocktake, formatQuantity, formatStocktakeDelta,
} from '../../utils/survivalFormat'
import { sortRowsByStaleness } from '../../utils/survivalStocktake'
import type { SurvivalWorksheetRow } from '../../types/survivalTypes'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  /** 从物品清单带过来的那批 id；**空数组 = 没挑东西**（正常入口不会为空） */
  presetItemIds: number[]
}>()

const emit = defineEmits<{
  submitted: []
}>()

const store = useSurvivalStore()

const note = ref('')
const date = ref<string>('')
const checked = ref<number[]>([])
/** 实盘数按 item_id 存；**没进这个 map 的行不会提交** */
const actuals = ref<Record<number, number>>({})

/** 打开时定下来的候选集；此后不再变（用户取消勾选也不消失，便于反悔） */
const candidateIds = ref<number[]>([])

/**
 * 只列**挑中的那几件**，按「最久没盘」排序。
 *
 * ⚠️ 过滤是必要的、不是洁癖：`store.worksheet` 是打开弹窗那一刻拉的全量，
 *    而候选 id 里可能有已经被删掉的（用户先在清单勾好、其间又在别处删了）。
 *    直接渲染会在表里留下一行没有账面、也提交不上去的幽灵行。
 */
const rows = computed<SurvivalWorksheetRow[]>(() =>
  sortRowsByStaleness(
    store.worksheet.filter((row) => candidateIds.value.includes(row.item_id)),
  ),
)

/** 挑中了、但清单里已经找不到的件数 —— 说出来，不静默少算 */
const missingCount = computed(
  () => candidateIds.value.length - rows.value.length,
)

/** ⚠️ 只作回显。真正的账面由服务端在提交那一刻重读，见文件头 ② */
function bookOf(row: SurvivalWorksheetRow): number {
  return row.book_quantity ?? 0
}

function actualOf(row: SurvivalWorksheetRow): number {
  return actuals.value[row.item_id] ?? bookOf(row)
}

function setActual(row: SurvivalWorksheetRow, value: number | null) {
  actuals.value[row.item_id] = value ?? 0
}

function previewDelta(row: SurvivalWorksheetRow): number {
  return Number((actualOf(row) - bookOf(row)).toFixed(2))
}

/** 与后端同一个三态语义：0 是核对无误，不是「差异为零」 */
function previewKind(row: SurvivalWorksheetRow): string {
  const delta = previewDelta(row)
  if (delta > 0) return 'surplus'
  if (delta < 0) return 'deficit'
  return 'flat'
}

const calibrateWarning = computed(() => {
  const picked = store.worksheet.filter((row) => checked.value.includes(row.item_id))
  const diff = picked.filter((row) => previewDelta(row) !== 0).length
  const head = `提交后这 ${picked.length} 件物品的库存会被直接改成实盘数（盘点即校准）。`
  return diff
    ? `${head}其中 ${diff} 件与账面不一致，改的就是它们。`
    : `${head}本次全部与账面一致，库存不会变化，但会留下这次核对记录。`
})

function toggle(row: SurvivalWorksheetRow) {
  const index = checked.value.indexOf(row.item_id)
  if (index >= 0) {
    checked.value.splice(index, 1)
    delete actuals.value[row.item_id]
    return
  }
  checked.value.push(row.item_id)
  // 默认等于账面：逐件核对时「没变化」是最常见的结论，应当一键写下
  if (actuals.value[row.item_id] === undefined) actuals.value[row.item_id] = bookOf(row)
}

/** 只勾**当前列出来的** —— 看不见的行被悄悄勾上是说不清的 */
function selectAll() {
  for (const row of rows.value) {
    if (!checked.value.includes(row.item_id)) checked.value.push(row.item_id)
    if (actuals.value[row.item_id] === undefined) actuals.value[row.item_id] = bookOf(row)
  }
}

/**
 * 打开时重拉工作表。
 *
 * 不是洁癖：这份数据带着「账面」与「上次盘点」，而这两样都会随时间变 ——
 * 打开弹窗就要新读一次，否则用户数的是一件、系统记的是另一件。
 *
 * ⚠️ 拉的是**全量**（不带 `item_ids`）：这份数据同时喂着清单页与类别明细的
 *    「上次盘点」列。只取子集会把那两处的列打空，而界面不会报错。
 *    要「只取几件」的是**单件盘点**弹窗，走 `fetchWorksheetRows()`。
 */
async function onOpen() {
  note.value = ''
  date.value = ''
  checked.value = []
  actuals.value = {}
  candidateIds.value = [...props.presetItemIds]
  await store.fetchWorksheet()
  // 挑中的默认**全部勾上**：它们是用户刚从清单里选出来的，
  // 再让他确认一遍「我确实要盘这几件」是多余的一道（要跳过某件，取消它即可）
  for (const row of rows.value) {
    checked.value.push(row.item_id)
    actuals.value[row.item_id] = bookOf(row)
  }
}

async function submit() {
  if (!checked.value.length) {
    ElMessage.warning('先勾要盘的物品')
    return
  }
  try {
    await ElMessageBox.confirm(
      `这 ${checked.value.length} 件物品的库存会被改成你填的实盘数，不是只读核对。`
      + '记录会留档；之后删掉它也不会把库存改回来（要改数量请去编辑物品）。确认提交？',
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
      lines: checked.value.map((id) => ({
        item_id: id,
        actual_quantity: actuals.value[id] ?? 0,
      })),
    })
    ElMessage.success(`已盘点 ${checked.value.length} 件，库存已按实盘校准`)
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
.survival-stocktake__bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.survival-stocktake__date {
  width: 180px;
}
.survival-stocktake__count {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-stocktake__alert {
  margin-bottom: 10px;
}
.survival-stocktake__table {
  width: 100%;
  margin-bottom: 10px;
}
.survival-stocktake__name {
  margin-right: 6px;
  font-weight: 600;
}
.survival-stocktake__input {
  width: 120px;
}
.survival-stocktake__muted {
  color: var(--el-text-color-placeholder);
}
.survival-stocktake__form {
  margin-top: 4px;
}
</style>
