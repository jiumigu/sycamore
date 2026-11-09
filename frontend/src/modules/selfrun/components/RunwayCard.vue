<template>
  <!-- 🔴 没有长阶段时**整卡不渲染** —— 与 `SelfRunCard` 同一判据：
       空卡片会在首屏长期占位，每次看到都在提醒「你还没开始」。
       ⚠️ 判据是「后端说没阶段」（`no_long_stage`），不是「月数为空」：
         净流入 / 没有为自己 的账同样是空，但那两种**有结论**，卡要留着说清楚。 -->
  <el-card
    v-if="data && data.issue?.code !== 'no_long_stage'"
    shadow="never"
    class="runway-card"
  >
    <div class="rw-row">
      <div class="rw-main">
        <span class="rw-title">💰 跑道</span>
        <span class="rw-months" :class="{ 'rw-null': data.months === null }">{{ monthsLabel }}</span>
        <span v-if="data.months !== null" class="rw-unit">个月</span>
      </div>

      <div class="rw-facts">
        <span v-if="untilLabel" class="rw-fact">
          按当前速度撑到 <strong class="rw-date">{{ untilLabel }}</strong>
        </span>
        <!-- 「撑不到阶段终点」才是「10 万过 3 年」这个问题的直接答案，
             比月数更该抢眼 —— 由后端判（`covers_stage`），前端不拿两个日期自己比。 -->
        <span v-if="data.covers_stage === false" class="rw-fact rw-warn">
          撑不到阶段终点{{ stageEndLabel }}
        </span>
        <!-- 样本不足 ⇒ 速度偏乐观。天数由后端给，前端不自己比 30。 -->
        <span v-if="data.thin && data.sample_days > 0" class="rw-fact rw-thin">
          日均仅 {{ data.sample_days }} 天样本，偏乐观
        </span>
      </div>

      <el-button size="small" text type="primary" class="rw-more" @click="go">账本 →</el-button>
    </div>

    <!-- 算不出来时给一句人话（原因码 → 文案，查表不猜语义） -->
    <div v-if="issueHint" class="rw-hint">{{ issueHint }}</div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getRunway } from '../api/selfrunApi'
import { SUPPORT_ZERO_HINT, SUPPORT_ZERO_LABEL } from '../types/selfrunTypes'
import type { RunwayReading } from '../types/selfrunTypes'

const router = useRouter()
const data = ref<RunwayReading | null>(null)

/** 月数：`null` ⇒ 查原因码表（**不猜语义**，漏加只会显示 `—`）。 */
const monthsLabel = computed(() => {
  const m = data.value?.months
  if (m === null || m === undefined) {
    return SUPPORT_ZERO_LABEL[data.value?.issue?.code ?? ''] ?? '—'
  }
  // 三年尺度上 0.1 个月没有信息量；超过 100 个月时另两位小数更是噪声。
  return m >= 100 ? String(Math.round(m)) : m.toFixed(1)
})

/** 后端给的是 `YYYY-MM-DD`，**原样显示**：不做 `new Date()`（会差 8 小时）。 */
const untilLabel = computed(() => data.value?.support_until ?? '')

const stageEndLabel = computed(() => {
  const end = data.value?.stage?.end_date
  return end ? `（${end}）` : ''
})

const issueHint = computed(() => {
  const code = data.value?.issue?.code
  return code ? SUPPORT_ZERO_HINT[code] ?? '' : ''
})

async function load() {
  try {
    const res = await getRunway()
    data.value = res.data
  } catch {
    // 取不到就整卡不渲染（与 SelfRunCard 一致）：不拿旧数冒充当前值。
    data.value = null
  }
}

function go() {
  router.push('/selfrun/stage')
}

onMounted(load)

/** 「刷新」按钮要能重取 —— 与 `QuoteCard` 同一入口约定。 */
defineExpose({ refresh: load })
</script>

<style scoped>
.runway-card {
  margin-bottom: 16px;
  border-radius: 10px;
}
.runway-card :deep(.el-card__body) {
  padding: 14px 20px;
}

.rw-row {
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
}

.rw-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.rw-title {
  font-weight: 600;
  font-size: 15px;
}
.rw-months {
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
  color: var(--el-color-primary);
  font-variant-numeric: tabular-nums;
}
.rw-months.rw-null {
  font-size: 18px;
  color: var(--el-text-color-secondary);
}
.rw-unit {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.rw-facts {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.rw-date {
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}
.rw-warn {
  color: var(--el-color-danger);
  font-weight: 600;
}
.rw-thin {
  color: var(--el-color-warning);
}

.rw-more {
  margin-left: auto;
}

.rw-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
