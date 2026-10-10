<!--
  必需品缺口对账（v3.59.7）

  这一块回答的是**第二把尺子**上的问题：不是「够撑多久」，而是「漏了什么」。

  为什么必须有它（原状的两个洞，都在「用」类上）：

    ① 「用」类的聚合口径曾经是**求和** —— 一件囤得多的东西（洗脸巾折算 4.5 万天）
       就能把整类撑到 4.5 万天，短板永远不落在它身上，而牙膏其实只剩 5 天。
       修法在类别上（`aggregate_mode` 改成 min），已随 v3.59.7 的种子一并修正。
    ② **没录入 ≠ 不缺** —— 牙膏从来没进过系统，公式里就没有它这一项。
       系统只会回答「你录的东西里最少的是哪个」，答不了「你漏了什么」。
       这一块就是补上的那把尺子。

  四条必须守住的展示判据：

  ① **五档各有各的处置，不合并**。未录入要去录入、待补数据要去改配置、
     告急要去补货 —— 一律显示成「算不出来」会把「还没录」说成「配置出错」，
     令人去改一个本来没坏的东西。
  ② **天数不掩码**。天数是推导值、不是隐私项（同 `progress_percentage`）。
     但这块里**没有**任何自由文本字段会落库，故一律不过 `maskFreeText`；
     物品名是**已落库数据的呈现**，按项目隐私判据要掩码 —— 见 `maskName`。
  ③ **空值不补 0**。`expected === null` 显示「—」，绝不显示 0 ——
     0 是「真的撑不了」的结论，与「还没录 / 算不出」是两回事。
  ④ **排序不由前端决定**。后端按紧迫度排好（核心优先 → 档位严重度 → 天数升序），
     这里不重排 —— 重排一次就等于有了第二份顺序口径。
  ⑤ **一条基准项可以挂多件物品**（v3.59.12；睡衣分夏 / 秋 / 冬、
     卫生巾分日用 / 夜用、鞋分室内 / 室外）。组内**取最小、不求和** ——
     这条口径整个在后端（`calc.compute_essential` 的 docstring 有推导），
     这里只做一件事：把 `row.items` 摊开给用户看。
     ⚠️ 「这个数是**哪件**拖出来的」必须一眼可得，否则用户会以为系统算错了 ——
        一件睡裤把「睡衣」压到 20 天，而列表上只写着一个孤零零的 20 天。
     ⚠️ `row.items` 的顺序同样不重排（最短在前、算不出的最后，后端排好的）。
