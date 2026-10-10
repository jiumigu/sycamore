<!--
  物品编辑弹窗

  字段按类别的消耗模式显隐，**不按类别名判断**：
    配餐类只填「有多少、什么角色、什么时候过期」—— 每天消耗多少由配方决定；
    折旧 / 按需 / 数字类才填「一件还能用多少天」。
  让配餐类也填「单件可用天数」是错的：八宝粥能撑多久取决于一天吃几罐，
  那是配方的事，填在这里会得到两个互相矛盾的口径。

  ⚠️ 「单件可用天数」在配餐类里**刻意不显示也不提交** ——
     显示了就会有人填，填了就会有两份口径。

  ── 类别可选（v3.59.5） ──

  类别是**记账口径的总开关**：它决定下面显隐哪些字段、单位下拉里有哪些单位。
  所以新增时它是第一格、可改，而不是由调用方在打开前就锁死 ——
  从「物品清单」进来时那件东西属于哪一类，用户自己最清楚；
  让他先关掉弹窗、回总览切类别、再点一次新增，是把口径问题变成了操作问题。

  ⚠️ **编辑时类别只读**：物品被配方引用时，改类别会让配方里出现别类的东西 ——
     「配方行的物品必须属于配方类别」这道校验只写在配方一侧，
     从物品这一侧改绕得过去，于是留下一个「看起来改了、配方里悄悄不一致」的入口。
     宁可在这里挡住。

  ── 按天 / 按次（v3.59.3） ──

  很多物品**不是每天都用**：一包 10 片的卫生巾，按「一份能用多少天」根本填不出来，
  因为它取决于多久用一次。所以计量方式二选一：

    按天：一份能用多少天            —— 天天在用的东西（纸巾、大米）
    按次：一份能用多少次 × 多久用一次 —— 间歇在用的东西（卫生巾、电池）

  两条口径**互斥**：切到按次时按天那个值不提交（显式送 null）。
  后端判据是「填了「一份能用几次」就按次算」，所以不送 null 会留下一条
  看不见的旧口径 —— 界面显示按次、算法按天，改起来还找不到地方。

  ⚠️ 这里的「阅读方式」预览（`每 3 天用 1 次`）**只是把那句话拼回来**，
     **不做任何换算** —— 「每周 2 次 = 3.5 天一次」那种折算在后端
     （唯一真源）。前端再算一遍就有了第二份口径，改后端时必然漏改。

  ── 衣物录入参考（v3.59.8） ──

  「一件还能穿多久」**不是常量**：只求遮体保暖可以穿十年，要求体面不起球往往一两年，
  而且两个答案都不算错。于是这一格只能拍脑袋 —— 拍出来差一个数量级也没人会发现
  （数字看着都合理）。所以折旧消耗类下面挂一份参考表。

  ⚠️ 参考表只做**提示**，绝不预填、绝不兜底：
     没填口径就是「算不出来」，让参考值顶上等于给所有衣物套一个统一寿命，
     那正是这次要修的错。只有用户**显式点按钮**才写进表单。
  ⚠️ 表里「可穿次数」与「可用天数」**不互相换算** —— 次数与穿法无关、跨人可比，
     天数隐含了一个穿着频次。各自填各自的那一列，不拿天数反推次数。

  ── 「一份」到底指什么 + 保存前试算（v3.59.11） ──

  起因：洗脸巾「数量 300 抽 + 一份能用几次 300 + 每 1 天用 2 次」，
  页面报 **123.7 年**。算法没错 ——

      天数 = 数量 × 一份能用几次 × (周期天数 ÷ 每周期次数) = 300 × 300 × 0.5 = 45,000 天

  错在**同一个 300 被填了两遍**：一次是「我有 300 抽」，一次是「一份里有 300 抽」。
  而这一格的提示语原来写的是「一包 10 片就填 10」—— 它把「一份」定义成了**包装**，
  用户的「数量」填的却是**内容物**（抽 / 片）。两个口径一混，300 就出现两次。

  ⇒ 所以标签跟着**数量的那个单位**走（`每抽能用几次`）：
    「一份」= 数量的单位所指的那一个，这个绑定没有第二次解释的空间。

  ⚠️ 它之所以骗过了人：**这个表单从来没把数乘出来给人看过**。
     中间量「一份可用 150 天」完全正常，错在最后一跳 —— 乘以 300。
     所以这里挂一条**保存前试算**：填完就显示最终会存进去的那个数。

  🔴 试算**走后端**（`POST /survival/items/preview/`），不在前端自己乘：
     那份公式与 `survival_calc` 迟早会分叉，而分叉是**静默的** ——
     试算说 150 天、保存后写着 123.7 年，两边看起来都像个正常的数。
     同理，试算的校验复用**同一个**表单序列化器，
     免得出现「试算放行、一按保存报 400」——那比没有试算更误导。

  ── 盘点周期 / 补货线 ──

  这两个对所有类别都显示（连配餐类也要盘），它们不影响时长计算，
  只喂给盘点工作表：定周期才会在清单上标「该盘了」，填了补货线才会标「该补货」。
  ⚠️ **留空 = 不催**，不是「催得很急」。别给个默认值 —— 那会让所有物品一起标红。
