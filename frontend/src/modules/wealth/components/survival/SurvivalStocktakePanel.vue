<!--
  实盘盘点记录（v3.59.3；v3.60.3 改为「一套网格 + 行合并」）

  这个面板回答的是**第四个问题**：以前盘过什么、盘出来差在哪。
  没有历史，盘点就只是一次性的动作 —— 没人会记得三个月前少的那 6 件。

  ══════════════════════════════════════════════════════════════
  v3.60.3：为什么从「两张表」改成「一套网格」
  ══════════════════════════════════════════════════════════════

  优化前是主表 + 展开子表：主表 5 列（盘点日 / 物品数 / 结果 / 备注 / 操作），
  展开后塞一张 6 列子表（物品 / 类别 / 账面 / 实盘 / 盈亏 / 备注）。
  实测（2026-09-29，真实数据）：

  | 观测 | 值 | 说明 |
  |---|---|---|
  | 单件记录 | **6 / 8** | 75% 的盘点只盘了一件 |
  | 读全 8 条需要 | **点 8 次展开** | 而 75% 的记录只为看一件物品 |
  | 展开后行数 | 8 + 10 = **18 行** | |
  | 列定义 | **11 处**（两套网格） | 展开后左右两端都不齐 |
  | 明细备注有内容 | **0 / 10** | 整列 140px 宽全是「—」 |

  ⇒ 明细直接成为表行，记录级字段（日期 / 结果 / 备注 / 操作）用
    `span-method` 跨行合并 —— 读数变成 **10 行、0 次点击**。

  ⚠️ 合并的「记录级列」判定走 `utils/survivalStocktake.ts` 的
     `STOCKTAKE_RECORD_PROPS`（按 **prop** 判、不按列序号）——
     这里只做参数适配，不写第二份列清单。

  两条**沿用下来**的展示判据：

  ① **盈亏要带符号**。`+2` 是盘盈、`-6` 是盘亏，看起来必须不一样 ——
     只给绝对值的话，「多了 6 件」和「少了 6 件」长得一模一样，
     而它们要采取的行动完全相反。
  ② **删除要说清代价**。删记录**不会回滚库存**（库存已被那次盘点校准过）。
     不说这句，用户会以为「删掉 = 撤销那次盘点」，而库存一点没变。
     所以这句同时写在下拉菜单项与确认框里。

  ⚠️ 颜色**刻意不套「涨红跌绿」**：那套是价格语义。盘点的差异只说明
     「实物与账面不一致」这个事实，两边都不是单纯的好消息或坏消息。
     所以只按「要不要留意」上色：核对无误给绿，有差异给提醒色。

  ⚠️ 明细**跟随列表一起返回**（与快照列表刻意不带明细相反）：
     盘点的明细就是内容本身 —— 只给「盘了 12 项、3 盈 2 亏」，
     还得再点一次才知道是哪三件，等于把唯一的答案藏起来。

  ⚠️ **不给「总盈亏」**。单位不同**不能相加**（盒 / 片 / 千克 / 罐 / 抽），
     `+6 盒` 与 `+50 抽` 加在一起没有意义。所以汇总行只给**次数与行数**。
