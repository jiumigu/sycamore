<template>
  <div class="one-liner-review">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">💬 一句话回顾</h2>
        <span class="header-hint">每天那一句「今天发生了什么」</span>
      </div>
      <div class="header-actions">
        <el-input
          v-model="keyword"
          class="search"
          size="small"
          clearable
          placeholder="搜一句话里的字…"
          @input="onKeywordInput"
        />
        <!-- 不用 router.back()：从别处进来时「返回」会退到不相干的地方 -->
        <el-button size="small" @click="goDaily">📝 返回日记流</el-button>
      </div>
    </div>

    <template v-if="data">
      <!-- 结论条：先说覆盖了多少，免得把这些句子当成「全部历史」 -->
      <div class="coverage" :class="`is-${coverage.tone}`">
        <span class="cov-main">{{ coverage.main }}</span>
        <span class="cov-sub">{{ coverage.sub }}</span>
      </div>

      <el-radio-group
        v-if="data.years.length > 1"
        v-model="year"
        class="year-filter"
        :disabled="loading"
        @change="load"
      >
        <el-radio-button :value="0">全部</el-radio-button>
        <el-radio-button v-for="y in data.years" :key="y" :value="y">{{ y }}</el-radio-button>
      </el-radio-group>

      <div v-loading="loading" class="stream-wrap">
        <!-- 两种「空」分开说：搜空了是这关键词没有，没写过是还没开始 -->
        <el-empty
          v-if="!data.items.length"
          :description="data.summary.keyword ? `没有含「${data.summary.keyword}」的一句话` : '还没有一句话'"
        >
          <el-button v-if="data.summary.keyword" @click="clearKeyword">清除搜索</el-button>
          <el-button v-else type="primary" @click="goDaily">去日记流写一句</el-button>
        </el-empty>

        <div v-else class="stream">
          <template v-for="group in groups" :key="group.year">
            <div class="year-divider">
              <span class="year-label">{{ group.year }}</span>
              <span class="year-count">{{ group.items.length }} 天</span>
            </div>
            <div
              v-for="item in group.items"
              :key="item.oid"
              class="entry"
              role="button"
              tabindex="0"
              @click="openDay(item)"
              @keyup.enter="openDay(item)"
            >
              <div class="when">
                <span class="md">{{ item.date.slice(5) }}</span>
                <span class="wd">{{ item.weekday }}</span>
              </div>
              <div class="body">
                <div class="line">{{ item.one_liner }}</div>
                <div class="meta">
                  <span v-if="item.total > 0">那天写了 {{ formatNumber(item.total) }} 字</span>
                  <span v-else class="dim">那天没有字数</span>
                  <span class="dot">·</span>
                  <span>{{ item.otype_display }}</span>
                  <el-tag
                    v-for="t in item.tags"
                    :key="t"
                    size="small"
                    class="tag"
                    effect="plain"
                  >{{ t }}</el-tag>
                </div>
              </div>
              <span class="go">查看 →</span>
            </div>
          </template>
        </div>
      </div>
    </template>

    <el-empty v-else-if="!loading" description="数据没读上来">
      <el-button @click="load">重试</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiErrorText } from '@/shared/utils/apiError'
import * as api from '../api/temporalApi'
import type { OneLinerItem, OneLinerReview } from '../types/temporalTypes'

const router = useRouter()
const loading = ref(false)
const data = ref<OneLinerReview | null>(null)
/** 0 = 全部年份；后端的年份列表里不会出现 0 */
const year = ref(0)
const keyword = ref('')

let keywordTimer: ReturnType<typeof setTimeout> | null = null

/**
 * 结论条：把「这是零散记下来的，不是全部历史」先说清楚。
 *
 * 🔴 分母（`days_total`）在后端只按年份收窄、不随关键词变；关键词生效时
 *    这个比率就没有意义了，所以那一路只报「搜到几天」。
 */
