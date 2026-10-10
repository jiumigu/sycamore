<!--
  物件资产 · 首屏四卡（v3.60.0）

  这四张卡回答的是**唯一**一个问题：我的家当现在是什么状态。

  ⚠️ 四张卡上没有一个前端算出来的数：件数、合计、计入件数、未计入件数
     全部来自 `/property/summary/`（后端 `property_calc.summarize` 唯一真源）。
     这里只做三件事 —— 摆数、按 meta 挂 ⓘ、把「未计入」显式念出来。

  🔴 「计入 N 件 + K 件损坏按 0 计 + M 件未填金额 + J 件算不出」必须并排出现，
     不能只给总额。只给总额的话，界面没法把「少算了」摆出来 ——
     总额看着小一点、件数却是全的，两个数都对不上，还没人会去查。
     而且各个原因要**分开说**，它们指向三个不同的动作：
       损坏按 0 计 → 已经定了，不用补任何数据（它就是不值钱了）；
       未填金额   → 去把价格补上；
       算不出净值 → 去把日期或年限补上。

  ⚠️ 卡①与卡④**没有副行**：设计稿上那里写着「近三年 2 件」这类数，
     但后端没有下发「近三年报废件数」这个量。
     宁可不显示，也不在前端按日期自己数一份 —— 那就是第二份口径
     （而且它会随日历变化，与后端那份迟早不一致）。

  ⚠️ 点击筛选只挂在卡①与卡④：它们对应的是**状态**这一个维度；
     卡②（原值）与卡③（净值）是金额，点了没有对应的筛选项可切，
     做成可点会让人以为「点一下能筛出贵的那几件」（那是排序的事）。
-->
<template>
  <div class="property-cards">
    <!-- ① 在用件数 -->
    <div
      class="property-cards__card"
      :class="{ 'is-active': activeStatus === 'in_use', 'is-clickable': true }"
      @click="emit('filter-status', activeStatus === 'in_use' ? '' : 'in_use')"
    >
      <div class="property-cards__label">
        {{ label('in_use_count', '在用件数') }}
        <MetricTooltip :meta="metaByKey['in_use_count']" :width="340" />
      </div>
      <div class="property-cards__value">{{ summary?.in_use_count ?? 0 }} 件</div>
      <div class="property-cards__sub property-cards__sub--empty">&nbsp;</div>
    </div>

    <!-- ② 原值合计 -->
    <div class="property-cards__card">
      <div class="property-cards__label">
        {{ label('total_amount', '原值合计') }}
        <MetricTooltip :meta="metaByKey['total_amount']" :width="380" />
      </div>
      <div class="property-cards__value">
        {{ formatMoneyOrDash(summary?.total_amount.total ?? null) }}
      </div>
      <div class="property-cards__sub">
        计入 {{ summary?.total_amount.counted ?? 0 }} 件
        <span v-if="totalExcluded" class="property-cards__warn">
          · {{ totalExcluded }}
        </span>
      </div>
    </div>

    <!-- ③ 在用净值合计 -->
    <div class="property-cards__card">
      <div class="property-cards__label">
        {{ label('in_use_net_value', '在用净值合计') }}
        <MetricTooltip :meta="metaByKey['in_use_net_value']" :width="380" />
      </div>
      <div class="property-cards__value">
        {{ formatMoneyOrDash(summary?.in_use_net_value.total ?? null) }}
      </div>
      <div class="property-cards__sub">
        计入 {{ summary?.in_use_net_value.counted ?? 0 }} 件
        <span v-if="netExcluded" class="property-cards__warn">
          · {{ netExcluded }}
        </span>
      </div>
    </div>

    <!-- ④ 已报废 -->
    <div
      class="property-cards__card"
      :class="{ 'is-active': activeStatus === 'scrapped', 'is-clickable': true }"
      @click="emit('filter-status', activeStatus === 'scrapped' ? '' : 'scrapped')"
    >
      <div class="property-cards__label">
        {{ label('scrapped_count', '已报废') }}
        <MetricTooltip :meta="metaByKey['scrapped_count']" :width="340" />
      </div>
      <div class="property-cards__value">{{ summary?.scrapped_count ?? 0 }} 件</div>
      <div class="property-cards__sub property-cards__sub--empty">&nbsp;</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MetricTooltip from '../common/MetricTooltip.vue'
import { formatExcludedHint, formatMoneyOrDash } from '../../utils/propertyFormat'
import type { PropertySummary } from '../../types/propertyTypes'
import type { RatioMeta } from '../../types/wealthTypes'

const props = defineProps<{
  summary: PropertySummary | null
  /** key → 口径元信息（取不到就不渲染气泡，不硬编码文案） */
  metaByKey: Record<string, RatioMeta>
  /** 当前状态筛选值；'' = 不筛 */
  activeStatus: string
}>()

const emit = defineEmits<{
  'filter-status': [status: string]
}>()

/**
 * 卡的标题也来自 meta（`label`），取不到才退回本地兜底。
 *
 * ⚠️ 兜底文案与后端只差一个字，界面上完全看不出来 ——
 *    所以后端有一条「键名清单」用例钉住这几个 key 一定在。
 *    这里的 `??` 只是防止气泡组件拿到 undefined 时整卡渲染不出来。
 */
function label(key: string, fallback: string): string {
  return props.metaByKey[key]?.label ?? fallback
}

const totalExcluded = computed(() =>
  props.summary ? formatExcludedHint(props.summary.total_amount) : '',
)

/**
 * 净值那一栏的几个原因**分开念**（`formatExcludedHint` 内部处理）。
 * ⚠️ 注意这里用的是净值块的计数，不是原值块的 ——
 *    原值块只可能「未填金额」；净值块才有「损坏按 0 计」「未填金额」「算不出」。
 */
const netExcluded = computed(() =>
  props.summary ? formatExcludedHint(props.summary.in_use_net_value) : '',
)
</script>

<style scoped>
.property-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.property-cards__card {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.property-cards__card.is-clickable {
  cursor: pointer;
}
.property-cards__card.is-clickable:hover {
  border-color: var(--el-color-primary-light-5);
}
.property-cards__card.is-active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-7) inset;
}
.property-cards__label {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-cards__value {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}
.property-cards__sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-cards__sub--empty {
  /* 占位：让四张卡等高，不让「没有副行」的两张塌下去 */
  line-height: 1;
}
.property-cards__warn {
  /* 「少算了」是提示，不是错误 —— 不涂红，只让它比周围深一点 */
  color: var(--el-text-color-regular);
}
</style>