-->
<template>
  <el-dialog
    v-model="visible"
    :title="itemId ? '编辑物品' : '新增物品'"
    width="620px"
    :close-on-click-modal="false"
  >
    <el-form :model="form" label-width="110px" size="small">
      <!-- 第一格就是类别：它是下面所有字段的总开关，先定它再填别的 -->
      <el-form-item label="类别">
        <el-select
          v-if="!itemId"
          v-model="form.category_id"
          placeholder="选择类别"
          size="small"
          class="survival-item-dialog__half"
          @change="onCategoryChange"
        >
          <el-option
            v-for="option in store.categories"
            :key="option.id"
            :label="option.name"
            :value="option.id"
          />
        </el-select>
        <span v-else class="survival-item-dialog__static">{{ category?.name ?? '—' }}</span>
        <div class="survival-item-dialog__hint">{{ categoryHint }}</div>
      </el-form-item>

      <el-form-item label="物品名称">
        <el-input v-model="form.name" placeholder="八宝粥 / 米粉 / 大衣 / 纸巾" maxlength="200" />
      </el-form-item>

      <el-form-item label="数量">
        <el-input-number v-model="form.quantity" :min="0" :step="1" :precision="2" />
        <el-select
          v-model="form.unit_id"
          placeholder="选择单位"
          size="small"
          class="survival-item-dialog__unit"
        >
          <el-option
            v-for="unit in unitOptions"
            :key="unit.id"
            :label="unit.name"
            :value="unit.id"
          />
          <!-- 就地新增：真正的痛点是「填到这一格才发现少一个单位」，
               那时候跳出弹窗去维护、回来还得重填一遍 -->
          <template #footer>
            <el-button link size="small" type="primary" @click.stop="quickAddVisible = true">
              <el-icon><Plus /></el-icon>新建单位
            </el-button>
          </template>
        </el-select>
      </el-form-item>

      <el-form-item v-if="isMeal" label="饱腹角色">
        <el-select v-model="form.satiety" size="small" class="survival-item-dialog__half">
          <el-option
            v-for="option in satietyOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <span class="survival-item-dialog__suffix">
          零食不参与「能撑多少顿」，会单独统计
        </span>
      </el-form-item>

      <template v-if="!isMeal">
        <el-form-item label="计量方式">
          <el-radio-group v-model="form.measure" size="small">
            <el-radio-button value="day">按天</el-radio-button>
            <el-radio-button value="cycle">按次</el-radio-button>
          </el-radio-group>
          <span class="survival-item-dialog__suffix">{{ measureHint }}</span>
        </el-form-item>

        <el-form-item v-if="form.measure === 'day'" label="一件可用天数">
          <el-input-number
            v-model="form.days_per_unit"
            :min="0.1"
            :step="1"
            :precision="1"
            placeholder="一件还能用多少天"
          />
          <span class="survival-item-dialog__suffix">{{ lifeHint }}</span>
        </el-form-item>

        <template v-else>
          <el-form-item :label="usesLabel">
            <el-input-number
              v-model="form.uses_per_unit"
              :min="0.01"
              :step="1"
              :precision="2"
            />
            <span class="survival-item-dialog__suffix">{{ usesHint }}</span>
          </el-form-item>

          <el-form-item label="使用频次">
            <span class="survival-item-dialog__cycle-text">每</span>
            <el-input-number
              v-model="form.use_cycle_num"
              :min="0.01"
              :step="1"
              :precision="2"
              class="survival-item-dialog__cycle-num"
            />
            <el-select
              v-model="form.use_cycle_unit"
              size="small"
              class="survival-item-dialog__cycle-unit"
            >
              <el-option
                v-for="option in useCycleUnits"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <span class="survival-item-dialog__cycle-text">用</span>
            <el-input-number
              v-model="form.use_times"
              :min="0.01"
              :step="1"
              :precision="2"
              class="survival-item-dialog__cycle-num"
            />
            <span class="survival-item-dialog__cycle-text">次</span>
          </el-form-item>

          <el-form-item label=" ">
            <span class="survival-item-dialog__hint">
              读作：{{ cycleReadOut }}。折算成「一份能用多少天」由系统算 ——
              这里不做换算，改算法时只改一处。
            </span>
          </el-form-item>
        </template>

        <el-form-item v-if="isTimeBased" label="一册耗时">
          <el-input-number
            v-model="form.hours_per_unit"
            :min="0.1"
            :step="1"
            :precision="1"
          />
          <span class="survival-item-dialog__suffix">小时；用来同时给出「还能读多少小时」</span>
        </el-form-item>
      </template>

      <!-- 衣物录入参考（v3.59.8）—— 判据见文件头 -->
      <el-form-item v-if="isDepreciation && wearReference.length" label=" ">
        <div class="survival-item-dialog__wear">
          <div class="survival-item-dialog__wear-head">
            <span class="survival-item-dialog__wear-title">衣物录入参考</span>
            <span class="survival-item-dialog__wear-sub">
              次数与穿法无关、跨人可比；天数隐含了一个穿着频次
            </span>
            <el-button link size="small" type="primary" @click="wearOpen = !wearOpen">
              {{ wearToggleLabel }}
            </el-button>
          </div>

          <div v-if="matchedWear" class="survival-item-dialog__wear-hit">
            <div class="survival-item-dialog__wear-hit-text">
              命中「{{ matchedWear.keyword }}」：
              <template v-if="matchedWear.uses_low !== null">
                约可穿 <b>{{ usesText(matchedWear) }}</b>
              </template>
              <template v-else>
                建议按天填 <b>{{ daysText(matchedWear) }} 天</b>
              </template>
              ，该换了的信号是「{{ matchedWear.signal }}」。
            </div>
            <div class="survival-item-dialog__wear-actions">
              <el-button
                v-if="matchedWear.uses_low !== null"
                link
                size="small"
                type="primary"
                @click="adoptWear('cycle')"
              >
                填按次建议（{{ suggestUses }}）
              </el-button>
              <el-button link size="small" type="primary" @click="adoptWear('day')">
                填按天建议（{{ suggestDays }} 天）
              </el-button>
            </div>
          </div>
          <div v-else class="survival-item-dialog__wear-sub survival-item-dialog__wear-sub--block">
            名称里含下列任一关键词（如 T恤 / 衬衫 / 外套）时会自动给出建议值
          </div>

          <el-table
            v-if="wearOpen"
            :data="orderedWearReference"
            :row-class-name="wearRowClass"
            size="small"
            class="survival-item-dialog__wear-table"
          >
            <el-table-column prop="keyword" label="衣物" width="80" />
            <el-table-column label="可穿次数" width="108">
              <template #default="{ row }">{{ usesText(row) }}</template>
            </el-table-column>
            <el-table-column label="若按天填" width="108">
              <template #default="{ row }">{{ daysText(row) }} 天</template>
            </el-table-column>
            <el-table-column
              prop="signal"
              label="该换了的信号"
              min-width="160"
              show-overflow-tooltip
            />
          </el-table>

          <div class="survival-item-dialog__hint">
            参考值按「能体面出门」的标准给，只求遮体保暖可以更宽松。
            它只是锚点，不是这件物品的参数 —— 你自己的手感优先。
          </div>
        </div>
      </el-form-item>

      <!-- 保存前试算（v3.59.11）—— 判据见文件头：错在最后一跳，就让它先跳一遍。
           ⚠️ 停在这儿而不是塞进页脚：它要跟着「数量 / 计量方式」一起被读到，
              放在备注、状态、盘点周期之下就离输入太远了。 -->
      <el-form-item v-if="!isMeal" label=" ">
        <div class="survival-item-dialog__preview">
          <span class="survival-item-dialog__preview-title">试算</span>
          <template v-if="previewExpected !== null">
            <span class="survival-item-dialog__preview-value">
              预计能撑 {{ formatDays(previewExpected) }}
            </span>
            <span class="survival-item-dialog__preview-sub">{{ previewRangeText }}</span>
          </template>
          <span v-else class="survival-item-dialog__preview-sub">{{ previewNote }}</span>
          <div v-if="previewReadOut" class="survival-item-dialog__preview-read">
            {{ previewReadOut }}
          </div>
        </div>
      </el-form-item>

      <el-form-item v-if="isMeal || isDepreciation" label="等级">
        <el-select v-model="form.grade" size="small" clearable class="survival-item-dialog__half">
          <el-option
            v-for="option in gradeOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item v-if="isTimeBased" label="优先级">
        <el-select v-model="form.priority" size="small" clearable class="survival-item-dialog__half">
          <el-option
            v-for="option in priorityOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="状态">
        <el-select v-model="form.status" size="small" class="survival-item-dialog__half">
          <el-option
            v-for="option in statusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="盘点周期">
        <el-input-number
          v-model="form.stocktake_cycle_days"
          :min="1"
          :step="1"
          :precision="0"
          placeholder="留空 = 不催"
          class="survival-item-dialog__cycle-num"
        />
        <span class="survival-item-dialog__suffix">
          天；留空就不提醒盘点，不会默认催你
        </span>
      </el-form-item>

      <el-form-item label="补货线">
        <el-input-number
          v-model="form.restock_threshold"
          :min="0"
          :step="1"
          :precision="2"
          placeholder="留空 = 不提醒"
          class="survival-item-dialog__cycle-num"
        />
        <span class="survival-item-dialog__suffix">
          {{ form.unit_id ? '与「数量」同一单位；降到这个数（含等于）就标「该补货」' : '先选单位' }}
        </span>
      </el-form-item>

      <el-form-item label="过期日期">
        <el-date-picker
          v-model="form.expire_date"
          type="date"
          size="small"
          value-format="YYYY-MM-DD"
          placeholder="选填；填了就是硬上限"
        />
        <div class="survival-item-dialog__hint">
          保质期是硬上限：库存算出来能撑 200 天，最早那批 10 天后过期，实际就撑 10 天。
        </div>
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="2" maxlength="500" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button size="small" type="primary" :loading="store.saving" @click="submit">保存</el-button>
    </template>

    <!-- 就地新增单位：建完自动选中，本弹窗的输入一个都不丢 -->
    <SurvivalUnitQuickAdd
      v-model:visible="quickAddVisible"
      :category-id="form.category_id"
      :category-name="category?.name ?? ''"
      @created="onUnitCreated"
    />
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import SurvivalUnitQuickAdd from './SurvivalUnitQuickAdd.vue'
import { formatDays, formatScenarioRange, formatSpread, formatUseCycle } from '../../utils/survivalFormat'
// ⚠️ 试算刻意**不走 store**：store 的动作都在管 state（`saving` / `refreshAll`），
//    而试算是只读探询、不产生任何状态。挂进 store 会连 `saving` 一起点亮，
//    于是「正在保存」的转圈会在用户每敲一个数字时出现 —— 那是假的。
import { previewSurvivalItem } from '../../api/survivalApi'
import type {
  SurvivalItemFormData,
  SurvivalItemPreview,
  SurvivalUnit,
  SurvivalWearReference,
} from '../../types/survivalTypes'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  /** 只是**默认值**：新增时预选它，用户可以在弹窗里改。编辑时以物品自己的类别为准 */
  categoryId: number | null
  /** 传 null = 新建 */
  itemId: number | null
}>()

