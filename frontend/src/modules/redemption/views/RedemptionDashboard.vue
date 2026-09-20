<template>
  <div class="redemption-dashboard">
    <!-- 窗口与状态条 -->
    <el-card class="block" shadow="never">
      <div class="window-bar">
        <div>
          <span class="wb-label">赎回期窗口</span>
          <span class="wb-range">{{ stats.window.start }} ~ {{ stats.window.end }}</span>
        </div>
        <div class="wb-stats">
          <div class="wb-item">
            <span class="wb-num">{{ stats.window.elapsed_days }}</span><span class="wb-cap">已过(天)</span>
          </div>
          <div class="wb-item">
            <span class="wb-num">{{ stats.window.remaining_days }}</span><span class="wb-cap">剩余(天)</span>
          </div>
          <div class="wb-item">
            <el-tag :type="stats.tracking_status === 'active' ? 'success' : 'info'" size="small">
              {{ stats.tracking_status === 'active' ? '追踪中' : '已暂停' }}
            </el-tag>
          </div>
        </div>
      </div>
      <el-progress
        :percentage="Math.round((stats.window.elapsed_days / stats.window.total_days) * 100)"
        :stroke-width="10" :show-text="false"
      />
      <div class="phase-note">当前阶段：<b>{{ phase }}</b></div>
    </el-card>

    <!-- 钱面：现金池 -->
    <el-card class="block" shadow="never">
      <template #header><span class="card-title">启动现金池（B2 口径）</span></template>
      <div class="pool-grid">
        <div class="pool-cell">
          <span class="pc-cap">本金</span><span class="pc-num">¥{{ fmt(stats.pool.principal) }}</span>
        </div>
        <div class="pool-cell">
          <span class="pc-cap">中途注入</span><span class="pc-num">¥{{ fmt(stats.pool.injected) }}</span>
        </div>
        <div class="pool-cell hl">
          <span class="pc-cap">当前余额</span><span class="pc-num">¥{{ fmt(stats.pool.balance) }}</span>
        </div>
        <div class="pool-cell">
          <span class="pc-cap">日均净消耗</span><span class="pc-num">¥{{ fmt(stats.pool.avg_daily) }}</span>
        </div>
        <div class="pool-cell">
          <span class="pc-cap">预计可支撑到</span>
          <span class="pc-num">{{ stats.pool.support_until || '永不耗尽' }}</span>
        </div>
      </div>
      <div class="sync-row">
        <el-button size="small" @click="doSync('preview')">同步到资金推演（预览）</el-button>
        <el-button size="small" type="primary" @click="doSync('apply')">写入推演</el-button>
        <span v-if="syncMsg" class="sync-msg">{{ syncMsg }}</span>
      </div>
    </el-card>

    <!-- 钱面：赎回归属档位 -->
    <el-card class="block" shadow="never">
      <template #header><span class="card-title">赎回归属分布（窗口内）</span></template>
      <div class="tier-list">
        <div v-for="t in stats.tier" :key="t.period_tag" class="tier-item">
          <el-tag :style="tagStyle(t.period_tag)" size="small" effect="plain">
            {{ t.period_tag === 'unmarked' ? '未标记' : t.period_tag }}
          </el-tag>
          <span class="tier-count">{{ t.count }} 笔</span>
          <span class="tier-total">¥{{ fmt(t.total) }}</span>
        </div>
      </div>
    </el-card>

    <!-- 时间面：覆盖率 + 归因 -->
    <el-card class="block" shadow="never" v-if="stats.time">
      <template #header>
        <span class="card-title">时间归因</span>
        <span v-if="stats.time.coverage_warn" class="warn-badge">⚠ 数据覆盖率偏低，结论谨慎</span>
      </template>

      <!-- 覆盖率条（硬要求，常驻） -->
      <div class="coverage">
        <div class="cov-head">
          <span>数据来源覆盖率</span>
          <span class="cov-rate">{{ (stats.time.coverage_rate * 100).toFixed(1) }}%</span>
        </div>
        <el-progress
          :percentage="Math.min(100, Math.round(stats.time.coverage_rate * 100))"
          :color="stats.time.coverage_warn ? '#F59E0B' : '#10B981'"
          :stroke-width="12"
        />
        <div class="cov-sub">
          已记录 {{ stats.time.covered_hours }}h / 理论 {{ stats.time.theoretical_hours }}h
          （按每天 12h 可支配估算；ATracker 之外的空转未记，覆盖率天然偏低）
        </div>
      </div>

      <!-- 四类小时分布 -->
      <div class="attr-grid">
        <div v-for="(h, k) in stats.time.hours" :key="k" class="attr-cell">
          <span class="ac-cap" :style="{ color: attrMeta(k).color }">{{ k }}</span>
          <span class="ac-num">{{ h.toFixed(1) }}h</span>
        </div>
      </div>

      <div class="metric-row">
        <div class="metric-cell">
          <span class="mc-cap">成长占比</span>
          <span class="mc-num">{{ (stats.time.toward_ratio * 100).toFixed(1) }}%</span>
        </div>
        <div class="metric-cell">
          <span class="mc-cap">单位赎回成本</span>
          <span class="mc-num">¥{{ stats.unit_cost != null ? formatAmount(stats.unit_cost, 2) : '—' }}/h</span>
        </div>
      </div>
      <div class="note-line">
        单位赎回成本 = 为自己净支出 ÷ 净赎回小时（已过天数 × 8h）。
        10 万 ¥ ÷ 1096 天 ÷ 8h ≈ <b>11.4 ¥/h</b> 为理论下限；高于它说明钱花在了自己身上。
      </div>
    </el-card>

    <el-card class="block" shadow="never" v-else>
      <div class="paused-note">
        追踪已暂停：评价与告警已隐藏，记录能力保留。恢复后可查看时间归因与单位成本。
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as rapi from '../api/redemptionApi'
import type { RedemptionStats } from '../types/redemptionTypes'
import { ATTRIBUTION_META } from '../types/redemptionTypes'
import { PERIOD_TAG_META } from '@/modules/wealth/types/wealthTypes'
import { formatAmount } from '@/shared/utils/format'

