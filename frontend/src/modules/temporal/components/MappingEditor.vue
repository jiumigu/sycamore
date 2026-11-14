<template>
  <div class="mapping-editor">
    <div class="page-header">
      <!-- v3.63.7：菜单项已撤，唯一入口是「任务清单」页的 🧩 按钮 ⇒ 返回到那里，
           不要再指向报表页（那是另一个低频页，回去还要再跳一次） -->
      <el-button size="small" @click="$router.push('/temporal/tasks')">
        <el-icon><ArrowLeft /></el-icon> 任务清单
      </el-button>
      <h2>🧩 分类映射编辑器</h2>
      <el-tag type="info" size="small">L1 归因 / L2 类型 / L3 task_name</el-tag>
      <div class="header-right">
        <el-button size="small" text type="primary" :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>
    <p class="page-desc">
      全量 task_name 台账：按时长审阅分类质量，可就地改 L1 归因 / L2 类型 / <b>成长计时</b> / <b>护栏角色</b>（作用于该任务名下的全部记录，不逐条改）。
    </p>

    <!-- 概要：全量口径，不随筛选变化 -->
    <el-card class="panel-card summary-card" shadow="never">
      <div class="summary-strip">
        <div class="sum-item">
          <div class="sum-label">任务名</div>
          <div class="sum-value">{{ summary.total }}<small>个</small></div>
        </div>
        <div class="sum-item">
          <div class="sum-label">已归类</div>
          <div class="sum-value">{{ summary.classified }}<small>个</small></div>
        </div>
        <div class="sum-item" :class="{ 'is-ok': !summary.unclassified }">
          <div class="sum-label">未归类</div>
          <div class="sum-value">{{ summary.unclassified }}<small>个</small></div>
          <div class="sum-note">{{ summary.unclassified ? '待指定 L2 类型' : '已全部归类 🎉' }}</div>
        </div>
        <div class="sum-item">
          <div class="sum-label">台账总时长</div>
          <div class="sum-value">{{ summary.total_hours.toFixed(1) }}<small>h</small></div>
          <div class="sum-note" :class="{ muted: !summary.unclassified_hours }">
            含未归类 {{ summary.unclassified_hours.toFixed(1) }}h
          </div>
        </div>
        <div class="sum-item">
          <div class="sum-label">计入成长计时</div>
          <div class="sum-value">{{ summary.growth_count }}<small>个</small></div>
          <div class="sum-note">累计 {{ summary.growth_hours.toFixed(1) }}h</div>
        </div>
        <!-- 「流失」那条线不看这一列（按 L1 归因），所以这里只数角色，不是「三条线」 -->
        <div class="sum-item" :class="{ 'is-ok': summary.role_count > 0 }">
          <div class="sum-label">护栏角色</div>
          <div class="sum-value">{{ summary.role_count }}<small>个</small></div>
          <div class="sum-note">{{ summary.role_count ? '已标角色' : '睡眠/午睡还没标' }}</div>
        </div>
      </div>

      <div class="attr-chips">
        <span class="chips-label">L1 归因小计</span>
        <span
          v-for="a in ATTRIBUTION_OPTIONS"
          :key="a"
          class="chip"
          :class="{ active: filter.attribution === a, dim: !!filter.attribution && filter.attribution !== a }"
          @click="toggleAttrFilter(a)"
        >
          <i class="dot" :style="{ background: attrColor(a) }" />
          <span class="chip-name">{{ a }}</span>
          <b class="chip-hours">{{ (summary.by_attribution[a] || 0).toFixed(1) }}h</b>
          <em class="chip-pct">{{ attrPct(a) }}%</em>
        </span>
        <span
          v-if="summary.unclassified"
          class="chip chip--unclassified"
          :class="{ active: filter.unclassifiedOnly }"
          @click="toggleUnclassifiedFilter"
        >
          <i class="dot" style="background: #CBD5E1" />
          <span class="chip-name">未归类</span>
          <b class="chip-hours">{{ summary.unclassified_hours.toFixed(1) }}h</b>
          <em class="chip-pct">{{ attrPct('__unclassified__') }}%</em>
        </span>
        <!-- 🔴 与「未归类」并列的第二个待办：L2 配了、L1 没配。
             从前只有 effective_attribution，这堆任务被兜底值伪装成已配置，
             页面上没有任何地方能数出「有几条其实没配」。 -->
        <span
          v-if="summary.unset_attr_count"
          class="chip chip--unset-attr"
          :class="{ active: filter.unsetAttrOnly }"
          @click="toggleUnsetAttrFilter"
        >
          <i class="dot" style="background: #F59E0B" />
          <span class="chip-name">未配归因</span>
          <b class="chip-hours">{{ summary.unset_attr_hours.toFixed(1) }}h</b>
          <em class="chip-pct">{{ summary.unset_attr_count }}个</em>
        </span>
      </div>
    </el-card>

    <el-alert
      v-if="summary.unclassified"
      type="warning" :closable="false" show-icon class="hint-alert"
      title="未归类任务不参与记录完整度计算"
    >
      请为其指定 <b>L2 活动类型</b>；若带价值归因，可一并指定 <b>L1 归因</b>。
    </el-alert>

    <el-alert
      v-if="summary.unset_attr_count"
      type="warning" :closable="false" show-icon class="hint-alert"
      :title="`${summary.unset_attr_count} 个任务名没配 L1 归因，${summary.unset_attr_hours.toFixed(1)}h 按兜底「成长」计入`"
    >
      L2 类型回答的是「这是什么活动」，L1 归因回答的是「它对你意味着什么」—— 后者只能你自己定。
      下拉框空着的那几行就是没配的，选一下即存。
    </el-alert>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="filter.search" placeholder="搜索任务名" clearable size="small" style="width:180px"
        @keyup.enter="load" @clear="load"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="filter.activityType" placeholder="L2 活动类型" clearable size="small" style="width:150px" @change="load">
        <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
      </el-select>
      <el-select v-model="filter.attribution" placeholder="L1 归因" clearable size="small" style="width:120px" @change="load">
        <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="a" :value="a" />
      </el-select>
      <el-checkbox v-model="filter.unclassifiedOnly" size="small" @change="load">仅未归类</el-checkbox>
      <el-checkbox v-model="filter.growthOnly" size="small" @change="load">仅计入成长计时</el-checkbox>
      <el-checkbox v-model="filter.roleOnly" size="small" @change="load">仅标了护栏角色</el-checkbox>
      <el-button size="small" @click="load">查询</el-button>
      <el-button size="small" @click="resetFilter">重置</el-button>
      <span class="filter-count">共 {{ items.length }} / {{ summary.total }} 个任务名</span>
    </div>

    <!-- 批量操作条 -->
    <div class="bulk-bar" v-if="selectedNames.length">
      <span>已选 {{ selectedNames.length }} 个任务名</span>
      <el-button size="small" type="primary" @click="openBulk">批量改 L2 / 归因 / 成长计时</el-button>
      <el-button size="small" @click="clearSelection">取消选择</el-button>
      <span class="bulk-hint">按 task_name 生效：该任务名下的全部记录一次性归类</span>
    </div>

    <!-- 幽灵行：有字典、没记录。多半是登记时名字没写完（「冥想」vs「心灵冥想」），
         留着会让同一个活动在报表里分成两行。这里只提示，删/并都由右边那一列手动做。 -->
    <el-alert
      v-if="ghostNames.length"
      type="info" :closable="false" show-icon class="hint-alert"
      :title="`${ghostNames.length} 个任务名从没记过时间：${ghostNames.slice(0, 6).join('、')}${ghostNames.length > 6 ? ' 等' : ''}`"
    >
      通常是登记时没写完的名字（比如「冥想」和「心灵冥想」）。可以<b>删除</b>，
      也可以<b>改名/合并</b>到同义的那个名字上 —— 合并后同一个活动只占一行。
    </el-alert>

    <el-card class="panel-card table-card" shadow="never">
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="items"
        stripe size="small" max-height="560" row-key="task_name"
        :default-sort="defaultSort"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="40" reserve-selection />
        <el-table-column label="任务名（L3）" prop="task_name" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'is-unclassified': row.is_unclassified }">{{ row.task_name }}</span>
          </template>
        </el-table-column>

        <el-table-column label="L1 归因" width="150">
          <template #default="{ row }">
            <!-- 🔴 绑 `default_attribution`（表里真存的值），**不是** `effective_attribution`。
                 绑后者的后果：没配的行被兜底值填满，看起来跟真配的一模一样 ——
                 用户从账本「8.99h 没设默认归因，去归好」点进来，看到「成长」已经选好，
                 只能得出「明明都配好了」的结论，然后无处可改（v3.64.28）。 -->
            <el-select
              :key="`attr-${row.task_name}-${rev}`"
              :model-value="row.default_attribution || ''"
              :placeholder="row.is_attr_unset ? `未配 · 现按${row.effective_attribution}` : '选一个'"
              :class="{ 'is-attr-unset': row.is_attr_unset }"
              size="small" style="width:100%"
              :disabled="savingRow === row.task_name"
              @click.stop @change="onAttrChange(row, $event)"
            >
              <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="a" :value="a" />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column label="L2 类型" width="136">
          <template #default="{ row }">
            <el-select
              :model-value="row.activity_type"
              size="small" style="width:100%"
              :disabled="savingRow === row.task_name"
              @click.stop @change="onTypeChange(row, $event)"
            >
              <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column width="96" align="center">
          <template #header>
            <span class="growth-head">
              成长计时
              <el-tooltip placement="top" :content="GROWTH_TIP">
                <el-icon class="growth-help"><QuestionFilled /></el-icon>
              </el-tooltip>
            </span>
          </template>
          <template #default="{ row }">
            <el-switch
              :key="`growth-${row.task_name}-${rev}`"
              :model-value="row.counts_growth"
              size="small"
              :loading="savingRow === row.task_name"
              :disabled="savingRow === row.task_name"
              @click.stop
              @change="(v: any) => onGrowthChange(row, !!v)"
            />
          </template>
        </el-table-column>

        <!-- 护栏角色（v3.64.13）：只有睡眠 / 午睡靠这一列；「流失」按 L1 归因，不在此列。
             🔴 角色由标记决定、**不看任务名** —— 改名不会让护栏静默失效。 -->
        <el-table-column width="118" align="center">
          <template #header>
            <span class="growth-head">
              护栏角色
              <el-tooltip placement="top" :content="ROLE_TIP">
                <el-icon class="growth-help"><QuestionFilled /></el-icon>
              </el-tooltip>
            </span>
          </template>
          <template #default="{ row }">
            <el-select
              :key="`role-${row.task_name}-${rev}`"
              :model-value="row.daily_role"
              size="small"
              style="width:102px"
              :disabled="savingRow === row.task_name"
              @click.stop
              @change="(v: DailyRole) => onRoleChange(row, v)"
            >
              <el-option v-for="o in DAILY_ROLE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column label="累计时长" prop="total_hours" width="126" sortable>
          <template #default="{ row }">
            <div class="hours-cell">
              <span class="hours-num">{{ row.total_hours.toFixed(1) }}h</span>
              <span class="hours-bar"><i :style="barStyle(row)" /></span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="记录次数" prop="record_count" width="86" sortable align="right" />
        <el-table-column label="单次均时" prop="avg_minutes" width="88" sortable align="right">
          <template #default="{ row }">
            <span :title="`${row.avg_minutes} 分钟`">{{ fmtAvg(row.avg_minutes) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近使用" prop="last_used" width="100" sortable>
          <template #default="{ row }">
            <span :class="{ muted: !row.last_used }">{{ row.last_used || '无记录' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="归因来源" width="96">
          <template #default="{ row }">
            <el-tooltip :content="sourceTip(row)" placement="top">
              <el-tag size="small" :style="sourceStyle(row)" effect="plain">
                {{ sourceLabel(row) }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>

        <!-- 改名 / 合并 / 删除（v3.64.55）。
             🔴 三个操作都**只作用在任务名这一层**：改名连记录一起改（否则时长凭空归零），
                删除只在名下 0 条时放行（有量时删了不是删数据，是让那 N 小时从台账消失）。 -->
        <el-table-column label="操作" width="132" fixed="right">
          <template #default="{ row }">
            <span class="row-ops">
              <el-button link type="primary" size="small" @click="openRename(row)">改名/合并</el-button>
              <el-tooltip :disabled="!row.record_count" :content="deleteTip(row)" placement="top">
                <span>
                  <el-button
                    link type="danger" size="small"
                    :disabled="row.record_count > 0"
                    @click="onDelete(row)"
                  >删除</el-button>
                </span>
              </el-tooltip>
            </span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!loading && !items.length"
        :description="emptyText"
        :image-size="70"
      />
    </el-card>

    <!-- 改名 / 合并（v3.64.55）—— 新名已存在就是合并，不用另开一个按钮：
         那个「哪些名字已存在」的列表就在下面的表格里，让用户自己判断是多余的。 -->
    <el-dialog v-model="renameVisible" title="改名 / 合并任务名" width="560px">
      <el-form label-width="86px" size="small">
        <el-form-item label="原任务名">
          <span class="rn-old">{{ renameRow?.task_name }}</span>
          <span class="rn-old-meta">
            {{ renameRow?.record_count }} 条记录 · {{ (renameRow?.total_hours ?? 0).toFixed(1) }}h ·
            最近 {{ renameRow?.last_used || '从未' }}
          </span>
        </el-form-item>
        <el-form-item label="改成">
          <el-autocomplete
            v-model="newName"
            :fetch-suggestions="suggestNames"
            placeholder="输入新名字，或从已有任务名里选一个"
            clearable
            style="width:100%"
            @input="onNameInput"
            @select="() => fetchPreview()"
          >
            <template #default="{ item }">
              <span>{{ item.value }}</span>
              <span class="rn-sug-hint">{{ item.hint }}</span>
            </template>
          </el-autocomplete>
        </el-form-item>
      </el-form>

      <!-- 影响预览由后端算（`dry_run=1`），与真执行同一份判据：
           前端拿台账行自己猜「这个名字有没有人用过」，列表被筛选过就会猜错。 -->
      <div v-if="preview" class="rn-impact">
        <template v-if="preview.merged">
          <div class="rn-line">
            <el-tag size="small" type="warning" effect="plain">合并</el-tag>
            把「{{ preview.task_name }}」并进「{{ preview.new_name }}」
          </div>
          <div v-if="preview.moved_records" class="rn-sub">
            {{ preview.moved_records }} 条记录、{{ fmtH(preview.moved_hours) }} 一起搬过去；
            「{{ preview.task_name }}」这一行会消失。
          </div>
          <div v-else class="rn-sub">
            名下一条记录都没有 —— 这一步实际上就是<b>删掉</b>「{{ preview.task_name }}」这一行。
          </div>
          <div v-if="preview.changed_attrs.length" class="rn-warn">
            属性以「{{ preview.new_name }}」那行为准：<b>{{ preview.changed_attrs.join('、') }}</b>
            会按它的值，原来那份被覆盖。
          </div>
        </template>
        <template v-else>
          <div class="rn-line">
            <el-tag size="small" type="success" effect="plain">改名</el-tag>
            「{{ preview.task_name }}」→「{{ preview.new_name }}」
          </div>
          <div class="rn-sub">
            {{ preview.moved_records }} 条记录、{{ fmtH(preview.moved_hours) }} 一起改名；
            L1 / L2 / 成长计时 / 护栏角色原样保留。
          </div>
        </template>
      </div>
      <div v-else-if="previewError" class="rn-impact is-error">{{ previewError }}</div>
      <div v-else-if="newName.trim()" class="rn-impact is-muted">算一下影响面…</div>

      <template #footer>
        <el-button size="small" @click="renameVisible = false">取消</el-button>
        <el-button
          size="small" type="primary"
          :loading="savingName" :disabled="!canConfirm"
          @click="confirmRename"
        >{{ preview?.merged ? '合并' : '改名' }}</el-button>
      </template>
    </el-dialog>

    <!-- 批量设置 -->
    <el-dialog v-model="bulkVisible" title="批量设置 L2 类型 / 归因 / 成长计时" width="480px">
      <el-form label-width="110px" size="small">
        <el-form-item label="L2 活动类型">
          <el-select v-model="bulkForm.activity_type" clearable placeholder="不修改" style="width:100%">
            <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="成长计时" :title="GROWTH_TIP">
          <el-select v-model="bulkForm.growth" style="width:100%">
            <el-option label="不修改（保留现状）" :value="ATTR_KEEP" />
            <el-option label="计入成长计时" value="yes" />
            <el-option label="不计入成长计时" value="no" />
          </el-select>
        </el-form-item>
        <el-form-item label="L1 价值归因">
          <el-select v-model="bulkForm.attribution" style="width:100%">
            <el-option label="不修改（保留现状）" :value="ATTR_KEEP" />
            <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="`设为 ${a}`" :value="a" />
          </el-select>
        </el-form-item>
        <div class="bulk-tip">
          三项都选「不修改」就什么都不会变；只改 L2 时归因原样保留。<br>
          影响 {{ selectedNames.length }} 个任务名下的全部记录：
          {{ selectedNames.slice(0, 6).join('、') }}{{ selectedNames.length > 6 ? ' 等' : '' }}
        </div>
      </el-form>
      <template #footer>
        <el-button size="small" @click="bulkVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="applyBulk">应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { apiErrorText } from '@/shared/utils/apiError'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, QuestionFilled, Refresh, Search } from '@element-plus/icons-vue'
import * as temporalApi from '../api/temporalApi'
import { useTemporalStore } from '../stores/temporalStore'
import {
  ACTIVITY_TYPE_OPTIONS, ATTR_SOURCE_MAP, ATTRIBUTION_COLOR_MAP, ATTRIBUTION_OPTIONS,
  DAILY_ROLE_OPTIONS,
} from '../types/temporalTypes'
import type {
  AttributionSource, DailyRole, MetaLedgerItem, MetaLedgerSummary, TaskRenameResult,
} from '../types/temporalTypes'

/** 批量弹窗的「不修改」哨兵值（不落库，仅前端语义） */
const ATTR_KEEP = '__keep__'

/**
 * 「成长计时」列的口径说明。
 *
 * 🔴 文案要说清「唯一依据」：此前是隐式的「L2 = 深度工作」自动判断，
 *    界面上根本看不到 —— 用户要么不知道它怎么算的，要么只能靠改 L2 间接控制。
 */
const GROWTH_TIP = '勾上后，该任务名下的时长计入「每周状态 → 成长小时数」。'
  + '这是唯一依据：改 L2 类型不会再顺带改它。'
  + '（v3.64.11 之前按「L2 = 深度工作」自动判断，所以老任务名已按当时的值预置好。）'

/**
 * 「日常护栏」列的口径说明。
 *
 * 🔴 说清三件事，否则用户会以为「标了就等于当天会显示数字」：
 *    ① 标了哪个角色就进哪一条线（夜间睡眠 / 午睡）；
 *    ② 夜间睡眠按「醒来那一刻」归到哪一天，午睡按开始时刻；
 *    ③ 阈值不在这里、也不跟着下发 —— 改阈值是改后端常量，不是改这一列。
 * 🔴 这里**不写任何阈值数字**：写了就是第二份副本（原来那句「≤2h」已经过期了，
 *    恰好证明写在两处必然漂），阈值只认 `constants.DAILY_GUARD_LINES`。
 */
const ROLE_TIP = '标了角色，仪表盘「今天的三条线」才会统计这个任务名。'
  + '夜间睡眠按「醒来那一刻」归属日期（23:40 睡 8h 算次日）；午睡按开始时刻。'
  + '「流失」不用标 —— 它直接读 L1 归因（玩游戏 / 刷短视频 / 看小说 都归流失）。'
  + '阈值在后端常量里，这一列只管「进哪条线」。'

const store = useTemporalStore()

const items = ref<MetaLedgerItem[]>([])
const loading = ref(false)
const saving = ref(false)
const savingRow = ref<string | null>(null)
/**
 * 行内下拉的「强制重建」计数器。
 *
 * 归因下拉是**受控**写法（`:model-value` 而非 `v-model`）：换成同一个值、或请求失败时，
 * 数据没变 → prop 值没变 → el-select 仍显示用户刚点的那个值，看不出没生效。
 * 递增本值可让 key 变化、重建组件，显示回到行数据的真实归因。
 */
const rev = ref(0)
const route = useRoute()
const tableRef = ref<any>(null)
const selectedNames = ref<string[]>([])

const filter = reactive<{
  search: string; activityType: string; attribution: string;
  unclassifiedOnly: boolean; growthOnly: boolean; roleOnly: boolean
  unsetAttrOnly: boolean
}>({
  search: '', activityType: '', attribution: '', unclassifiedOnly: false, growthOnly: false, roleOnly: false,
  unsetAttrOnly: false,
})

/** 有没有在用筛选（决定这一次返回能不能当「全量快照」用） */
const hasAnyFilter = computed(() => !!(
  filter.search.trim() || filter.activityType || filter.attribution
  || filter.unclassifiedOnly || filter.growthOnly || filter.roleOnly || filter.unsetAttrOnly
))

const EMPTY_SUMMARY: MetaLedgerSummary = {
  total: 0, classified: 0, unclassified: 0, total_hours: 0, unclassified_hours: 0,
  growth_count: 0, growth_hours: 0, role_count: 0,
  unset_attr_count: 0, unset_attr_hours: 0,
  // 键集**从单一真源派生**，不再手写 —— 曾硬编码五个词，加「体验」时会静默漏一格
  // （渲染时靠 `|| 0` 兜底，看不出来）。v3.60.36 改为派生。
  by_attribution: Object.fromEntries(ATTRIBUTION_OPTIONS.map((a) => [a, 0] as [string, number])),
}
const summary = ref<MetaLedgerSummary>({ ...EMPTY_SUMMARY })

const bulkVisible = ref(false)
const bulkForm = reactive<{ activity_type: string; attribution: string; growth: string }>({
  activity_type: '', attribution: ATTR_KEEP, growth: ATTR_KEEP,
})

// ─── 改名 / 合并 / 删除（v3.64.55）───

/**
 * 无筛选时的全量台账快照。
 *
 * 用途只有两个：① 改名弹窗的候选名；② 「幽灵行」提示（有字典、没记录的名字）。
 * 不参与任何统计口径 —— 页面上的数字一律来自 `items` / `summary`。
 */
const allRows = ref<MetaLedgerItem[]>([])
const renameVisible = ref(false)
const renameRow = ref<MetaLedgerItem | null>(null)
const newName = ref('')
const preview = ref<TaskRenameResult | null>(null)
const previewError = ref('')
const savingName = ref(false)
let previewTimer: ReturnType<typeof setTimeout> | undefined

const ghostNames = computed(() =>
  allRows.value.filter(r => !r.record_count).map(r => r.task_name))

const canConfirm = computed(() => {
  const name = newName.value.trim()
  const old = renameRow.value?.task_name
  return !!name && name !== old && !previewError.value && preview.value !== null && !savingName.value
})

function deleteTip(row: MetaLedgerItem) {
  return `名下还有 ${row.record_count} 条记录（${row.total_hours.toFixed(1)}h），不能直接删 —— `
    + '删掉不会删记录，只会让它从台账消失、按兜底归因计入。要并到别处请用「改名/合并」。'
}

function openRename(row: MetaLedgerItem) {
  renameRow.value = row
  newName.value = ''
  preview.value = null
  previewError.value = ''
  renameVisible.value = true
}

/** 候选名：全部已有任务名（排掉自己），后面带上用量 —— 用户才好判断「并到哪个」 */
function suggestNames(q: string, cb: (items: { value: string; hint: string }[]) => void) {
  const kw = (q || '').trim().toLowerCase()
  const old = renameRow.value?.task_name
  cb(
    allRows.value
      .filter(r => r.task_name !== old && (!kw || r.task_name.toLowerCase().includes(kw)))
      .slice(0, 20)
      .map(r => ({ value: r.task_name, hint: `${r.record_count} 条 · ${r.total_hours.toFixed(1)}h` })),
  )
}

/** 输入停顿 300ms 再问后端 —— 每敲一个字发一次请求既慢又会被后到的旧响应覆盖 */
function onNameInput() {
  preview.value = null
  previewError.value = ''
  if (previewTimer) clearTimeout(previewTimer)
  previewTimer = setTimeout(() => { void fetchPreview() }, 300)
}

async function fetchPreview() {
  const row = renameRow.value
  const name = newName.value.trim()
  if (!row || !name || name === row.task_name) return
  try {
    const res = await temporalApi.renameTaskName({ task_name: row.task_name, new_name: name, dry_run: 1 })
    // 名字在请求期间又被改了 ⇒ 这份预览已经过期，丢掉（否则会拿旧结论去确认新名字）
    if (newName.value.trim() !== name) return
    preview.value = res.data
    previewError.value = ''
  } catch (err) {
    if (newName.value.trim() !== name) return
    preview.value = null
    previewError.value = apiErrorText(err, '算不出影响面')
  }
}

async function confirmRename() {
  const row = renameRow.value
  const name = newName.value.trim()
  if (!row || !name) return
  savingName.value = true
  try {
    const res = await temporalApi.renameTaskName({ task_name: row.task_name, new_name: name })
    const d = res.data
    const moved = d.moved_records
      ? `${d.moved_records} 条记录、${fmtH(d.moved_hours)}`
      : '它名下本来就没有记录'
    ElMessage.success(d.merged
      ? `已把「${row.task_name}」并入「${d.new_name}」：${moved}`
      : `已把「${row.task_name}」改名为「${d.new_name}」：${moved}`)
    renameVisible.value = false
    // 行 key 就是任务名 ⇒ 改名后旧选中项已经不存在，必须清掉再刷
    clearSelection()
    await load()
  } catch (err) {
    ElMessage.error(apiErrorText(err, '改名失败'))
  } finally { savingName.value = false }
}

async function onDelete(row: MetaLedgerItem) {
  try {
    await ElMessageBox.confirm(
      `删掉「${row.task_name}」这一行？它名下没有记录，删了只是从台账消失，不会丢任何时长。`,
      '删除任务名',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch { return }   // 点了取消
  try {
    await temporalApi.deleteTaskName({ task_name: row.task_name })
    ElMessage.success(`已删除「${row.task_name}」`)
    clearSelection()
    await load()
  } catch (err) {
    ElMessage.error(apiErrorText(err, '删除失败'))
  }
}

const maxHours = computed(() => Math.max(...items.value.map(i => i.total_hours), 1))

const emptyText = computed(() => {
  if (filter.unclassifiedOnly) return '全部已归类 🎉 新任务名会在 CSV 导入后落到这里'
  if (filter.growthOnly) return '还没有任务名计入成长计时 —— 打开那一列的开关就会算进「成长小时数」'
  if (filter.roleOnly) return '还没有任务名标「护栏角色」—— 标了才会进仪表盘「今天的三条线」的睡眠 / 午睡'
  if (filter.search || filter.activityType || filter.attribution) return '没有匹配的任务名'
  return '暂无任务名'
})

const defaultSort = { prop: 'total_hours', order: 'descending' as const }

function attrColor(name: string) { return ATTRIBUTION_COLOR_MAP[name] || '#94A3B8' }

function attrPct(key: string) {
  const total = summary.value.total_hours
  if (!total) return '0.0'
  const v = key === '__unclassified__' ? summary.value.unclassified_hours : (summary.value.by_attribution[key] || 0)
  return ((v / total) * 100).toFixed(1)
}

function fmtAvg(minutes: number) {
  if (!minutes) return '—'
  return minutes >= 60 ? `${(minutes / 60).toFixed(1)}h` : `${Math.round(minutes)}min`
}

/** 小时数一律 1 位小数 —— 与「累计时长」列同一个精度，免得同屏出现 103.1h / 103.14h */
function fmtH(hours: number) {
  return `${(hours || 0).toFixed(1)}h`
}

function barStyle(row: MetaLedgerItem) {
  return { width: `${Math.max((row.total_hours / maxHours.value) * 100, 2)}%`, background: attrColor(row.effective_attribution || '') }
}

function sourceLabel(row: MetaLedgerItem) {
  const s = row.attribution_source as AttributionSource | null
  if (!s) return '—'
  return ATTR_SOURCE_MAP[s].label
}

function sourceTip(row: MetaLedgerItem) {
  const s = row.attribution_source as AttributionSource | null
  if (!s) return '无归因信息'
  return `${ATTR_SOURCE_MAP[s].tip} 当前生效：${row.effective_attribution}`
}

function sourceStyle(row: MetaLedgerItem) {
  const s = row.attribution_source as AttributionSource | null
  const c = s ? ATTR_SOURCE_MAP[s].color : '#CBD5E1'
  return { color: c, borderColor: `${c}55`, background: `${c}14` }
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {}
    if (filter.search.trim()) params.search = filter.search.trim()
    if (filter.activityType) params.activity_type = filter.activityType
    if (filter.attribution) params.attribution = filter.attribution
    if (filter.unclassifiedOnly) params.unclassified_only = '1'
    if (filter.growthOnly) params.growth_only = '1'
    if (filter.roleOnly) params.role_only = '1'
    if (filter.unsetAttrOnly) params.unset_attr_only = '1'
    const res = await temporalApi.getMetaLedger(params)
    items.value = res.data.items || []
    summary.value = res.data.summary || { ...EMPTY_SUMMARY }
    // 无筛选的那一次顺手留一份全量快照：改名候选名 / 幽灵行提示要用全量，
    // 但**不另发请求** —— 免得两份「全库」各自取一次、前后不一致。
    if (!hasAnyFilter.value) allRows.value = items.value
  } catch { items.value = [] } finally { loading.value = false }
}

function resetFilter() {
  filter.search = ''; filter.activityType = ''; filter.attribution = ''
  filter.unclassifiedOnly = false; filter.growthOnly = false; filter.roleOnly = false
  filter.unsetAttrOnly = false
  load()
}

/** 三个 chip 是互斥的视角（某个归因 / 未归类 / 未配归因）。
 *  从前只清 `attribution` 一项，于是「未归类 + 未配归因」能同时为真 ⇒ 组合出空列表，
 *  看着像「没有这类任务」。开一个就清另外两个。 */
function clearChipFilters() {
  filter.attribution = ''
  filter.unclassifiedOnly = false
  filter.unsetAttrOnly = false
}

function toggleAttrFilter(a: string) {
  const next = filter.attribution === a ? '' : a
  clearChipFilters()
  filter.attribution = next
  load()
}

function toggleUnclassifiedFilter() {
  const next = !filter.unclassifiedOnly
  clearChipFilters()
  filter.unclassifiedOnly = next
  load()
}

function toggleUnsetAttrFilter() {
  const next = !filter.unsetAttrOnly
  clearChipFilters()
  filter.unsetAttrOnly = next
  load()
}

function onSelectionChange(rows: MetaLedgerItem[]) {
  selectedNames.value = rows.map(r => r.task_name)
}

function clearSelection() {
  selectedNames.value = []
  tableRef.value?.clearSelection()
}

/** 批量/单行统一的落库入口：keep_default 保留原归因
 *
 * `activityType` 允许为空 —— 那表示「这次只改成长计时」，后端不新建行、只翻开关。
 */
async function setMeta(taskNames: string[], activityType: string, attr: string, growth?: boolean) {
  const payload: Record<string, unknown> = { task_names: taskNames }
  if (activityType) payload.activity_type = activityType
  if (attr === ATTR_KEEP) {
    payload.keep_default = true
  } else {
    payload.attribution = attr
  }
  // 🔴 只有真的传了才发：`counts_growth` 缺席 = 「别动」，
  //    顺手带上 `false` 会把整批任务的成长计时清零（`null ≠ 0` 的反面同样要命）
  if (growth !== undefined) payload.counts_growth = growth
  return store.batchSetMeta(payload)
}

/** 只翻「成长计时」开关：不带 L2、不带归因，避免任何连带副作用 */
function setGrowth(taskNames: string[], value: boolean) {
  return store.batchSetMeta({ task_names: taskNames, counts_growth: value })
}

async function onGrowthChange(row: MetaLedgerItem, value: boolean) {
  if (value === row.counts_growth) return
  savingRow.value = row.task_name
  try {
    await setGrowth([row.task_name], value)
    ElMessage.success(
      value
        ? `「${row.task_name}」已计入成长计时 —— 每周状态的成长小时数会算上它`
        : `「${row.task_name}」已移出成长计时`,
    )
    await load()
  } catch (err) {
    ElMessage.error(apiErrorText(err, '保存失败'))
    // 开关是**受控**的（`:model-value`）：请求失败时 prop 没变，
    // 但组件内部可能已经翻过去了 ⇒ 重建一次，显示回到数据真实值
    rev.value += 1
    await load()
  } finally { savingRow.value = null }
}

/** 角色值 → 中文名（只用于提示语；下拉选项来自 DAILY_ROLE_OPTIONS） */
const ROLE_LABEL: Record<string, string> = Object.fromEntries(
  DAILY_ROLE_OPTIONS.map((o) => [o.value, o.label]),
)

/** 只改「日常护栏角色」：不带 L2、不带归因，避免任何连带副作用 */
function setRole(taskNames: string[], role: DailyRole) {
  // 🔴 `daily_role: ''` 是**有效值**（退出护栏），必须照发、不能被 `if (role)` 吞掉 ——
  //    否则「改回不参与」会变成一个不发请求的假操作。
  return store.batchSetMeta({ task_names: taskNames, daily_role: role })
}

async function onRoleChange(row: MetaLedgerItem, value: DailyRole) {
  if (value === row.daily_role) return
  savingRow.value = row.task_name
  try {
    await setRole([row.task_name], value)
    ElMessage.success(
      value
        ? `「${row.task_name}」已计入「${ROLE_LABEL[value]}」这条线`
        : `「${row.task_name}」已退出日常护栏`,
    )
    await load()
  } catch (err) {
    ElMessage.error(apiErrorText(err, '保存失败'))
    // 与成长计时开关同理：受控写法的下拉在请求失败时要重建，回到数据真实值
    rev.value += 1
    await load()
  } finally { savingRow.value = null }
}

async function onAttrChange(row: MetaLedgerItem, value: string) {
  if (value === row.effective_attribution && row.attribution_source !== 'fallback') return
  savingRow.value = row.task_name
  try {
    await setMeta([row.task_name], row.activity_type, value)
    ElMessage.success(`已将「${row.task_name}」的 L1 归因设为 ${value}`)
    await load()
  } catch (err) { ElMessage.error(apiErrorText(err, '保存失败')) } finally { savingRow.value = null }
}

async function onTypeChange(row: MetaLedgerItem, value: string) {
  if (value === row.activity_type) return
  savingRow.value = row.task_name
  try {
    // 只改 L2：保留原默认归因，不产生归因副作用
    await setMeta([row.task_name], value, ATTR_KEEP)
    ElMessage.success(`已将「${row.task_name}」的 L2 类型改为 ${value}`)
    await load()
  } catch (err) { ElMessage.error(apiErrorText(err, '保存失败')) } finally { savingRow.value = null }
}

function openBulk() {
  bulkForm.activity_type = ''
  bulkForm.attribution = ATTR_KEEP
  bulkForm.growth = ATTR_KEEP
  bulkVisible.value = true
}

async function applyBulk() {
  if (!selectedNames.value.length) return
  const setGrowthFlag = bulkForm.growth !== ATTR_KEEP
  if (!bulkForm.activity_type && !setGrowthFlag) {
    ElMessage.warning('三项都是「不修改」—— 选一样要改的（L2 类型 / 成长计时 / 归因）')
    return
  }
  saving.value = true
  try {
    const growth = setGrowthFlag ? bulkForm.growth === 'yes' : undefined
    const res = await setMeta([...selectedNames.value], bulkForm.activity_type, bulkForm.attribution, growth)
    // ⚠️ 取数层级：setMeta 返回的是 axios response，后端的 updated 在 res.data 上
    const d = (res as { data?: { updated?: number } })?.data || {}
    let msg = `已更新 ${d.updated ?? 0} 个任务名`
    if (setGrowthFlag) msg += growth ? '，已计入成长计时' : '，已移出成长计时'
    ElMessage.success(msg)
    bulkVisible.value = false
    clearSelection()
    await load()
  } catch (err) { ElMessage.error(apiErrorText(err, '批量失败')) } finally { saving.value = false }
}

// 🔴 支持 `?unset_attr_only=1`：阶段账本的「去归好」带着它跳过来，
//    落地就是那几条没配的行 —— 从「去归好」到「看到该改哪一行」不该再让人自己筛。
onMounted(() => {
  if (route.query.unset_attr_only === '1') filter.unsetAttrOnly = true
  load()
})
</script>

<style scoped lang="scss">
.mapping-editor { padding: 20px; background: #F5F7FA; min-height: 100vh;
  .page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 6px;
    h2 { margin: 0; font-size: 20px; }
    .header-right { margin-left: auto; } }
  .page-desc { margin: 0 0 12px; font-size: 12px; color: #64748B; }
  .hint-alert { margin-bottom: 14px; }

  // 没配归因的下拉：空着 + 琥珀描边。空才是事实，描边让它在一屏几十行里能被找到
  :deep(.el-select.is-attr-unset .el-select__wrapper) {
    background: #FFFBEB;
    box-shadow: 0 0 0 1px #FCD34D inset;
  }

  .panel-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    :deep(.el-card__body) { padding: 0; } }
  .summary-card { margin-bottom: 14px;
    :deep(.el-card__body) { padding: 14px 16px 12px; } }

  .summary-strip { display: flex; gap: 12px; flex-wrap: wrap;
    /* 6 格排一行：基准宽度调窄，避免第 6 格单独折到第二行被拉成一整条 */
    .sum-item { flex: 1 1 118px; min-width: 108px; padding: 8px 12px; border-radius: 8px; background: #F8FAFC;
      .sum-label { font-size: 12px; color: #64748B; }
      .sum-value { font-size: 22px; font-weight: 600; color: #1F2937; line-height: 1.4;
        small { font-size: 12px; font-weight: 400; color: #94A3B8; margin-left: 2px; } }
      .sum-note { font-size: 11px; color: #94A3B8;
        &.muted { color: #CBD5E1; } }
      &.is-ok .sum-note { color: #10B981; } } }

  .attr-chips { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 12px;
    .chips-label { font-size: 12px; color: #64748B; margin-right: 2px; }
    .chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 14px;
      background: #F1F5F9; border: 1px solid transparent; cursor: pointer; font-size: 12px; color: #334155;
      transition: all .15s;
      &:hover { background: #E2E8F0; }
      &.active { background: #EEF2FF; border-color: #6366F1; color: #4338CA; }
      &.dim { opacity: .45; }
      .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
      .chip-hours { font-weight: 600; }
      .chip-pct { color: #94A3B8; font-style: normal; font-size: 11px; }
      // 「未配归因」是一条待办，不是一种中性分布 ⇒ 常驻琥珀底，不靠 hover 才显形
      &.chip--unset-attr { background: #FFFBEB; border-color: #FCD34D; color: #92400E; } } }

  .filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
    .filter-count { font-size: 12px; color: #94A3B8; } }
  .bulk-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; font-size: 13px; color: #4b5563;
    .bulk-hint { font-size: 12px; color: #9CA3AF; } }

  .table-card { :deep(.el-card__body) { padding: 6px 8px 12px; } }
  .growth-head { display: inline-flex; align-items: center; gap: 3px; }
  .growth-help { color: #94A3B8; cursor: help; font-size: 12px;
    &:hover { color: #6366F1; } }
  .hours-cell { display: flex; flex-direction: column; gap: 3px;
    .hours-num { font-size: 13px; }
    .hours-bar { display: block; height: 3px; border-radius: 2px; background: #EEF2F7;
      i { display: block; height: 100%; border-radius: 2px; } } }

  .muted { color: #b8bcc4; }
  .is-unclassified { color: #94A3B8; }
  .bulk-tip { font-size: 12px; color: #94A3B8; padding-left: 110px; line-height: 1.6; }

  // 禁用按钮本身收不到 hover（Chrome 不派发事件）⇒ 让事件落到外面那层 span 上，
  // 否则「为什么不能删」的说明永远弹不出来，只剩一个灰按钮。
  :deep(.el-button.is-disabled) { pointer-events: none; }
  // 两个 link 按钮默认会挤在一起（「改名/合并删除」），给一点间距
  .row-ops { display: inline-flex; align-items: center; gap: 8px; }

  // 改名 / 合并弹窗
  .rn-old { font-weight: 600; color: #1F2937; }
  .rn-old-meta { margin-left: 10px; font-size: 12px; color: #94A3B8; }
  .rn-sug-hint { float: right; margin-left: 12px; font-size: 12px; color: #94A3B8; }
  .rn-impact { border-radius: 8px; background: #F8FAFC; padding: 10px 12px; font-size: 12px;
    color: #334155; line-height: 1.7;
    // 合并会「吃掉」一行 ⇒ 与改名区分开，别让人以为只是换个名字
    &.is-error { background: #FEF2F2; color: #B91C1C; }
    &.is-muted { color: #94A3B8; }
    .rn-line { display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
      font-size: 13px; color: #1F2937; }
    .rn-sub { color: #475569; }
    .rn-warn { margin-top: 6px; padding: 6px 8px; border-radius: 6px;
      background: #FFFBEB; color: #92400E; } }
}
</style>