const store = useSurvivalStore()

/**
 * ⚠️ 表单先声明、计算属性后声明。
 *
 * 类别现在是**表单里的一个字段**（`form.category_id`）而不是外部传入的常量，
 * 下面所有「按类别分派」的计算属性都必须读它 —— 读 prop 会让「改了类别但字段没跟着变」
 * 变成一个只在切类别时才出现的鬼影 bug。
 */
const form = reactive({
  category_id: null as number | null,
  name: '',
  quantity: 0,
  unit_id: null as number | null,
  satiety: '',
  grade: '',
  priority: '',
  status: 'stocked',
  /** 'day' 按天 / 'cycle' 按次 —— 两条口径互斥 */
  measure: 'day' as 'day' | 'cycle',
  days_per_unit: null as number | null,
  uses_per_unit: null as number | null,
  use_cycle_num: null as number | null,
  use_cycle_unit: 'day',
  use_times: null as number | null,
  stocktake_cycle_days: null as number | null,
  restock_threshold: null as number | null,
  hours_per_unit: null as number | null,
  expire_date: null as string | null,
  notes: '',
})

const category = computed(() => store.categories.find((c) => c.id === form.category_id) ?? null)
const mode = computed(() => category.value?.consume_mode ?? 'on_demand')
const isMeal = computed(() => mode.value === 'meal')
const isDepreciation = computed(() => mode.value === 'depreciation')
const isTimeBased = computed(() => mode.value === 'time_based')

