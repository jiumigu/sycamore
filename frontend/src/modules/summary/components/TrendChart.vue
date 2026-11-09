<template>
  <div ref="rootRef" class="mgrid" @mouseleave="tip = null">
    <!--
      口径：**覆盖率写出来，强度用底色深浅**。

      为什么不再用柱高：上一版「柱高 = 强度、颜色 = 覆盖率」两套编码叠在一起，
      读者要先把柱子读成长短、再把颜色读成百分比，才拼得出一个月的状态 ——
      多一步就是「看不懂」。现在只剩一件事要解释：
      **数字是覆盖率，深浅是强度**。
    -->
    <div class="mgrid__legend">
      <span class="lg"><span class="lg__txt">48%</span>文字 = 覆盖率（有记录 / 该有的）</span>
      <span class="lg"><span class="lg__ramp"></span>底色越深 = 强度越高（按行归一）</span>
      <span class="lg"><span class="lg__neg"></span>红底 = 负强度（净流出）</span>
      <span class="lg lg--muted"><span class="lg__hollow"></span>虚框 = 本期未结 · 空格 = 还没到</span>
    </div>

    <div class="mgrid__body">
      <div class="mrow mrow--head">
        <span class="mrow__label"></span>
        <span v-for="m in 12" :key="m" class="mcell mcell--head">{{ m }}月</span>
      </div>

      <div v-for="mod in store.trendModules" :key="mod.module" class="mrow">
        <span class="mrow__label">
          {{ mod.label }}
          <em>{{ mod.intensity_unit }}</em>
        </span>

        <span
          v-for="(col, i) in columns(mod)"
          :key="i"
          class="mcell"
          :class="[`is-${col.state}`, { 'is-empty-cov': col.state === 'ok' && col.coverage === 0 }]"
          :style="col.state === 'ok' ? { background: col.fill } : undefined"
          @mouseenter="onEnter($event, mod, col, i)"
          @click="col.state === 'ok' && pickMonth(i + 1)"
        >
          <span v-if="col.state === 'ok'" class="mcell__txt" :style="{ color: col.fg }">
            {{ col.label }}
          </span>
          <span v-else-if="col.state === 'unclosed'" class="mcell__dash">—</span>
        </span>
      </div>
    </div>

    <!--
      🔴 提示框必须挂到 body：本组件长在 el-card 里，而卡片是 overflow:hidden，
         绝对定位在卡片内的提示框会被**下边缘裁掉**（最后一行「阅读」最明显）。
         坐标改用视口坐标（clientX/clientY）+ position:fixed，
         并在下方放不下时翻到光标上方 —— 见 `placeTip()`。
    -->
    <Teleport to="body">
      <div
        v-if="tip"
        ref="tipEl"
        class="mgrid__tip"
        :style="{
          left: tip.x + 'px',
          top: tip.y + 'px',
          visibility: tip.placed ? 'visible' : 'hidden',
        }"
      >
        <div class="tip__title">{{ tip.title }}</div>
        <div class="tip__row">
          <span>覆盖率</span>
          <span class="tip__v">{{ tip.coverageText }}</span>
        </div>
        <div class="tip__row">
          <span>强度</span>
          <span class="tip__v">{{ tip.intensityText }}</span>
        </div>
        <div v-if="tip.hint" class="tip__hint">{{ tip.hint }}</div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useSummaryStore } from '../stores/summaryStore'
import { formatSignedAmount } from '@/shared/utils/format'
import type { TrendModuleMeta } from '../types/summaryTypes'

/**
 * 月度「覆盖率 + 强度」
 *
 * 🔴 两个量用两种**不同性质**的载体，而不是两种图形编码：
 *    - **覆盖率 → 文字**（`48%`）：要读准、要能比较，文字最直接；
 *    - **强度 → 底色深浅**：它是「感觉量」（这个月记得厚不厚），
 *      用深浅表达比用长短更贴近直觉，也不会被误读成「进度条」。
 *
 * 为什么不按绝对刻度上色：7 个维度量纲不同（步/天 vs 元/月），
 * 共用一个色阶只会让「只有时间投入有颜色」。所以按**行**归一
 * （该维度年内最高月 = 最深），行与行之间不比深浅 —— 图例里写明。
 *
 * 🔴 三种「没有」三样长相：虚框 = 本期未结 · 空格 = 还没到 · `0%` = 有该期但没记。
 */
const store = useSummaryStore()
const emit = defineEmits<{ 'pick-month': [month: number] }>()

/**
 * 点格子开当月明细。
 *
 * 🔴 必须在这里顺手收起提示框：提示框已经 Teleport 到 body 且 z-index 3000，
 *    点开后鼠标仍停在格子上 ⇒ `mouseleave` 不触发 ⇒ 提示框会**盖在弹窗之上**。
 */
function pickMonth(month: number) {
  tip.value = null
  emit('pick-month', month)
}

type CellState = 'ok' | 'future' | 'unclosed'

