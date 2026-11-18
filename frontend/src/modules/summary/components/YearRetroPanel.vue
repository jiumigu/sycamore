<template>
  <div class="yrp">
    <!-- 头部：年份 + 回程 -->
    <div class="yrp__head">
      <el-button size="small" text @click="emit('back')">← 年度明细</el-button>
      <div class="yrp__title">
        <span class="yrp__year">{{ year }} 年</span>
        <el-tag v-if="data?.is_partial" size="small" type="info" effect="plain">
          今年还没过完 · 截至 {{ md(data.as_of) }}
        </el-tag>
      </div>
    </div>

    <!-- 空的三种原因分开说：还没到 / 一条都没有 / 记录太少 -->
    <el-alert
      v-if="emptyText"
      :title="emptyText"
      type="info"
      :closable="false"
      show-icon
      class="yrp__alert"
    />

    <template v-else>
      <!-- 开头句由后端算好（前端不自己拼「有 X 天有记录」） -->
      <p v-if="data?.summary" class="yrp__lead">{{ data.summary.text }}</p>

      <el-alert
        v-if="thinText"
        :title="thinText"
        type="warning"
        :closable="false"
        class="yrp__alert"
      />

      <div v-loading="loading" class="yrp__body">
        <ol class="yrp__flow">
          <li v-for="(seg, i) in data?.segments ?? []" :key="i" class="yrp__seg">
            <span class="yrp__dot" :class="`is-${seg.kind}`" />
            <div class="yrp__main">
              <div class="yrp__date">{{ md(seg.date) }}<template v-if="seg.date_end"> — {{ md(seg.date_end) }}</template></div>
              <p class="yrp__text">{{ seg.text }}</p>
              <!-- 引文形态，不是按钮：这些记录没有逐条跳转的入口，
                   做成按钮就等于给一个点不动的假出口 -->
              <blockquote v-for="(ev, j) in seg.evidence" :key="j" class="yrp__quote">
                <span class="yrp__quote-src">{{ ev.label }} · {{ md(ev.date) }}</span>
                <span class="yrp__quote-text">{{ ev.text }}</span>
              </blockquote>
            </div>
          </li>
        </ol>

        <p v-if="data?.absences?.length" class="yrp__absence">
          这一年，{{ data.absences.join('、') }}一条记录都没有。
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getYearRetro } from '../api/summaryApi'
import type { YearRetroData } from '../types/summaryTypes'

const props = defineProps<{ year: number }>()
const emit = defineEmits<{ back: [] }>()

const data = ref<YearRetroData | null>(null)
const loading = ref(false)
/** 取数失败与「这一年没东西可讲」是两件事，不能都显示成空 */
const failed = ref(false)

async function fetchData() {
  loading.value = true
  failed.value = false
  try {
    const res = await getYearRetro(props.year)
    data.value = res.data as YearRetroData
  } catch {
    data.value = null
    failed.value = true
  } finally {
    loading.value = false
  }
}

watch(() => props.year, fetchData, { immediate: true })

/** 「3 月 8 日」：年份在这一页固定，不重复写 */
function md(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${Number(m)} 月 ${Number(d)} 日`
}

/**
 * 空态只查表，不现场拼文案
 *
 * 🔴 三种「没有」不是一件事：还没到（future）、一条都没有（no_data）、
 *    记录太少（sparse_data）。混成一句「暂无数据」就等于没说。
 */
const EMPTY_TEXT: Record<string, string> = {
  future: '这一年还没到。',
  no_data: '这一年没有任何记录。',
  sparse_data: '这一年的记录太少，讲不出一段完整的话。',
}

const emptyText = computed(() => {
  if (failed.value) return '读取失败 —— 与「这一年没记录」不是一回事，可以重开一次试试。'
  const reason = data.value?.empty_reason
  return reason ? EMPTY_TEXT[reason] ?? '' : ''
})

/** 有段但段数偏少：说明这一年确实平顺，不是坏了 */
const thinText = computed(() =>
  data.value?.thin && data.value.thin_reason === 'few_events' && !emptyText.value
    ? '这一年记录得很勤，但没发生什么值得单说的事 —— 能讲的都在上面了。'
    : '',
)
</script>

<style scoped>
.yrp {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.yrp__head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.yrp__title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.yrp__year {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.yrp__alert {
  margin: 0;
}

.yrp__lead {
  margin: 0;
  max-width: 700px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

.yrp__body {
  min-height: 80px;
  /* 视口高时多显示一点；矮屏不至于只剩两行 */
  max-height: min(58vh, 560px);
  overflow-y: auto;
  /* 滚动条不压正文（macOS 覆盖式滚动条默认不占位，Windows 会） */
  padding-right: 4px;
}

/* 长文靠行宽控制可读性：960 宽的弹窗里整行铺满，一句话要横跨 40+ 字 */
.yrp__flow {
  max-width: 700px;
  margin: 4px 0 0;
  padding: 0;
  list-style: none;
}
/* 时间线：竖线画在每个 item 上，最后一项不留尾巴 —— 否则线会伸到列表外面 */
.yrp__seg {
  position: relative;
  display: flex;
  gap: 10px;
  padding: 0 0 16px 0;
}
.yrp__seg::before {
  content: '';
  position: absolute;
  left: 3px;
  top: 12px;
  bottom: 0;
  width: 1px;
  background: var(--el-border-color-lighter);
}
.yrp__seg:last-child {
  padding-bottom: 0;
}
.yrp__seg:last-child::before {
  display: none;
}
.yrp__dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--el-text-color-placeholder);
}
.yrp__dot.is-first,
.yrp__dot.is-last {
  background: var(--el-color-primary);
}
.yrp__dot.is-gap {
  background: var(--el-color-warning);
}
.yrp__dot.is-stage {
  background: var(--el-color-success);
}

.yrp__main {
  min-width: 0;
  flex: 1;
}
.yrp__date {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-placeholder);
  margin-bottom: 2px;
}
.yrp__text {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--el-text-color-primary);
}

/* 引文块：只给数据，不给按钮形态 */
.yrp__quote {
  margin: 6px 0 0;
  padding: 4px 0 4px 9px;
  border-left: 2px solid var(--el-border-color);
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.yrp__quote-src {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
}
.yrp__quote-text {
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
  word-break: break-word;
}

.yrp__absence {
  margin: 14px 0 0;
  max-width: 700px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-placeholder);
}
</style>