const unitOptions = computed(() => store.units.filter((u) => u.category_id === form.category_id))

/**
 * 当前选中的单位名 —— 「一份」这个词的落点（v3.59.11）。
 *
 * 🔴 这一格原来只写「一份能用几次」，而唯一的提示语是「一包 10 片就填 10」：
 *    它把「一份」定义成**包装**，可「数量」是拿**内容物**（抽 / 片）填的。
 *    两个口径一混，300 就出现两次，于是 300 抽洗脸巾算成了 123.7 年。
 *    ⇒ 标签跟着数量的单位走，「一份」= 数量的单位所指的那一个。
 */
const unitName = computed(
  () => unitOptions.value.find((u) => u.id === form.unit_id)?.name ?? '',
)

const usesLabel = computed(() => `每${unitName.value || '份'}能用几次`)

const usesHint = computed(() => (
  `按${unitName.value ? `「${unitName.value}」` : '数量的那个单位'}算：一次用一个就填 1；`
  + `数量若按「包 / 瓶」填，才填一整包的次数`
))
const satietyOptions = computed(() => store.meta?.satiety ?? [])
const gradeOptions = computed(() => store.meta?.grades ?? [])
const statusOptions = computed(() => store.meta?.statuses ?? [])
const priorityOptions = computed(() => store.meta?.priorities ?? [])
/** 周期单位（天 / 周 / 月）—— 与后端 constants 同一份，前端不硬编码文案 */
const useCycleUnits = computed(() => store.meta?.use_cycle_units ?? [])
/** 消耗模式的中文名（配餐供餐 / 折旧消耗 / 按需消耗 / 时间消耗）也来自后端 */
const modeLabel = computed(
  () => store.meta?.consume_modes.find((m) => m.value === mode.value)?.label ?? '',
)