const stats = ref<RedemptionStats>(emptyStats())
const phase = ref('')
const syncMsg = ref('')

function emptyStats(): RedemptionStats {
  return {
    window: { start: '', end: '', total_days: 0, elapsed_days: 0, remaining_days: 0 },
    tracking_status: 'active',
    pool: { principal: 0, injected: 0, self_expense: 0, self_income: 0, balance: 0, avg_daily: 0, support_until: null },
    tier: [],
    time: null,
    unit_cost: null,
  }
}

function fmt(n: number) {
  return formatAmount(n, 0)
}

function tagStyle(tag: string) {
  const m = PERIOD_TAG_META[tag] || PERIOD_TAG_META.unmarked
  return { color: m.color, borderColor: m.color, backgroundColor: m.bg }
}

function attrMeta(k: string) {
  return ATTRIBUTION_META[k] || { color: '#888', bg: '#eee' }
}

async function load() {
  try {
    const res = await rapi.getRedemptionStats()
    stats.value = res.data
    const cfg = await rapi.getRedemption()
    phase.value = cfg.data.derived?.phase || ''
  } catch {
    ElMessage.error('加载赎回统计失败')
  }
}

async function doSync(mode: 'preview' | 'apply') {
  try {
    const res = await rapi.syncScenario(mode)
    if (mode === 'preview') {
      syncMsg.value = `预览：现金 ¥${res.data.cash} → 支撑 ${res.data.support_weeks ?? '∞'} 周（耗尽年龄 ${res.data.end_age ?? '—'}）`
    } else {
      syncMsg.value = '已写入资金推演（current_cash / daily_budget）'
      ElMessage.success('已同步到推演')
    }
  } catch {
    ElMessage.error('同步失败')
  }
}

onMounted(load)
</script>

<style scoped>
.redemption-dashboard { display: flex; flex-direction: column; gap: 14px; }
.block { border-radius: 10px; }
.card-title { font-weight: 600; }
.window-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.wb-label { color: var(--el-text-color-secondary); margin-right: 8px; }
.wb-range { font-weight: 600; }
.wb-stats { display: flex; gap: 18px; align-items: center; }
.wb-item { display: flex; flex-direction: column; align-items: center; }
.wb-num { font-size: 20px; font-weight: 700; }
.wb-cap { font-size: 12px; color: var(--el-text-color-secondary); }
.phase-note { margin-top: 8px; font-size: 13px; color: var(--el-text-color-regular); }

.pool-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.pool-cell { display: flex; flex-direction: column; gap: 4px; padding: 10px; background: var(--el-fill-color-light); border-radius: 8px; }
.pool-cell.hl { background: #F3E8FF; }
.pc-cap { font-size: 12px; color: var(--el-text-color-secondary); }
.pc-num { font-size: 16px; font-weight: 700; }
.sync-row { margin-top: 12px; display: flex; align-items: center; gap: 10px; }
.sync-msg { font-size: 12px; color: var(--el-text-color-secondary); }

.tier-list { display: flex; flex-wrap: wrap; gap: 12px; }
.tier-item { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: var(--el-fill-color-light); border-radius: 8px; }
.tier-count { font-size: 13px; }
.tier-total { font-weight: 600; }

.warn-badge { margin-left: 10px; font-size: 12px; color: #D97706; }
.coverage { margin-bottom: 14px; }
.cov-head { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px; }
.cov-rate { font-weight: 700; }
.cov-sub { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }

.attr-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
.attr-cell { display: flex; flex-direction: column; gap: 4px; padding: 10px; background: var(--el-fill-color-light); border-radius: 8px; }
.ac-cap { font-weight: 600; }
.ac-num { font-size: 16px; font-weight: 700; }

.metric-row { display: flex; gap: 14px; margin-bottom: 8px; }
.metric-cell { flex: 1; display: flex; flex-direction: column; gap: 2px; padding: 10px; background: var(--el-fill-color-light); border-radius: 8px; }
.mc-cap { font-size: 12px; color: var(--el-text-color-secondary); }
.mc-num { font-size: 18px; font-weight: 700; }
.note-line { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }
.paused-note { font-size: 13px; color: var(--el-text-color-secondary); text-align: center; padding: 20px; }
</style>
