<template>
  <!-- 🔴 **无阶段时不显示占位卡片** —— 空卡片会在仪表盘第一屏长期占位，
       每次看到都在提醒「你没在做」。入口放「更多」里，不在这里催。 -->
  <el-card v-if="card && stage" shadow="never" class="selfrun-card">
    <div class="sr-head">
      <span class="sr-title">🌱 自我运转</span>
      <span class="sr-sub">{{ stage.name }} · 第 {{ stage.elapsed_days }} 天</span>
      <el-button size="small" text type="primary" class="sr-more" @click="go">去看看 →</el-button>
    </div>
    <div class="sr-body">
      <div class="sr-judge">
        <span class="sr-status" :style="{ color: statusColor }">{{ card.status_label || '—' }}</span>
        <span class="sr-frac">达标 {{ card.ok }} / {{ card.counted }}</span>
        <span class="sr-key">{{ card.period_key ?? '—' }}</span>
      </div>
      <div class="sr-heartbeat">{{ card.heartbeat.message ?? '这一周还在跑' }}</div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSelfRunOverview } from '../api/selfrunApi'
import { FALLBACK_COLOR } from '../types/selfrunTypes'
import type { OverviewCard, SelfRunStage } from '../types/selfrunTypes'

const router = useRouter()
const card = ref<OverviewCard | null>(null)
const stage = ref<SelfRunStage | null>(null)
/** 配色由后端下发 —— 但仪表盘这张卡只调 `overview`，而它**不带 colors**，
 *  所以这里用一张只含「档位 → 色」的**本地兜底**；
 *  它是兜底不是第二份真源：`/selfrun` 页面仍以后端 `colors` 为准。 */
const FALLBACK_PERIOD_COLOR: Record<string, string> = {
  on_track: '#10B981', slipping: '#F59E0B', slid: '#94A3B8',
  no_record: '#CBD5E1', fallow: '#E5E7EB',
}

const statusColor = computed(
  () => FALLBACK_PERIOD_COLOR[card.value?.status ?? ''] ?? FALLBACK_COLOR,
)

async function load() {
  try {
    const res = await getSelfRunOverview()
    card.value = res.data.card
    stage.value = res.data.stage
  } catch {
    card.value = null
    stage.value = null
  }
}

function go() {
  router.push('/selfrun')
}

onMounted(load)
</script>

<style scoped>
.selfrun-card {
  margin-bottom: 16px;
  border-radius: 10px;
  :deep(.el-card__body) { padding: 14px 20px; }
}
.sr-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sr-title { font-weight: 600; font-size: 15px; }
.sr-sub { font-size: 12px; color: var(--el-text-color-secondary); }
.sr-more { margin-left: auto; }
.sr-body { display: flex; align-items: center; gap: 16px; margin-top: 8px; flex-wrap: wrap; }
.sr-judge { display: flex; align-items: baseline; gap: 10px; }
.sr-status { font-size: 20px; font-weight: 700; }
.sr-frac { font-size: 13px; color: var(--el-text-color-regular); }
.sr-key { font-size: 12px; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.sr-heartbeat { font-size: 12px; color: var(--el-text-color-secondary); font-style: italic; }
</style>