const quickAddVisible = ref(false)

/**
 * 衣物可穿次数参考（v3.59.8）—— 只在折旧消耗类下面出现。
 *
 * 🔴 它**不预填任何字段**：没填口径就是「算不出来」，让参考值顶上等于给所有衣物
 *    套一个统一寿命 —— 那正是这次要修的错。只在用户**点按钮**时才写进表单。
 */
const wearReference = computed(() => store.meta?.wear_reference ?? [])
const wearOpen = ref(false)

/** 名称里含关键词就命中（`T恤` 与 `t恤` 都算）；取表中第一条命中的 */
const matchedWear = computed(() => {
  const name = form.name.trim().toLowerCase()
  if (!name) return null
  return wearReference.value.find(
    (row) => name.includes(row.keyword.toLowerCase()),
  ) ?? null
})

/** 命中的那行置顶 —— 表有十来行，不置顶等于让人自己找 */
const orderedWearReference = computed(() => {
  const rows = wearReference.value
  const hit = matchedWear.value
  if (!hit) return rows
  return [hit, ...rows.filter((row) => row !== hit)]
})

const wearToggleLabel = computed(
  () => (wearOpen.value ? '收起' : `看全部 ${wearReference.value.length} 类`),
)

function wearRowClass({ row }: { row: SurvivalWearReference }) {
  return row === matchedWear.value ? 'survival-item-dialog__wear-row--hit' : ''
}

/** 区间取中值；只给下限（「1000 次以上」）时就用下限 */
function mid(low: number, high: number | null) {
  return high === null ? low : Math.round((low + high) / 2)
}

function usesText(row: SurvivalWearReference) {
  if (row.uses_low === null) return '—'
  return row.uses_high === null
    ? `${row.uses_low} 次以上`
    : `${row.uses_low} ~ ${row.uses_high} 次`
}

function daysText(row: SurvivalWearReference) {
  return row.days_low === row.days_high
    ? `${row.days_low}`
    : `${row.days_low} ~ ${row.days_high}`
}

const suggestUses = computed(() => {
  const row = matchedWear.value
  if (!row || row.uses_low === null) return ''
  const times = mid(row.uses_low, row.uses_high)
  return row.wears_per_week ? `${times} 次 · 每周 ${row.wears_per_week} 次` : `${times} 次`
})

const suggestDays = computed(() => {
  const row = matchedWear.value
  return row ? mid(row.days_low, row.days_high) : 0
})

/**
 * 采纳建议值 —— **只有显式点按钮才写**。
 *
 * 两列**不互相换算**：点「按次」填的是次数 + 频次，点「按天」填的是天数，
 * 各自来自表里各自那一列。拿天数反推次数会得到一个没人核对过的假设，
 * 而且它看起来完全合理 —— 正是这个文件要防的那类错。
 */
function adoptWear(kind: 'cycle' | 'day') {
  const row = matchedWear.value
  if (!row) return
  if (kind === 'day') {
    form.measure = 'day'
    form.days_per_unit = mid(row.days_low, row.days_high)
  } else {
    if (row.uses_low === null || row.wears_per_week === null) return
    form.measure = 'cycle'
    form.uses_per_unit = mid(row.uses_low, row.uses_high)
    form.use_cycle_num = 1
    form.use_cycle_unit = 'week'
    form.use_times = row.wears_per_week
  }
  ElMessage.success('已填入建议值，可以按自己的情况改')
}

/** 新单位就地选中 —— 用户是为了这一格才去建它的 */
function onUnitCreated(unit: SurvivalUnit) {
  form.unit_id = unit.id
}

const lifeHint = computed(() => {
  if (isMeal.value) return '每天消耗多少由配方决定，这里只记有多少、什么时候过期'
  if (isDepreciation.value) return '一件大衣还能穿 3 年 → 填 1095'
  if (isTimeBased.value) return '一册书按我的节奏能读几天'
  return '一份能用多少天：一包纸巾用 10 天 → 填 10'
})

