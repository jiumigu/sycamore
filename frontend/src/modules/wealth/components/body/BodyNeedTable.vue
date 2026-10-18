<!--
  身上之物 · 清单（v3.62.4）

  这一块回答的是「我列的这些位，现在都什么情况」，并且**行内就能改**
  —— 记「找到了没有」应当是随手一下的事，不该每次都开弹窗。

  🔴 三条展示纪律（都是本项目踩过的地方）：

     ① **空 ≠ 凑合**。`satisfaction` 为 null 时，格子里显示的是后端下发的
        `blank_reason` 短字（「—」= 还没有东西在用 / 「未评」= 有东西在用但没评过）。
        前端**不自己写这两个字**、也**不拿 `property_id` 自己推** ——
        那是第二份口径，改后端时它不会被改到，而界面上照旧说得通。

     ② **三把尺子互不推导**。进度、满意、归属是三列，各自独立改 ——
        本组件不做任何「改了这个就顺手改那个」的联动。
        「已找到 + 凑合」与「寻找中 + 称心」都是合法状态，不是矛盾数据。

     ③ **徽标是只读的**。真源在好恶物档案馆，本模块不新建、不修改评价；
        点它去**那一条**档案。`null` = 还没评过 ⇒ 什么都不显示
        （不是灰色的「无」——那会让「没人评过」看起来像「评过了、结论是没有」）。

  ⚠️ 筛选在**前端**做（列表量级小），但顶部那个数来自后端汇总 ——
     两者的判据同源（都走 `find_status != 'settled'`），所以数一定对得上。
-->

<template>
  <div class="body-table">
    <div class="body-table__filters">
      <el-input
        v-model="search"
        size="small"
        placeholder="搜要什么"
        clearable
        class="body-table__search"
      />
      <el-select
        v-model="part"
        size="small"
        clearable
        placeholder="全部部位"
        class="body-table__select"
      >
        <el-option
          v-for="option in store.parts"
          :key="option.id"
          :label="option.name"
          :value="option.id"
        />
      </el-select>
      <el-select
        v-model="status"
        size="small"
        clearable
        placeholder="全部进度"
        class="body-table__select"
      >
        <el-option
          v-for="option in store.findStatusOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-button v-if="hasFilter" link size="small" type="primary" @click="clearFilters">
        清空筛选
      </el-button>
      <!--
        🔴 计数读的是**全量结果**，不是「这一页」；有筛选时把被筛掉的也念出来 ——
           筛剩 2 条却显示「共 2 条」，读作「我只列了 2 条」，而实际只是条件挡住了其余。
      -->
      <span class="body-table__count">{{ countLabel }}</span>
    </div>

    <el-empty v-if="!rows.length" :description="emptyText" :image-size="60" />

    <el-table v-else :data="rows" size="small" class="body-table__grid" row-key="id">
      <el-table-column label="部位" width="92">
        <template #default="{ row }">
          <span class="body-table__part">{{ row.part_name }}</span>
        </template>
      </el-table-column>

      <el-table-column label="要什么" min-width="130">
        <template #default="{ row }">
          <span class="body-table__name">{{ row.name }}</span>
        </template>
      </el-table-column>

      <el-table-column label="进度" width="118">
        <template #header>
          <span class="body-table__head">
            进度
            <MetricTooltip :meta="metaByKey.find_status" :width="360" />
          </span>
        </template>
        <template #default="{ row }">
          <el-select
            :model-value="row.find_status"
            size="small"
            class="body-table__inline-select"
            @change="(value: string) => onStatusChange(row, value)"
          >
            <el-option
              v-for="option in store.findStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </template>
      </el-table-column>

      <el-table-column label="满意" width="112">
        <template #header>
          <span class="body-table__head">
            满意
            <MetricTooltip :meta="metaByKey.satisfaction" :width="380" />
          </span>
        </template>
        <template #default="{ row }">
          <!--
            🔴 留空时格子里的字来自后端（「—」/「未评」），
               并且**是灰的** —— 它是「还没评」，不是「评价结果」。
          -->
          <el-tooltip
            :content="blankLabel(row)"
            placement="top"
            :show-after="120"
            :disabled="!row.satisfaction_blank_reason"
          >
            <el-select
              :model-value="row.satisfaction"
              size="small"
              clearable
              class="body-table__inline-select"
              :placeholder="blankShort(row)"
              @change="(value: string | null) => onSatisfactionChange(row, value)"
            >
              <el-option
                v-for="option in store.satisfactionOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-tooltip>
        </template>
      </el-table-column>

      <el-table-column label="用的是哪一件" min-width="220">
        <template #header>
          <span class="body-table__head">
            用的是哪一件
            <MetricTooltip :meta="metaByKey.linked_item" :width="380" />
          </span>
        </template>
        <template #default="{ row }">
          <div v-if="row.linked_kind" class="body-table__link">
            <span class="body-table__link-kind">{{ row.linked_kind_label }}</span>
            <span class="body-table__link-name">{{ row.linked_name }}</span>
            <!--
              档案馆徽标 —— **只读**：点它去那一条补理由，不在这里新建评价。
              ⚠️ 本模块的「满意」与它是两把正交的尺子，结论相反是允许的；
                 界面不做任何「要不要同步」的提示。
            -->
            <el-tag
              v-if="row.treasure_badge"
              size="small"
              effect="dark"
              :type="row.treasure_badge === '歹' ? 'danger' : 'success'"
              class="body-table__badge"
              @click="openTreasure(row)"
            >
              {{ row.treasure_badge === '歹' ? '👎 踩坑' : '👍 好物' }}
            </el-tag>
          </div>
          <span v-else class="body-table__muted">没挂东西</span>
        </template>
      </el-table-column>

      <el-table-column label="想找什么样的" min-width="200">
        <template #header>
          <span class="body-table__head">
            想找什么样的
            <MetricTooltip :meta="metaByKey.wish" :width="340" />
          </span>
        </template>
        <template #default="{ row }">
          <span v-if="row.wish" class="body-table__wish">{{ row.wish }}</span>
          <span v-else class="body-table__muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="104" fixed="right">
        <template #default="{ row }">
          <el-button link size="small" @click="emit('edit', row.id)">编辑</el-button>
          <el-button link size="small" type="danger" @click="emit('delete', row.id)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MetricTooltip from '../common/MetricTooltip.vue'