interface Column {
  state: CellState
  coverage: number | null
  intensity: number | null
  /** 格子里写的字：**取整的覆盖率**（`48%`）。小数留给提示框 —— 格子里放不下 */
  label: string
  /** 底色（rgba）；`ok` 状态才有 */
  fill: string
  /** 文字颜色：底色深了就翻白，否则看不清 */
  fg: string
  negative: boolean
}

interface TipInfo {
  /** 视口坐标（fixed 定位用）—— 不再是容器内坐标 */
  x: number
  y: number
  /** 量完真实尺寸、定好位才显示，避免在 (0,0) 闪一下 */
  placed: boolean
  title: string
  coverageText: string
  intensityText: string
  hint: string
}

const tip = ref<TipInfo | null>(null)
const tipEl = ref<HTMLElement | null>(null)
const rootRef = ref<HTMLElement | null>(null)

/** 正强度：绿；负强度：红（净流出不是「更弱」，是方向相反） */
const HUE_OK = '16, 185, 129'
const HUE_NEG = '239, 68, 68'
/** 底色透明度区间：最浅也要看得见「这里有值」，最深不压住文字 */
const ALPHA_MIN = 0.10
const ALPHA_MAX = 0.86

function depth(t: number): number {
  return ALPHA_MIN + (ALPHA_MAX - ALPHA_MIN) * Math.max(0, Math.min(t, 1))
}

/**
 * 视口内摆放：右侧放不下 ⇒ 翻到光标左侧；下方放不下 ⇒ 翻到光标上方。
 *
 * 🔴 旧实现把坐标 clamp 在**容器内**（`r.height - 30`），最后一行「阅读」的提示框
 *    顶边被压到容器底部，再 `translate(14px,14px)` 往下推 ⇒ 整块掉出卡片被裁掉。
 *    现在按**真实宽高**（`offsetWidth/offsetHeight`）判边界，且允许溢出卡片。
 */
function placeTip(cx: number, cy: number, w: number, h: number): { x: number; y: number } {
  const gap = 14
  const pad = 8
  const vw = window.innerWidth
  const vh = window.innerHeight

  let x = cx + gap
  if (x + w > vw - pad) x = cx - gap - w
  x = Math.max(pad, Math.min(x, vw - w - pad))

  let y = cy + gap
  if (y + h > vh - pad) y = cy - gap - h
  y = Math.max(pad, Math.min(y, vh - h - pad))

  return { x, y }
}

function columns(mod: TrendModuleMeta): Column[] {
  const theme = store.trend
  const maxAbs = Math.max(
    theme?.intensity_max?.[mod.module] ?? 0,
    ...store.trendData.map((m) => Math.abs(m.intensity[mod.module] ?? 0)),
  ) || 1

  return Array.from({ length: 12 }, (_, i) => {
    const row = store.trendData[i]
    const base: Column = {
      state: 'future', coverage: null, intensity: null, label: '',
      fill: 'transparent', fg: '', negative: false,
    }
    if (!row || row.is_future) return base

    const cov = row.coverage[mod.module] ?? null
    if (cov === null) return { ...base, state: 'unclosed' }

    const iv = row.intensity[mod.module] ?? null
    // 取整：格子窄（窄屏只有 38px），`94.7%` 会挤；小数在提示框里给全
    const label = `${Math.round(cov)}%`
    if (iv === null) {
      // 有该期、一条没记：文字 `0%` 已经说清了，底色留白（没有强度可染）
      return { ...base, state: 'ok', coverage: cov, label }
    }
    const t = Math.abs(iv) / maxAbs
    const neg = iv < 0
    return {
      state: 'ok',
      coverage: cov,
      intensity: iv,
      label,
      fill: `rgba(${neg ? HUE_NEG : HUE_OK}, ${depth(t).toFixed(3)})`,
      // 深底翻白：0.45 以上已经是中深绿/红，再压深色字就看不清了
      fg: depth(t) > 0.45 ? '#FFFFFF' : 'var(--el-text-color-primary)',
      negative: neg,
    }
  })
}

function money(v: number | null): string {
  return v === null ? '—' : formatSignedAmount(v, 2)
}

function onEnter(ev: MouseEvent, mod: TrendModuleMeta, col: Column, idx: number) {
  const title = `${idx + 1}月 · ${mod.label}`
  if (col.state === 'future') {
    showTip(ev, { title, coverageText: '—', intensityText: '—', hint: '这个月还没到' })
    return
  }
  if (col.state === 'unclosed') {
    showTip(ev, {
      title, coverageText: '—', intensityText: '—',
      hint: '按月记账的维度要等本期结束才算覆盖（每月 1 号不无故掉档）',
    })
    return
  }

  const row = store.trendData[idx]
  const covered = row?.covered?.[mod.module]
  const periods = row?.periods?.[mod.module]
  const pct = col.coverage === null ? '—' : `${col.coverage}%`
  const coverageText = covered !== undefined && periods
    ? `${pct}（${covered}/${periods} ${mod.period_word}）`
    : pct
  const intensityText = col.intensity === null
    ? '—'
    : `${mod.module === 'wealth' ? money(col.intensity) : col.intensity.toLocaleString('zh-CN', { maximumFractionDigits: 1 })} ${mod.intensity_unit}`

  const hints: string[] = []
  if (col.negative) hints.push('强度为负（净流出），底色用红')
  if (col.coverage === 0) hints.push('这个月有，但一条都没记')
  if (col.intensity === null) hints.push('没有记录 ⇒ 强度算不出来')

  showTip(ev, { title, coverageText, intensityText, hint: hints.join('；') })
}