const measureHint = computed(() => (
  form.measure === 'cycle'
    ? '不是天天用的东西（卫生巾、电池、滤芯）'
    : '每天都要用的东西（纸巾、大米）'
))

/**
 * 类别这一格的说明 = 后端给的模式名 + 该模式该填什么。
 *
 * ⚠️ 模式名从 `/survival/meta/` 取，不在前端硬编码 ——
 *    换个名字或换个 mode，前端一句都不该改。
 */
const categoryHint = computed(() => {
  const head = modeLabel.value ? `${modeLabel.value}：` : ''
  const body = `${head}${lifeHint.value}`
  if (!props.itemId) return body
  return `${body}。类别建好后不可改 —— 换类别等于换一套账，请另建一件`
})

/** 只是把四个字段拼回一句人话 —— 不做换算，见文件头 */
const cycleReadOut = computed(() => {
  const cycleUnitLabel = useCycleUnits.value
    .find((u) => u.value === form.use_cycle_unit)?.label ?? '天'
  const cycle = formatUseCycle(form.use_cycle_num, cycleUnitLabel, form.use_times)
  // ⚠️ 说的必须是**同一个单位**（数量的那个），否则「一份」又成了一个没人定义过的词
  const per = unitName.value || '份'
  if (!form.uses_per_unit) return `每${per}能用几次还没填`
  if (!cycle) return `每${per}能用 ${form.uses_per_unit} 次`
  return `每${per}能用 ${form.uses_per_unit} 次，${cycle}`
})

/**
 * 换类别 = 换一套账。
 *
 * 单位下拉是按类别过滤的，旧单位在新类别里根本不存在（「罐」不属于「穿」）；
 * 模式专属的字段同理 —— 把「一件可用天数」原样带到配餐类，
 * 等于给新类别塞一个没人核对过的数，而且它在界面上已经看不见了。
 * 所以这里一并清空，宁可让用户按新口径重填一遍。
 */
function onCategoryChange() {
  form.unit_id = unitOptions.value[0]?.id ?? null
  form.measure = 'day'
  form.days_per_unit = null
  form.uses_per_unit = null
  form.use_cycle_num = 1
  form.use_cycle_unit = 'day'
  form.use_times = 1
  form.hours_per_unit = null
  form.grade = ''
  form.priority = ''
  // 配餐类默认「果腹」—— 它是唯一能顶一顿饭的角色，而这个类别全是吃饭的
  form.satiety = isMeal.value ? 'filling' : ''
}

function resetForm() {
  // 先定类别，再定单位 —— 单位下拉是按类别过滤的
  form.category_id = props.categoryId ?? store.categories[0]?.id ?? null
  form.name = ''
  form.quantity = 0
  form.unit_id = unitOptions.value[0]?.id ?? null
  form.status = 'stocked'
  form.satiety = isMeal.value ? 'filling' : ''
  form.grade = ''
  form.priority = ''
  form.measure = 'day'
  form.days_per_unit = null
  form.uses_per_unit = null
  form.use_cycle_num = 1
  form.use_cycle_unit = 'day'
  form.use_times = 1
  form.stocktake_cycle_days = null
  form.restock_threshold = null
  form.hours_per_unit = null
  form.expire_date = null
  form.notes = ''
}

watch(visible, (open) => {
  if (!open) return
  resetForm()
  // 参考表每次打开都回到收起态：它只在「不知道该填多少」时才需要看
  wearOpen.value = false
  if (!props.itemId) return
  const item = store.items.find((i) => i.id === props.itemId)
  if (!item) return
  // 编辑时类别跟着**物品自己**走，不跟调用方传的默认值
  form.category_id = item.category_id ?? props.categoryId
  form.name = item.name
  form.quantity = item.quantity
  form.unit_id = item.unit_id
  form.satiety = item.satiety
  form.grade = item.grade
  form.priority = item.priority
  form.status = item.status
  // 口径跟着已存的那条走；两条都没填时落回「按天」（更常见的那条）
  form.measure = item.life_mode === 'cycle' ? 'cycle' : 'day'
  form.days_per_unit = item.days_per_unit
  form.uses_per_unit = item.uses_per_unit
  form.use_cycle_num = item.use_cycle_num ?? 1
  form.use_cycle_unit = item.use_cycle_unit || 'day'
  form.use_times = item.use_times ?? 1
  form.stocktake_cycle_days = item.stocktake_cycle_days
  form.restock_threshold = item.restock_threshold
  form.hours_per_unit = item.hours_per_unit
  form.expire_date = item.expire_date
  form.notes = item.notes
})

/** 按次计量是否生效；配餐类永远不生效（消耗由配方决定） */
const byCycle = computed(() => !isMeal.value && form.measure === 'cycle')