-->
<template>
  <div class="survival-essential" :class="{ 'survival-essential--embedded': props.embedded }">
    <div class="survival-essential__head">
      <div class="survival-essential__title-wrap">
        <span v-if="!props.embedded" class="survival-essential__title">必需品缺口对账</span>
        <span class="survival-essential__subtitle">
          基准清单是「本该有什么」，物品是「实际有多少」；两者逐项对上，
          对不上的就是缺口
        </span>
      </div>
      <div class="survival-essential__actions">
        <el-button size="small" :loading="store.saving" @click="seedList">
          初始化基准清单
        </el-button>
        <el-button size="small" type="primary" @click="openDialog(null)">
          新增基准项
        </el-button>
        <MetricTooltip :meta="reconcileMeta" />
      </div>
    </div>

    <!-- 还没建清单：这是一件「还没做」，不是「坏了」 -->
    <el-empty
      v-if="!isConfigured"
      description="还没有基准清单 —— 点「初始化基准清单」写入一份通用清单，之后可任意增删改"
      :image-size="70"
    />

    <template v-else>
      <!-- 汇总条：一句话说清这份对账到不到位 -->
      <div class="survival-essential__summary">
        <span class="survival-essential__stat">
          核心必需品 <b>{{ summary?.core_total ?? 0 }}</b> 项
        </span>
        <span
          v-if="unclosedCount > 0"
          class="survival-essential__stat survival-essential__stat--gap"
        >
          <el-icon><WarningFilled /></el-icon>
          有 <b>{{ unclosedCount }}</b> 项还没闭合
        </span>
        <span v-else class="survival-essential__stat survival-essential__stat--ok">
          核心项已全部闭合
        </span>

        <template v-if="shortest">
          <span class="survival-essential__divider">·</span>
          <span class="survival-essential__stat">
            最先见底：
            <b>{{ maskedName(shortest.name) }}</b>
            <span class="survival-essential__days">{{ daysText(shortest.days) }}</span>
          </span>
        </template>
      </div>

      <!--
        未闭合的核心项要**点名**：只说「有 4 项没闭合」等于没说 ——
        用户接下来要做的动作（去录哪一件）必须能直接照做。
      -->
      <div v-if="unclosed.length" class="survival-essential__unclosed">
        <span class="survival-essential__unclosed-label">还差：</span>
        <el-tag
          v-for="row in unclosed"
          :key="row.essential_id"
          :type="tagType(row.level)"
          size="small"
          effect="plain"
        >
          {{ maskedName(row.name) }}
          <span class="survival-essential__unclosed-level">
            {{ store.essentialLevelLabel[row.level] ?? row.level }}
          </span>
        </el-tag>
      </div>

      <el-table
        :data="store.essentials"
        size="small"
        row-key="essential_id"
        class="survival-essential__table"
      >
        <el-table-column label="必需品" min-width="150">
          <template #default="{ row }">
            <div class="survival-essential__name-cell">
              <span class="survival-essential__name">{{ maskedName(row.name) }}</span>
              <span class="survival-essential__cat">{{ row.category_name }}</span>
              <el-tooltip v-if="row.hint" :content="row.hint" placement="top">
                <el-icon class="survival-essential__hint-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="性质" width="90">
          <template #default="{ row }">
            <el-tag :type="row.scope === 'core' ? 'danger' : 'info'" size="small" effect="plain">
              {{ store.essentialScopeLabel[row.scope] ?? row.scope }}
            </el-tag>
          </template>
        </el-table-column>

        <!--
          关联物品用**行内下拉**：对账的绝大多数操作就是「把我柜子里这件
          挂到那条基准上」，那应该是一次点击，不是去另一个页面填一串数字。
        -->
        <el-table-column label="对应物品" min-width="210">
          <template #default="{ row }">
            <!--
              多选（v3.59.12）：一条基准项常常要几件并列才成立。
              `collapse-tags` 让夏/秋/冬三件睡衣不把行高撑起来，
              `collapse-tags-tooltip` 保证折叠之后仍看得见全选了哪几件 ——
              少了它，用户会以为只挂上了一件。
            -->
            <el-select
              :model-value="linkedIds(row)"
              multiple
              collapse-tags
              collapse-tags-tooltip
              clearable
              filterable
              size="small"
              placeholder="未录入"
              class="survival-essential__select"
              @update:model-value="(v: number[]) => onLink(row, v)"
            >
              <el-option
                v-for="it in itemsOfCategory(row.category_id)"
                :key="it.id"
                :label="it.name"
                :value="it.id"
              />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column label="可支撑" width="110">
          <template #default="{ row }">
            <el-tooltip v-if="row.expected !== null" placement="top">
              <!--
                ⚠️ 这里必须用 `#content` 插槽，不能像单值时那样传 `content` 字符串：
                   多件时要说清「是**哪件**拖出来的」，那需要多行。
                ⚠️ 行内样式而不是 class：tooltip 的内容会被 teleport 到 body，
                   scoped 样式够不着它 —— 用 class 会一行样式都不生效，
                   而且不报错（同「取不到就静默不渲染」那类坑）。
              -->
              <template #content>
                <div style="line-height: 1.7">
                  <div
                    v-for="it in row.items"
                    :key="it.item_id"
                    :style="it.item_id === row.item_id ? 'font-weight: 600' : ''"
                  >
                    {{ maskedName(it.item_name) }}：{{ daysText(it.expected) }}
                  </div>
                  <div v-if="row.items.length > 1" style="margin-top: 4px">
                    共 {{ row.items.length }} 件并列，取最短那件
                  </div>
                  <div style="margin-top: 4px; opacity: 0.8">{{ tripleText(row) }}</div>
                </div>
              </template>
              <span class="survival-essential__days">{{ daysText(row.expected) }}</span>
            </el-tooltip>
            <span v-else class="survival-essential__days survival-essential__days--none">—</span>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="tagType(row.level)" size="small" effect="dark">
              {{ store.essentialLevelLabel[row.level] ?? row.level }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" align="right">
          <template #default="{ row }">
            <el-button link size="small" @click="openDialog(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="removeRow(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <SurvivalEssentialDialog
      v-model="dialogVisible"
      :row="editingRow"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * ⚠️ 这一块里**没有任何算法或阈值**：
 *    档位（adequate / tight / …）与覆盖天数全部由后端算好放在每行的 `level`
 *    与 `expected` 里。前端只做两件事 —— 展示、上色。
 *    在这里补一个「其实 30 天以下就算告急」的判断，口径就有了两份，
 *    改后端时必然漏改（而且不一致是静默的：两边都能显示出看着合理的颜色）。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { InfoFilled, WarningFilled } from '@element-plus/icons-vue'
import MetricTooltip from '@/modules/wealth/components/common/MetricTooltip.vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import SurvivalEssentialDialog from './SurvivalEssentialDialog.vue'
import type { SurvivalEssential, SurvivalEssentialLevel } from '../../types/survivalTypes'

/**
 * `embedded` —— 供弹窗外壳（`SurvivalReconcileDialog`）使用的**外观开关**：
 * 去掉卡片外壳与自带标题（弹窗自己已经有标题栏，再来一行是重复的同一句话）。
 *
 * ⚠️ 它只影响外观，**不动任何取数、展示或分档** —— 换个壳不该改变这里显示的东西。
 *    （若哪天它开始影响内容，就说明有人在壳里做了业务判断，那应该收回面板里。）
 */
const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })

const store = useSurvivalStore()
const { maskName } = usePrivacyMask()

const dialogVisible = ref(false)
const editingRow = ref<SurvivalEssential | null>(null)

const isConfigured = computed(() => store.essentialReconcile?.is_configured ?? false)
const summary = computed(() => store.essentialSummary)
const unclosed = computed(() => store.essentialUnclosed)
const unclosedCount = computed(() => summary.value?.unclosed_core_count ?? 0)
const shortest = computed(() => store.essentialShortest)
const reconcileMeta = computed(() => store.metricMetaByKey['essential_reconcile'] ?? null)

onMounted(() => {
  if (!store.essentials.length) store.fetchEssentials()
  store.fetchMeta()
})

/**
 * 档位 → el-tag 的类型
 *
 * ⚠️ 这里只做「severity → 颜色」的映射，**不重新分档**。
 *    `unknown` 与 `tight` 都用 warning：它们都表示「要留意但不用慌」，
 *    而 `missing` 用 info 是刻意的 —— 未录入是一件待办，不是警报。
 */
function tagType(level: SurvivalEssentialLevel | string): 'info' | 'warning' | 'danger' | 'success' | 'primary' {
  switch (level) {
    case 'critical':
      return 'danger'
    case 'unknown':
    case 'tight':
      return 'warning'
    case 'adequate':
      return 'success'
    default:
      return 'info'
  }
}

/** 天数文案 —— **空值绝不补 0** */
function daysText(days: number | null): string {
  if (days === null) return '—'
  return `${Number(days.toFixed(1))} 天`
}

/** 三档铺开：这个数是怎么来的，要摊得开 */
function tripleText(row: SurvivalEssential): string {
  const d = row.days
  return `省着用 ${daysText(d.optimistic)} / 正常 ${daysText(d.likely)} / 费着用 ${daysText(d.pessimistic)}`
}

/**
 * 这一行当前挂了哪几件（多选下拉的 `:model-value`）
 *
 * ⚠️ 取 `items` 数组而不是顶层的 `item_id` —— 顶层那个是**代表件**
 *    （正常用量下最短的那件），拿它回显会让另外几件在界面上消失。
 */