/**
 * 先渲染（`placed=false` ⇒ visibility:hidden）→ 量真实宽高 → 定好位 → 显示。
 *
 * 为什么要量：提示框有 `hint` 时比没有时高一行，硬编码高度会在某几种格子上又冒出裁切。
 */
async function showTip(ev: MouseEvent, info: Omit<TipInfo, 'x' | 'y' | 'placed'>) {
  tip.value = { ...info, x: 0, y: 0, placed: false }
  await nextTick()
  const el = tipEl.value
  if (!el || !tip.value) return
  const { x, y } = placeTip(ev.clientX, ev.clientY, el.offsetWidth, el.offsetHeight)
  tip.value = { ...tip.value, x, y, placed: true }
}

/**
 * 滚动时提示框会脱离光标（fixed 坐标不跟随滚动）⇒ 直接收起。
 * 捕获阶段监听，卡片内部的小滚动区也能收到。
 */
function closeTip() { tip.value = null }
onMounted(() => window.addEventListener('scroll', closeTip, true))
onBeforeUnmount(() => window.removeEventListener('scroll', closeTip, true))
</script>

<style scoped>
.mgrid {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  /* 窄卡片时字号要跟着收（见 `.mcell__txt` 的 `@container`） */
  container-type: inline-size;
}
.mgrid__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.lg {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.lg--muted { color: var(--el-text-color-placeholder); }
.lg__txt {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  padding: 0 3px;
  border-radius: 2px;
  background: var(--el-fill-color);
  font-size: 9px;
  color: var(--el-text-color-regular);
  font-variant-numeric: tabular-nums;
}
.lg__ramp {
  width: 46px;
  height: 8px;
  border-radius: 2px;
  background: linear-gradient(90deg, rgba(16, 185, 129, 0.1), rgba(16, 185, 129, 0.86));
}
.lg__neg {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: rgba(239, 68, 68, 0.7);
}
.lg__hollow {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  border: 1px dashed var(--el-border-color-darker);
}

.mgrid__body {
  display: flex;
  flex-direction: column;
}
.mrow {
  display: grid;
  grid-template-columns: 84px repeat(12, 1fr);
  align-items: stretch;
  min-height: 40px;
}
.mrow--head { min-height: 16px; }
.mrow__label {
  display: flex;
  flex-direction: column;
  justify-content: center;
  font-size: 12px;
  color: var(--el-text-color-regular);
  padding-right: 6px;
  white-space: nowrap;
}
.mrow__label em {
  font-style: normal;
  font-size: 10px;
  color: var(--el-text-color-placeholder);
}

.mcell {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 1px;
  border-radius: 3px;
  background: var(--el-fill-color-lighter);
  cursor: pointer;
  transition: background 0.2s;
}
.mcell:hover { outline: 1px solid var(--el-border-color-darker); }
.mcell--head {
  background: none;
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  cursor: default;
  margin: 0;
}
.mcell--head:hover { outline: none; }
.mcell.is-future,
.mcell.is-unclosed {
  cursor: default;
  background: none;
}
.mcell.is-future { border: 1px dashed var(--el-border-color-lighter); }
.mcell.is-unclosed { border: 1px dashed var(--el-border-color); }
.mcell.is-future:hover,
.mcell.is-unclosed:hover { outline: none; }

/* 覆盖率文字：等宽数字，读数时不会左右跳 */
.mcell__txt {
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
/* 窄屏格子只有 38px：字号得跟着收，否则 `100%` 会被裁 */
@container (max-width: 720px) {
  .mcell__txt { font-size: 10px; }
}
.mcell.is-empty-cov .mcell__txt { color: var(--el-color-danger); }
.mcell__dash { font-size: 11px; color: var(--el-text-color-placeholder); }

/* 提示框：Teleport 到 body + fixed 定位（坐标就是 clientX/clientY，间距在 placeTip 里加）
   🔴 不要再改回 absolute —— 卡片 overflow:hidden 会把最后一行的提示框裁掉一半 */
.mgrid__tip {
  position: fixed;
  z-index: 3000;
  pointer-events: none;
  min-width: 190px;
  max-width: 280px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid var(--el-border-color-light);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.1);
  font-size: 12px;
  color: var(--el-text-color-primary);
}
.tip__title {
  font-weight: 600;
  margin-bottom: 4px;
}
.tip__row {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  color: var(--el-text-color-secondary);
}
.tip__v {
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}
.tip__hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
</style>