// ── 保存前试算（v3.59.11） ──

/**
 * 🔴 走后端（`POST /survival/items/preview/`），不在前端自己乘。
 *    前端乘一遍确实更快，但那会得到**第二份公式**；两份公式迟早分叉，
 *    而分叉是静默的 —— 试算说 150 天、保存后写着 123.7 年，两边都像个正常的数。
 *    后端那个端点用的是与保存**同一行**代码、同一个表单序列化器。
 */
const previewRow = ref<SurvivalItemPreview | null>(null)
const previewError = ref('')
let previewTimer: ReturnType<typeof setTimeout> | undefined

/** 填到能算的程度才发请求 —— 半截配置只会撞上后端的必填校验，那是纯噪音 */
const canPreview = computed(() => {
  if (isMeal.value || !form.category_id || !(form.quantity > 0)) return false
  if (byCycle.value) {
    return Boolean(
      form.uses_per_unit && form.use_cycle_num && form.use_times && form.use_cycle_unit,
    )
  }
  return Boolean(form.days_per_unit)
})

const previewExpected = computed(() => previewRow.value?.expected ?? null)

const previewRangeText = computed(() => {
  const row = previewRow.value
  if (!row || row.expected === null) return ''
  const spread = formatSpread(row.spread)
  // ⚠️ 「无离差」与「算不出来」是两件事，别让 `formatSpread` 的空值文案漏进来
  return [formatScenarioRange(row.days), spread === '算不出来' ? '' : spread]
    .filter(Boolean)
    .join(' · ')
})

/**
 * 把**这一次提交的原始字段**念一遍 —— 本案骗过人的地方就在这里。
 *
 * 表单从来没把「数量」与「每单位能用几次」并排放过：「一份可用 150 天」
 * 这个中间量看着完全正常，错在最后一跳（乘以 300）。所以这里把它们并排念出来。
 * ⚠️ 仍然**不做任何乘除**，只把填过的原话拼回一句。
 */
const previewReadOut = computed(() => {
  const row = previewRow.value
  if (!row || row.expected === null) return ''
  const per = unitName.value || '份'
  const quantity = `数量 ${Number(form.quantity)}${unitName.value}`
  if (byCycle.value) {
    const cycleUnitLabel = useCycleUnits.value
      .find((u) => u.value === form.use_cycle_unit)?.label ?? '天'
    const cycle = formatUseCycle(form.use_cycle_num, cycleUnitLabel, form.use_times)
    return [
      quantity,
      `每${per}能用 ${Number(form.uses_per_unit)} 次`,
      cycle,
    ].filter(Boolean).join(' · ')
  }
  return `${quantity} · 每${per}可用 ${formatDays(row.days_per_unit_effective)}`
})

const previewNote = computed(() => {
  const issue = previewRow.value?.issues?.[0]
  if (previewError.value) return previewError.value
  if (issue) return issue.message
  if (!canPreview.value) return '把「数量」与计量口径填上，这里会先算一遍再保存'
  return ''
})

async function runPreview() {
  const categoryId = form.category_id
  if (!canPreview.value || !categoryId) {
    previewRow.value = null
    previewError.value = ''
    return
  }
  try {
    // 与 store 里一样按 `resp.data` 取 —— 拦截器把整个 AxiosResponse 透传下来了
    const resp = await previewSurvivalItem(buildPayload(categoryId))
    previewRow.value = (resp.data as SurvivalItemPreview) ?? null
    previewError.value = ''
  } catch {
    // 试算是**护栏，不是闸门**：它自己坏了也必须能保存
    previewRow.value = null
    previewError.value = '试算暂时不可用（不影响保存）'
  }
}

watch(
  () => [
    form.category_id, form.quantity, form.unit_id, form.measure,
    form.days_per_unit, form.uses_per_unit, form.use_cycle_num,
    form.use_cycle_unit, form.use_times, form.expire_date, form.status,
  ],
  () => {
    if (previewTimer) clearTimeout(previewTimer)
    // 防抖：`el-input-number` 每敲一位都变，逐字发请求既慢又会让数字跳来跳去
    previewTimer = setTimeout(runPreview, 300)
  },
)

function validateCycle(): boolean {
  if (!byCycle.value) return true
  if (!form.uses_per_unit) {
    ElMessage.warning('按次计量要填「一份能用几次」')
    return false
  }
  if (!form.use_cycle_num || !form.use_times) {
    ElMessage.warning('按次计量要填全使用频次（每几个周期用几次），两个数都不能是 0')
    return false
  }
  return true
}

/**
 * 提交负载 —— **试算与保存共用这一份**（v3.59.11）。
 *
 * ⚠️ 复制成两份就会变成「试算按 A 校验、保存送 B」：两边各自都自洽，
 *    合起来却是一个只在某个字段上出现的幽灵。
 */