import { useBodyStore } from '../../stores/bodyStore'
import { extractApiMessage } from '../../utils/propertyError'
import { blankReasonLabel, blankReasonShort } from '../../types/bodyTypes'
import type { BodyNeed, BodySatisfaction } from '../../types/bodyTypes'
import type { RatioMeta } from '../../types/wealthTypes'

const props = defineProps<{
  /** 全部位（未筛选）—— 筛选在这个组件里做 */
  needs: BodyNeed[]
  metaByKey: Record<string, RatioMeta>
}>()

const emit = defineEmits<{
  edit: [id: number]
  delete: [id: number]
}>()

const store = useBodyStore()
const router = useRouter()

// ─── 筛选项（`defineModel`：顶部计数的点击要能直接改这几项） ───
const search = defineModel<string>('search', { default: '' })
const part = defineModel<number | null>('part', { default: null })
const status = defineModel<string>('status', { default: '' })
/** true = 只看没搞定的（顶部那个数字点下去就是它） */
const pendingOnly = defineModel<boolean>('pending', { default: false })

const hasFilter = computed(
  () => !!search.value || part.value !== null || !!status.value || pendingOnly.value,
)

const emptyText = computed(() =>
  hasFilter.value
    ? '没有符合条件的 —— 换个筛选条件，或者清空筛选'
    : '还没列过任何一条 —— 点右上角「新增一位」开始记：这个部位需要什么、找到了没有',
)

/**
 * ⚠️ 顺序要紧：**先筛再排**。这里不排序（后端给的序是「部位自定义顺序 → 最近录入」），
 *    但筛选条件里那条「只看没搞定的」必须与后端的判据**同源** ——
 *    `find_status !== 'settled'`，一个字都不差。
 */
const rows = computed<BodyNeed[]>(() => {
  const text = search.value.trim().toLowerCase()
  return props.needs.filter((item) => {
    if (text && !item.name.toLowerCase().includes(text)) return false
    if (part.value !== null && item.part_id !== part.value) return false
    if (status.value && item.find_status !== status.value) return false
    if (pendingOnly.value && item.find_status === 'settled') return false
    return true
  })
})

const countLabel = computed(() => {
  const total = props.needs.length
  const shown = rows.value.length
  return shown === total ? `共 ${total} 件` : `筛出 ${shown} / 共 ${total} 件`
})

// ─── 行内改（不做「乐观更新」：成功后以服务端返回为准，失败就提示并重拉） ───

async function onStatusChange(row: BodyNeed, value: string) {
  if (!value || value === row.find_status) return
  try {
    await store.patchNeed(row.id, { find_status: value as BodyNeed['find_status'] })
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '改进度失败'))
    // 失败后把列表拉回服务端的真值 —— 否则界面停在用户刚选的那个值上，
    // 而库里还是旧的，看起来像「改成功了但刷新又变回去」。
    await store.refreshAll()
  }
}

async function onSatisfactionChange(row: BodyNeed, value: string | null) {
  const next = (value || null) as BodySatisfaction | null
  if (next === row.satisfaction) return
  try {
    // 清空 = 把评分撤掉（送 null，不是空串）
    await store.patchNeed(row.id, { satisfaction: next })
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '改满意失败'))
    await store.refreshAll()
  }
}

// ─── 展示辅助：只查表，不判断 ───

function blankShort(row: BodyNeed): string {
  return blankReasonShort(store.meta, row.satisfaction_blank_reason)
}

function blankLabel(row: BodyNeed): string {
  return blankReasonLabel(store.meta, row.satisfaction_blank_reason)
}

/** 点徽标 = 打开档案馆那条去补理由（不是再登记一条） */
function openTreasure(row: BodyNeed) {
  if (!row.treasure_record_id) return
  router.push({ path: '/treasure', query: { focus: String(row.treasure_record_id) } })
}

function clearFilters() {
  search.value = ''
  part.value = null
  status.value = ''
  pendingOnly.value = false
}
</script>

<style scoped>
.body-table__filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.body-table__search {
  width: 160px;
}
.body-table__select {
  width: 124px;
}
.body-table__count {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.body-table__grid {
  width: 100%;
}
.body-table__head {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.body-table__part {
  color: var(--el-text-color-regular);
}
.body-table__name {
  font-weight: 600;
}
.body-table__inline-select {
  width: 96px;
}
.body-table__link {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.body-table__link-kind {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.body-table__link-name {
  color: var(--el-text-color-primary);
}
.body-table__badge {
  cursor: pointer;
}
.body-table__wish {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.body-table__muted {
  color: var(--el-text-color-placeholder);
}
</style>