-->
<template>
  <div class="survival-stocktake-panel">
    <div class="survival-stocktake-panel__head">
      <div class="survival-stocktake-panel__title-wrap">
        <span class="survival-stocktake-panel__title">实盘盘点记录</span>
        <span class="survival-stocktake-panel__subtitle">
          人手数出来的实物数；提交时库存已按实盘校准，删记录不会把库存改回去
          —— 点「开始盘点」会带你去物品清单挑要数的几件
        </span>
      </div>
      <!--
        ⚠️ 这个按钮**不再直接开弹窗**（v3.60.2）。挑物品只留物品清单一处，
           而弹窗里那份 43 行的全量表已经撤掉 —— 从一个没有预设的地方
           直接开弹窗只会开出一个空壳。所以它改成一次**导航**：
           切到物品清单并给一句提示（见 SurvivalView 的 gotoLedgerToPick）。
      -->
      <el-button size="small" type="primary" @click="emit('stocktake', [])">
        开始盘点
      </el-button>
    </div>

    <template v-if="flatRows.length">
      <!-- 汇总行：只给次数与行数，不给总盈亏（单位不同不相加，见文件头注释） -->
      <div class="survival-stocktake-panel__summary">{{ summaryLine }}</div>

      <el-table
        :data="flatRows"
        size="small"
        row-key="key"
        :span-method="spanOf"
        :row-class-name="rowClassOf"
        class="survival-stocktake-panel__table"
      >
        <el-table-column prop="stocktake_date" label="盘点日" width="170">
          <template #default="{ row }">
            <div class="survival-stocktake-panel__date">{{ row.record.stocktake_date }}</div>
            <!--
              ⚠️ 小字是**录入时刻**（`created_at`），不是「盘点发生的时刻」。
                 `stocktake_date` 是业务日期（可补录）、`created_at` 是系统时刻，
                 两者不同义 —— 所以措辞显式写「录入」，不混着叫。
                 它解决的是实测里 **6/8 条记录落在重复日期上**、无法区分的问题。
            -->
            <div v-if="dateMeta(row.record)" class="survival-stocktake-panel__meta">
              {{ dateMeta(row.record) }}
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="item_name" label="物品" min-width="200">
          <template #default="{ row }">
            <template v-if="row.line">
              <span :class="{ 'survival-stocktake-panel__gone': row.line.item_id === null }">
                {{ row.line.item_name }}
              </span>
              <span class="survival-stocktake-panel__cat">· {{ row.line.category_name }}</span>
              <el-tag v-if="row.line.item_id === null" size="small" type="info" effect="plain">
                物品已删
              </el-tag>
            </template>
            <!-- 没有明细的盘点仍然占一行 —— 静默吞掉它比显示出来糟得多 -->
            <span v-else class="survival-stocktake-panel__none">这次盘点没有明细</span>
          </template>
        </el-table-column>

        <!-- 账面与实盘合成一列：三个格子说一件事（账面 / 实盘 / 盈亏），
             读者得自己做两遍减法。箭头一亮，差异自己就出来了。 -->
        <el-table-column prop="quantity" label="账面 → 实盘" width="155">
          <template #default="{ row }">
            <span v-if="row.line" class="survival-stocktake-panel__qty">
              {{ formatQuantity(row.line.book_quantity, row.line.unit_name) }}
              <span class="survival-stocktake-panel__arrow">→</span>
              {{ formatQuantity(row.line.actual_quantity, row.line.unit_name) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="delta" label="盈亏" width="80">
          <template #default="{ row }">
            <el-tag
              v-if="row.line"
              :type="deltaKindType(row.line.delta_kind)"
              size="small"
              effect="plain"
            >
              {{ formatStocktakeDelta(row.line.delta) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 记录级：跨行合并后它就是「这次盘点」的组标记 -->
        <el-table-column prop="result" label="结果" width="132">
          <template #default="{ row }">
            <el-tag
              v-for="tag in stocktakeResultTags(row.record)"
              :key="tag.label"
              :type="tag.type"
              size="small"
              effect="plain"
              class="survival-stocktake-panel__result-tag"
            >
              {{ tag.label }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 记录级：空就留白，不留「—」（备注的「空」只有一种含义） -->
        <el-table-column prop="note" label="备注" min-width="150">
          <template #default="{ row }">
            {{ formatNote(maskFreeText(row.record.note)) }}
          </template>
        </el-table-column>

        <!-- 行备注：实测 0/10 有内容 ⇒ 整表都没有时这一列整个不渲染 -->
        <el-table-column v-if="hasLineNotes" prop="line_note" label="行备注" min-width="130">
          <template #default="{ row }">
            {{ row.line ? formatNote(maskFreeText(row.line.note)) : '' }}
          </template>
        </el-table-column>

        <!--
          ⚠️ 删除**不再是常显的红字**（v3.60.3）。实测 8 条记录至今一次都没删过，
             而红色是界面里最强的视觉权重 —— 最强权重不该给最不该顺手点的动作。
             收进「⋯」后常态只剩一个灰点，代价（库存不回滚）还能写在菜单里。
        -->
        <el-table-column prop="ops" label="操作" width="56" align="center">
          <template #default="{ row }">
            <el-dropdown trigger="click" @command="onRecordCommand">
              <el-button link size="small" class="survival-stocktake-panel__more">
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="row.record.id">
                    删除这次盘点（库存不回滚）
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <el-empty
      v-else
      description="还没有实盘盘点记录 —— 点「开始盘点」挑几件数一数，盘盈盘亏都会留档"
      :image-size="60"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MoreFilled } from '@element-plus/icons-vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import {
  deltaKindType,
  formatClock,
  formatNote,
  formatQuantity,
  formatStocktakeDelta,
  stocktakeResultTags,
} from '../../utils/survivalFormat'
import {
  flattenStocktakeRows,
  recordSpan,
  type StocktakeFlatRow,
} from '../../utils/survivalStocktake'
import type { SurvivalStocktake } from '../../types/survivalTypes'

const emit = defineEmits<{
  stocktake: [itemIds: number[]]
}>()

const store = useSurvivalStore()
const { maskFreeText } = usePrivacyMask()

/** 表行 = 明细行（拍平在 utils，本组件不做行构造） */
const flatRows = computed(() => flattenStocktakeRows(store.stocktakes))

/**
 * 汇总行。
 *
 * 🔴 **不给「总盈亏」**：单位不同不能相加（盒 / 片 / 千克 / 罐 / 抽），
 *    `+6 盒牛奶` 与 `+50 抽洗脸巾` 加起来没有意义 —— 那正是本项目反复防的
 *    那类「看着合理的错值」。所以只给**次数与行数**。
 */
const summaryLine = computed(() => {
  const records = store.stocktakes
  if (!records.length) return ''
  const parts = [`共 ${records.length} 次盘点`, `${flatRows.value.length} 行明细`]
  const surplus = records.reduce((sum, r) => sum + r.surplus_count, 0)
  const deficit = records.reduce((sum, r) => sum + r.deficit_count, 0)
  if (surplus) parts.push(`盘盈 ${surplus} 行`)
  if (deficit) parts.push(`盘亏 ${deficit} 行`)
  return parts.join(' · ')
})

/** 整表都没有行备注时，那一列整个不渲染（实测 0/10 条有内容） */
const hasLineNotes = computed(() =>
  store.stocktakes.some((record) => (record.lines ?? []).some((line) => Boolean(line.note))),
)

/**
 * 日期格第二行：录入时刻，以及**仅在多件时**才说的件数。
 * 单件写「1 件」是噪音 —— 实测 6/8 条记录都是单件。
 */
function dateMeta(record: SurvivalStocktake): string {
  const parts: string[] = []
  const clock = formatClock(record.created_at)
  if (clock) parts.push(`${clock} 录入`)
  if (record.line_count > 1) parts.push(`${record.line_count} 件`)
  return parts.join(' · ')
}

/** el-table 的 span-method —— 判定逻辑在 utils（单一实现），这里只做参数适配 */
function spanOf(payload: { row: StocktakeFlatRow; column: { property?: string } }) {
  return recordSpan(payload.row, payload.column.property)
}

/** 组与组之间画一条分隔线，让「一次盘点」的边界看得见 */
function rowClassOf(payload: { row: StocktakeFlatRow }): string {
  return payload.row.isGroupFirst ? 'is-group-start' : ''
}

async function onRecordCommand(command: string | number | object) {
  const record = store.stocktakes.find((item) => item.id === Number(command))
  if (record) await remove(record)
}

async function remove(row: SurvivalStocktake) {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${row.stocktake_date} 这次盘点（${row.line_count} 件）？`
      + '删掉的只是这次核对的凭据 —— 当时按实盘校准过的库存不会被改回去。'
      + '要改数量请去「物品清单」里编辑物品。',
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeStocktake(row.id)
    ElMessage.success('已删除这次盘点记录（库存未变）')
  } catch {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.survival-stocktake-panel {
  margin-top: 16px;
  padding: 12px 14px 4px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
}
.survival-stocktake-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.survival-stocktake-panel__title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.survival-stocktake-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.survival-stocktake-panel__subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-stocktake-panel__summary {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-stocktake-panel__table {
  width: 100%;
}
/* 行高比默认略紧 —— 目标是让全部记录一屏读完，不必靠滚动找那条 */
.survival-stocktake-panel__table :deep(.el-table__cell) {
  padding: 6px 0;
}
/* 组与组的分隔线：合并单元格之后，不画线就看不出「哪几行是同一次盘点」 */
.survival-stocktake-panel__table :deep(.is-group-start > td) {
  border-top: 2px solid var(--el-border-color-lighter);
}
.survival-stocktake-panel__date {
  color: var(--el-text-color-primary);
}
.survival-stocktake-panel__meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-stocktake-panel__cat {
  margin-left: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-stocktake-panel__gone {
  text-decoration: line-through;
  color: var(--el-text-color-secondary);
}
.survival-stocktake-panel__none {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.survival-stocktake-panel__qty {
  white-space: nowrap;
}
.survival-stocktake-panel__arrow {
  margin: 0 4px;
  color: var(--el-text-color-placeholder);
}
.survival-stocktake-panel__result-tag {
  margin-right: 4px;
}
.survival-stocktake-panel__more {
  color: var(--el-text-color-secondary);
}
</style>