function linkedIds(row: SurvivalEssential): number[] {
  return row.items.map((it) => it.item_id)
}

/** 两个 id 集合是否等价 —— 顺序无关：多选下拉的勾选顺序不保证与后端返回一致 */
function sameIds(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false
  const set = new Set(a)
  return b.every((id) => set.has(id))
}

/** 同类别下的物品 —— 跨类别关联通常是选错了，所以不列别的类别 */
function itemsOfCategory(categoryId: number | null) {
  if (categoryId === null) return store.items
  return store.items.filter((it) => it.category_id === categoryId)
}

/** 已在别的基准项上关联过的物品仍可出现：一件东西可以同时是两件事的必需品 */
function maskedName(name: string): string {
  return maskName(name)
}

function openDialog(row: SurvivalEssential | null) {
  editingRow.value = row
  dialogVisible.value = true
}

function onSaved() {
  dialogVisible.value = false
}

async function onLink(row: SurvivalEssential, itemIds: number[]) {
  // ⚠️ 比的是**集合**不是长度：多选下拉在你取消一个又勾回同一个时，
  //    也会发一次 change —— 不做等价判断就会白刷一次并把列表"闪"一下。
  if (sameIds(linkedIds(row), itemIds)) return
  try {
    await store.linkEssentialItems(row.essential_id, itemIds)
    ElMessage.success(
      itemIds.length ? `已关联 ${itemIds.length} 件` : '已解除关联',
    )
  } catch (e) {
    ElMessage.error(extractMessage(e, '关联失败'))
  }
}

async function removeRow(row: SurvivalEssential) {
  try {
    await ElMessageBox.confirm(
      `确定删除基准项「${row.name}」吗？这只会去掉这条「本该有」的记录，` +
        '不会删除任何库存物品。',
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeEssential(row.essential_id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(extractMessage(e, '删除失败'))
  }
}

async function seedList() {
  try {
    const result = await store.seedEssentials()
    // ⚠️ 被跳过的项要**说出来**：静默跳过会让人以为清单本来就这么长
    if (result.missing_categories.length) {
      ElMessage.warning(
        `已写入 ${result.created} 项；` +
          `以下类别还不存在，相关基准项已跳过：${result.missing_categories.join('、')}`,
      )
    } else {
      ElMessage.success(
        result.created ? `已写入 ${result.created} 项基准清单` : '清单已是最新，无需重写',
      )
    }
  } catch (e) {
    ElMessage.error(extractMessage(e, '初始化失败'))
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
.survival-essential {
  margin-top: 16px;
  padding: 12px 14px 6px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
}
/* 弹窗里的形态：外壳与自带标题都去掉 —— 弹窗自己就是那层容器，
   再套一层带边框的卡会在弹窗里形成「框里的框」，而且窄屏下白边叠白边。 */
.survival-essential--embedded {
  margin-top: 0;
  padding: 0;
  border: none;
  border-radius: 0;
  background: transparent;
}
.survival-essential__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.survival-essential__title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.survival-essential__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.survival-essential__subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-essential__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.survival-essential__summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--el-text-color-regular);
  padding: 6px 10px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}
.survival-essential__stat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.survival-essential__stat--gap {
  color: var(--el-color-warning);
}
.survival-essential__stat--ok {
  color: var(--el-color-success);
}
.survival-essential__divider {
  color: var(--el-text-color-placeholder);
}
.survival-essential__unclosed {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin: 10px 0 4px;
}
.survival-essential__unclosed-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-essential__unclosed-level {
  margin-left: 4px;
  opacity: 0.75;
}
.survival-essential__table {
  margin-top: 6px;
}
.survival-essential__name-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.survival-essential__name {
  font-weight: 500;
}
.survival-essential__cat {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-essential__hint-icon {
  color: var(--el-text-color-placeholder);
  cursor: help;
}
.survival-essential__select {
  width: 100%;
}
.survival-essential__days {
  font-variant-numeric: tabular-nums;
}
.survival-essential__days--none {
  color: var(--el-text-color-placeholder);
}
</style>