function buildPayload(categoryId: number): SurvivalItemFormData {
  return {
    category_id: categoryId,
    name: form.name.trim(),
    quantity: form.quantity,
    unit_id: form.unit_id,
    satiety: isMeal.value ? form.satiety : '',
    grade: form.grade,
    status: form.status,
    priority: isTimeBased.value ? form.priority : '',
    // 配餐类不提交单件可用天数 —— 每天消耗多少由配方决定，两处都填会互相矛盾
    days_per_unit: isMeal.value || byCycle.value ? null : form.days_per_unit,
    // ⚠️ 切换口径时**显式送 null** 清掉另一条 —— 后端判据是「填了按次就按次算」，
    //    留着旧值会让界面显示按次、算法按天，而且找不到地方改。
    //    三个频次字段**一起送 null**：只让 unit 那个送 'day'（当年为了迁就
    //    NOT NULL 列写的）看起来没事，实际把「一列迁就、两列不迁就」的不一致
    //    藏了起来 —— 后端放行 null、数据库拒收，保存直接失败。
    uses_per_unit: byCycle.value ? form.uses_per_unit : null,
    use_cycle_num: byCycle.value ? form.use_cycle_num : null,
    use_cycle_unit: byCycle.value ? form.use_cycle_unit : null,
    use_times: byCycle.value ? form.use_times : null,
    stocktake_cycle_days: form.stocktake_cycle_days,
    restock_threshold: form.restock_threshold,
    hours_per_unit: isTimeBased.value ? form.hours_per_unit : null,
    expire_date: form.expire_date,
    notes: form.notes,
  }
}

async function submit() {
  // 先取出来再判空：`const` 的收窄能一直带到 `buildPayload(...)` 里面，
  // 而 `form.category_id` 这样的属性访问在中间夹了函数调用后不保证还收窄着。
  const categoryId = form.category_id
  if (!categoryId) {
    ElMessage.warning('先选一个类别')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('物品名称不能为空')
    return
  }
  if (form.quantity < 0) {
    ElMessage.warning('数量不能为负')
    return
  }
  if (!validateCycle()) return
  try {
    await store.saveItem(buildPayload(categoryId), props.itemId ?? undefined)
    ElMessage.success('已保存')
    visible.value = false
  } catch (e: unknown) {
    ElMessage.error(extractMessage(e, '保存失败'))
  }
}

function extractMessage(e: unknown, fallback: string): string {
  const response = (e as {
    response?: { status?: number; data?: Record<string, unknown> }
  })?.response
  const data = response?.data
  if (data && typeof data.detail === 'string') return data.detail
  if (data) {
    const first = Object.values(data)[0]
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string') return first
  }
  // 后端崩了（5xx）时它给不出字段级原因。只有一句「保存失败」的话，
  // 一次服务端异常和一次「我填错了」长得一模一样 —— 把状态码带上，
  // 至少能分清是自己要改、还是该去看后端日志。
  if (response?.status && response.status >= 500) {
    return `${fallback}（服务端错误 ${response.status}，请查看后端日志）`
  }
  return fallback
}
</script>

<style scoped>
.survival-item-dialog__unit {
  width: 150px;
  margin-left: 10px;
}
.survival-item-dialog__half {
  width: 200px;
}
.survival-item-dialog__static {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.survival-item-dialog__suffix {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-item-dialog__hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.survival-item-dialog__cycle-text {
  margin: 0 6px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.survival-item-dialog__cycle-num {
  width: 110px;
}
.survival-item-dialog__cycle-unit {
  width: 90px;
}
/* 保存前试算（v3.59.11）—— 它得看着像「结论」，不能像一句注释：
   它是这个表单里唯一的护栏，做轻了就没人读。 */
.survival-item-dialog__preview {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}
.survival-item-dialog__preview-title {
  margin-right: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}
.survival-item-dialog__preview-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-color-primary);
}
.survival-item-dialog__preview-sub {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-item-dialog__preview-read {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.survival-item-dialog__wear {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.survival-item-dialog__wear-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.survival-item-dialog__wear-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}
.survival-item-dialog__wear-sub {
  flex: 1;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.survival-item-dialog__wear-sub--block {
  margin-top: 6px;
}
.survival-item-dialog__wear-hit {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--el-color-primary-light-9);
}
.survival-item-dialog__wear-hit-text {
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}
.survival-item-dialog__wear-actions {
  margin-top: 2px;
}
.survival-item-dialog__wear-table {
  margin-top: 8px;
}
.survival-item-dialog__wear-table :deep(.survival-item-dialog__wear-row--hit) {
  background: var(--el-color-primary-light-9);
}
</style>
