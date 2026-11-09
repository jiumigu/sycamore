<template>
  <el-form-item label="取数方式">
    <el-radio-group v-model="kind">
      <el-radio-button value="manual">手工登记</el-radio-button>
      <el-radio-button value="auto">自动取数</el-radio-button>
      <el-radio-button value="auto_plus_manual">自动 + 手工补记</el-radio-button>
    </el-radio-group>
  </el-form-item>

  <template v-if="sourceKind === 'manual'">
    <el-alert
      type="info" :closable="false" show-icon
      title="手工项不需要取数器"
      :description="manualHint"
    />
  </template>
  <template v-else>
    <el-form-item label="取数器">
      <el-select v-model="reader" style="width: 100%">
        <el-option
          v-for="r in readerChoices" :key="r.value"
          :label="readerLabel(r)" :value="r.value"
        />
      </el-select>
    </el-form-item>

    <!-- `where_key === 'l2'`：按活动类型过滤（候选值取自库里，不是常量表） -->
    <el-form-item v-if="currentReader?.where_key === 'l2'" label="活动类型">
      <el-select
        v-model="where" multiple filterable allow-create
        placeholder="留空 = 不过滤（全部活动类型都算）" style="width: 100%"
      >
        <el-option v-for="v in l2Options" :key="v" :label="v" :value="v" />
      </el-select>
      <div class="scf-hint">
        候选值来自<b>库里的「活动类型」</b>（不是常量表）—— 这就是「深度工作」那一层。
      </div>
    </el-form-item>

    <!-- `where_key === 'key'`：白名单键（写错会直接报错，所以给你选、不给你填） -->
    <el-form-item v-else-if="currentReader?.where_key === 'key'" label="取值键">
      <el-select v-model="where" style="width: 100%">
        <el-option v-for="k in mvKeys" :key="k" :label="k" :value="k" />
      </el-select>
    </el-form-item>

    <!-- `where_key === 'work_kind'`：按作品类型过滤（「这月画了几张」） -->
    <el-form-item v-else-if="currentReader?.where_key === 'work_kind'" label="作品类型">
      <el-select
        v-model="where" clearable
        placeholder="留空 = 不限类型（全部作品都算）" style="width: 100%"
      >
        <el-option
          v-for="o in workKindOptions" :key="o.value"
          :label="o.label" :value="o.value"
        />
      </el-select>
      <div class="scf-hint">
        按作品的<b>类型</b>过滤。选「绘画作品」就只数这期成形的画 ——
        作品页新建时类型没选对，这里就会漏，而页面上只是少一件（不报错）。
      </div>
    </el-form-item>

    <el-form-item v-else label="附加条件">
      <div class="scf-muted">
        这个取数器自带固定口径，没有需要你填的条件。
      </div>
    </el-form-item>

    <el-alert
      v-if="sourceKind === 'auto_plus_manual'"
      type="warning" :closable="false" show-icon
      title="「自动 + 手工补记」= 自动取的 + 你补的，两者相加"
      description="线下发生的事自动源覆盖不到，所以留一个补记口。只有真的两边都会有时才选它。"
    />
  </template>

  <el-alert
    v-if="sourceKind !== 'manual' && !readerChoices.length"
    type="error" :closable="false" show-icon
    title="拿不到取数器清单"
    description="枚举是随模板列表一起下发的 —— 先点「刷新」把列表拉回来，再回来改这条。"
  />
</template>

<script setup lang="ts">
/** 自我运转 · 「取数方式」表单块（模板库 / 改 KPI 两处共用）
 *
 * 🔴 这块**只渲染，不持有状态** —— 值全由父组件给、改动逐字段抛回去。
 *    两处各写一份的话，「换了取数器要清掉上一条的 `where`」这种细节
 *    只会在一处生效，另一处就静默串味（表现是条件还留着、但已经不属于这个取数器）。
 */
import { computed, watch } from 'vue'
import { useSelfRunStore } from '../stores/selfrunStore'
import type { ReaderOption, SelfRunEnumOption, SourceKind } from '../types/selfrunTypes'
import type { WhereValue } from '../utils/sourceConfig'

const props = defineProps<{
  sourceKind: SourceKind
  readerKind: string
  whereValue: WhereValue
  /** 手工项的说明文案 —— 两处场景不同（模板讲「以后建阶段」，KPI 讲「这条现在就生效」） */
  manualHint?: string
}>()

const emit = defineEmits<{
  (e: 'update:sourceKind', v: SourceKind): void
  (e: 'update:readerKind', v: string): void
  (e: 'update:whereValue', v: WhereValue): void
  /** 取了另一个取数器 ⇒ 父组件清 `baseWhere` 与界面上的条件（这里不做，见文件头注释）。
   *  ⚠️ 带上**新的** kind：此刻 `props.readerKind` 还是旧值，父组件拿不到新取数器
   *     的 `where_key`，也就清不对（多选该清成 `[]`、单选该清成 `''`）。 */
  (e: 'readerSwitch', nextKind: string): void
}>()

const store = useSelfRunStore()

const kind = computed({
  get: () => props.sourceKind,
  set: (v: SourceKind) => emit('update:sourceKind', v),
})

const reader = computed({
  get: () => props.readerKind,
  set: (v: string) => {
    if (v !== props.readerKind) emit('readerSwitch', v)
    emit('update:readerKind', v)
  },
})

const where = computed({
  get: () => props.whereValue,
  set: (v: WhereValue) => emit('update:whereValue', v),
})

const readerChoices = computed<ReaderOption[]>(() => store.templateEnum?.readers ?? [])
const l2Options = computed<string[]>(() => store.templateEnum?.l2_options ?? [])
const mvKeys = computed<string[]>(() => store.templateEnum?.module_value_keys ?? [])
/** 作品类型候选 —— 后端 `WORK_KIND_CHOICES` 直发，前端零副本（加类型不必改这里） */
const workKindOptions = computed<SelfRunEnumOption[]>(
  () => store.templateEnum?.work_kind_options ?? [],
)

const currentReader = computed<ReaderOption | null>(
  () => readerChoices.value.find(r => r.value === props.readerKind) ?? null,
)

const manualHint = computed(() => props.manualHint
  ?? '系统里没有对应模块的东西（比如宣纸、画）只能手工记 —— 每周/每月自己去「本周状态」里补一笔。')

/**
 * 「手工登记 → 自动取数」⇒ 把 `manual_sum` 这个取数器清掉。
 *
 * 🔴 不清的话界面上那个下拉会**留着上一任的 `manual_sum` 并显示成已选**：
 *    切完看起来配好了，实际上数还是从手工登记来（等于没切），而页面不报错。
 *    清空之后保存会被「选了自动取数，就得挑一个取数器」挡住 —— 错误落在
 *    你正在点的这个按钮上，而不是三天后「这条怎么还是 0」。
 */
watch(() => props.sourceKind, (v) => {
  if (v !== 'manual' && props.readerKind === 'manual_sum') emit('update:readerKind', '')
})

/** 「时间统计 · 按时长求和」这种念法 —— 让人知道数据要去哪个模块补 */
function readerLabel(r: ReaderOption): string {
  return r.hint ? `${r.value}（来源：${r.hint}）` : r.value
}
</script>

<style scoped>
.scf-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; }
.scf-muted { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
