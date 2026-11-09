<template>
  <el-card :shadow="props.shadow" class="quote-card">
    <template #header>
      <div class="quote-card-head">
        <span class="quote-card-title">📖 每日金句</span>
        <el-button size="small" text @click="refresh">🔄 换一句</el-button>
      </div>
    </template>

    <div v-if="quote" class="quote-card-body">
      <div class="quote-card-text">{{ quote.content }}</div>
      <div class="quote-card-meta">
        <span v-if="quote.author" class="quote-card-author">— {{ quote.author }}</span>
        <el-tag size="small">{{ quote.language }}</el-tag>
      </div>
    </div>

    <div v-else class="quote-card-empty">
      还没有能上卡的摘录 —— 去
      <el-button link type="primary" @click="goQuotes">摘录管理</el-button>
      加一条，或到「系统设置 → 摘录金句池」把长度上限调大。
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getNextQuote } from '../api/quoteApi'
import type { Quote } from '../types/quoteTypes'

/**
 * 每日金句卡 —— **唯一实现**（v3.63.14 抽出）。
 *
 * 抽出的原因：仪表盘与汇总总览原先各写一遍模板、各写一遍 `refreshQuote()`。
 * 两处走同一个 `/toolkit/quotes/next/`，但空态文案、作者排布、样式各是一套 ⇒
 * 改一处口径必须找到另一处，漏了就变成「同一张卡在两个页面长得不一样」。
 *
 * 取数与空态都收在这里，页面只负责摆放与卡片外观：
 *   - `shadow` 由页面给（仪表盘 never、汇总总览 hover）
 *   - 布局类（`section-card` / `recall-card`）由页面通过 class 透传
 */
const props = withDefaults(defineProps<{ shadow?: 'always' | 'hover' | 'never' }>(), {
  shadow: 'never',
})

const router = useRouter()
const quote = ref<Quote | null>(null)

/**
 * ⚠️ 池为空时后端返回 **204**，`res.data` 是空串 `''`（不是 null）——
 * 直接赋值会让 `v-if="quote"` 判真、把空串当成一条金句渲染。所以显式判类型。
 */
async function refresh() {
  try {
    const res = await getNextQuote()
    const data = res.data
    quote.value = data && typeof data === 'object' ? (data as Quote) : null
  } catch {
    quote.value = null
  }
}

function goQuotes() {
  router.push('/toolkit/quotes')
}

/** 页面级的「刷新」需要能重取一条，暴露给父组件调用 */
defineExpose({ refresh })

onMounted(refresh)
</script>

<style scoped>
.quote-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.quote-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.quote-card-body {
  padding: 4px 0;
}
.quote-card-text {
  font-size: 15px;
  line-height: 1.65;
  color: var(--el-text-color-primary);
  white-space: pre-wrap;
  /* 长度上限放开成可配置后（v3.60.12），长摘录会**全文**上卡 ——
     卡内滚动而不是把卡片撑高；在汇总总览里它与「一条旧结论」并排，
     一张卡变高会带着整行一起变高。 */
  max-height: 180px;
  overflow-y: auto;
}
.quote-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.quote-card-author {
  font-size: 13px;
  font-style: italic;
  color: var(--el-text-color-secondary);
}
/* 空态说清「去哪加」「怎么让长摘录进池」，不留一句干巴巴的「暂无金句」 */
.quote-card-empty {
  padding: 20px 0;
  text-align: center;
  font-size: 13px;
  line-height: 1.9;
  color: var(--el-text-color-placeholder);
}
</style>