const coverage = computed(() => {
  const s = data.value?.summary
  if (!s) return { tone: 'empty', main: '', sub: '' }
  if (s.keyword) {
    return {
      tone: s.days_with_liner ? 'ok' : 'empty',
      main: `搜到 ${s.days_with_liner} 天含「${s.keyword}」的一句话`,
      sub: `在这 ${s.days_total} 天日记里`,
    }
  }
  if (!s.days_with_liner) {
    return {
      tone: 'empty',
      main: `${s.days_total} 天日记里，还没有一句「今天发生了什么」`,
      sub: '每写完一天，顺手在「一句话记录今天」里留一句，回看时就不用重读全文',
    }
  }
  const span = s.earliest_date === s.latest_date
    ? s.earliest_date
    : `${s.earliest_date} ~ ${s.latest_date}`
  return {
    tone: 'ok',
    main: `${s.days_total} 天日记里，${s.days_with_liner} 天写下了这一句`,
    sub: `${span}${s.year ? ` · 只看 ${s.year} 年` : ''}`,
  }
})

/** 按年分段；items 已是日期倒序，分段时不再排序（顺序即口径，后端定） */
const groups = computed(() => {
  const out: Array<{ year: string; items: OneLinerItem[] }> = []
  for (const item of data.value?.items ?? []) {
    const y = item.date.slice(0, 4)
    const last = out[out.length - 1]
    if (last && last.year === y) last.items.push(item)
    else out.push({ year: y, items: [item] })
  }
  return out
})

function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN')
}

async function load() {
  loading.value = true
  try {
    const res = await api.getOneLiners({
      ...(year.value ? { year: year.value } : {}),
      ...(keyword.value.trim() ? { q: keyword.value.trim() } : {}),
    })
    data.value = res.data
  } catch (e) {
    ElMessage.error(apiErrorText(e, '读取一句话失败'))
    data.value = null
  } finally {
    loading.value = false
  }
}

function onKeywordInput() {
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(load, 300)
}

function clearKeyword() {
  keyword.value = ''
  load()
}

/** 回日记流看那一天：带 date 参数，日记流会按这一天筛出来 */
function openDay(item: OneLinerItem) {
  router.push({ path: '/temporal/daily', query: { date: item.date } })
}

function goDaily() {
  router.push('/temporal/daily')
}

onMounted(load)

onBeforeUnmount(() => {
  if (keywordTimer) clearTimeout(keywordTimer)
})
</script>

<style scoped lang="scss">
.one-liner-review {
  padding: 20px 24px 40px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;

  .header-left {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-shrink: 0;
  }

  .page-title {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    white-space: nowrap;
  }

  .header-hint {
    font-size: 12px;
    color: #909399;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 10px;

    .search {
      width: 220px;
    }
  }
}

.coverage {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  border-radius: 8px;
  border-left: 4px solid #c0c4cc;
  background: #f5f7fa;
  margin-bottom: 14px;

  .cov-main {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
  }

  .cov-sub {
    font-size: 12px;
    color: #909399;
  }

  &.is-ok {
    border-left-color: #10b981;
    background: #f0f9f4;
  }

  &.is-empty {
    border-left-color: #e6a23c;
    background: #fdf6ec;
  }
}

.year-filter {
  margin-bottom: 12px;
}

.stream-wrap {
  min-height: 200px;
}

.stream {
  display: flex;
  flex-direction: column;
}

.year-divider {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 18px 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;

  .year-label {
    font-size: 16px;
    font-weight: 700;
    color: #303133;
  }

  .year-count {
    font-size: 12px;
    color: #909399;
  }
}

.entry {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.15s;

  &:hover,
  &:focus-visible {
    background: #f5f7fa;
    outline: none;

    .go {
      opacity: 1;
    }
  }

  .when {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    width: 62px;
    flex-shrink: 0;
    padding-top: 2px;

    .md {
      font-size: 13px;
      font-weight: 600;
      color: #606266;
      font-variant-numeric: tabular-nums;
    }

    .wd {
      font-size: 11px;
      color: #a8abb2;
    }
  }

  .body {
    flex: 1;
    min-width: 0;

    .line {
      font-size: 15px;
      line-height: 1.5;
      color: #303133;
      overflow-wrap: anywhere;
    }

    .meta {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 3px;
      font-size: 12px;
      color: #909399;

      .dim {
        color: #c0c4cc;
      }

      .dot {
        color: #dcdfe6;
      }

      .tag {
        margin-left: 2px;
      }
    }
  }

  .go {
    flex-shrink: 0;
    font-size: 12px;
    color: #409eff;
    opacity: 0;
    transition: opacity 0.15s;
    padding-top: 4px;
  }
}
</style>
