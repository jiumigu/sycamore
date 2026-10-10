<template>
  <div class="ask-review">
    <div class="head-bar">
      <el-button text @click="$router.push('/toolkit/ask-library')">
        <el-icon><ArrowLeft /></el-icon> 返回 AI 问答库
      </el-button>
    </div>

    <h2 class="page-title">🧠 问答回顾</h2>
    <p class="subtitle">
      按场景列出全部问答主题，最久没碰过的排最前 —— 点主题进去，给当时那条回答补一句你自己的结论。
    </p>

    <!-- 入口说明：这一页存在的理由 -->
    <el-card class="stats-card" shadow="never">
      <div class="stats-row">
        <span class="stat"><b>{{ stats.topics }}</b> 个主题</span>
        <span class="stat"><b>{{ stats.answers }}</b> 条回答</span>
        <span class="stat done"><b>{{ stats.marked }}</b> 已标结论</span>
        <span class="stat todo"><b>{{ stats.unmarked }}</b> 还没标</span>
      </div>
      <p v-if="stats.unmarked > 0" class="stats-hint">
        这 {{ stats.unmarked }} 条是当时的「原料」，还不是「结论」—— 它们不会被推到汇总总览。
        回顾时顺手标一条，它下次就有机会在首页被你想起来。
      </p>
      <p v-else-if="stats.answers > 0" class="stats-hint ok">全部回答都已标过结论。</p>
    </el-card>

    <el-card v-if="!loading && groups.length === 0" class="group-card">
      <div class="chart-empty">
        问答库还是空的 —— 先去
        <el-button link type="primary" @click="$router.push('/toolkit/ask-library')">AI 问答库</el-button>
        记一条提问与回答。
      </div>
    </el-card>

    <el-card v-for="g in groups" :key="g.scene_name" class="group-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span class="card-title">{{ g.scene_id === null ? '🗂 未分类' : '🗂 ' + g.scene_name }}</span>
          <el-tag size="small" type="info">{{ g.topics.length }} 个主题</el-tag>
        </div>
      </template>
      <el-table :data="g.topics" size="small" style="width: 100%">
        <el-table-column label="主题" min-width="280">
          <template #default="{ row }">
            <div class="topic-title">{{ row.title }}</div>
            <div class="topic-q">{{ row.question }}</div>
          </template>
        </el-table-column>
        <el-table-column label="回答" width="70" align="right">
          <template #default="{ row }">{{ row.answer_count }}</template>
        </el-table-column>
        <el-table-column label="已标结论" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.concluded_count > 0" size="small" type="success">
              {{ row.concluded_count }} / {{ row.answer_count }}
            </el-tag>
            <el-tag v-else size="small" type="info">0 / {{ row.answer_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="冷落" width="90" align="right">
          <template #default="{ row }">
            <el-tag v-if="row.days_idle >= 14" size="small" type="warning">{{ row.days_idle }} 天</el-tag>
            <span v-else class="idle-plain">{{ row.days_idle }} 天</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openReview(row)">回顾</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 回顾抽屉：标记动作发生在「看得见判断依据」的这一刻 -->
    <el-drawer v-model="drawerVisible" :title="current?.title || '回顾'" size="64%" destroy-on-close>
      <div v-loading="detailLoading" class="review-body">
        <template v-if="current">
          <div class="review-question">
            <span class="q-label">当时的问题</span>
            <p class="q-text">{{ current.question }}</p>
          </div>

          <p class="mark-hint">
            标「采纳」或写一句备注，这条就会成为「结论」，有机会出现在汇总总览的
            「一条旧结论」卡上。不标也行 —— 这里只是给你一个顺手记下来的地方。
          </p>

          <div v-for="a in answers" :key="a.id" class="answer-card" :class="{ 'is-target': a.id === targetAnswerId }">
            <div class="answer-head">
              <el-tag size="small" effect="plain">{{ a.ai }}</el-tag>
              <span class="answer-time">{{ fmtTime(a.asked_at) }}</span>
              <el-tag v-if="a.verdict" size="small" :type="verdictType(a.verdict)">{{ a.verdict }}</el-tag>
              <el-tag v-else size="small" type="info">未标记</el-tag>
              <el-button
                size="small"
                link
                type="primary"
                class="expand-btn"
                @click="toggleExpand(a.id)"
              >
                {{ expanded.has(a.id) ? '收起' : '展开全文' }}
              </el-button>
            </div>

            <div v-if="a.question" class="answer-subq">追问：{{ a.question }}</div>

            <p class="answer-text" :class="{ expanded: expanded.has(a.id) }">{{ a.answer }}</p>

            <div class="mark-row">
              <el-radio-group v-model="a.verdict" size="small">
                <el-radio-button value="">未标记</el-radio-button>
                <el-radio-button value="采纳">采纳</el-radio-button>
                <el-radio-button value="备用">备用</el-radio-button>
                <el-radio-button value="不采用">不采用</el-radio-button>
              </el-radio-group>
              <el-button
                size="small"
                type="primary"
                :loading="savingId === a.id"
                @click="saveAnswer(a)"
              >
                保存
              </el-button>
            </div>

            <el-input
              v-model="a.note"
              type="textarea"
              :rows="2"
              maxlength="500"
              show-word-limit
              placeholder="你自己的结论（一句话就够。写在这里的内容会优先作为「一条旧结论」显示）"
            />
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import {
  getAskReview,
  getAskTopic,
  updateAskAnswer,
} from '@/modules/toolkit/api/askLibraryApi'
import type {
  AskAnswerItem,
  AskReviewGroup,
  AskReviewStats,
  AskReviewTopicItem,
} from '@/modules/toolkit/api/askLibraryApi'

const loading = ref(false)
const groups = ref<AskReviewGroup[]>([])
const stats = ref<AskReviewStats>({ topics: 0, answers: 0, marked: 0, unmarked: 0 })

const route = useRoute()
/** 深链定位到的那条回答（来自汇总总览「一条旧结论」卡的 `?answer=`）；`null` = 无定位 */
const targetAnswerId = ref<number | null>(null)

const drawerVisible = ref(false)
const current = ref<AskReviewTopicItem | null>(null)
const answers = ref<AskAnswerItem[]>([])
const detailLoading = ref(false)
const savingId = ref<number | null>(null)
const expanded = ref<Set<number>>(new Set())

async function load() {
  loading.value = true
  try {
    const res = await getAskReview()
    groups.value = (res.data?.groups || []) as AskReviewGroup[]
    stats.value = res.data?.stats || { topics: 0, answers: 0, marked: 0, unmarked: 0 }
  } catch {
    ElMessage.error('加载回顾数据失败')
  } finally {
    loading.value = false
  }
}

async function openReview(row: AskReviewTopicItem) {
  current.value = row
  drawerVisible.value = true
  detailLoading.value = true
  expanded.value = new Set()
  try {
    const res = await getAskTopic(row.id)
    answers.value = (res.data?.answers || []) as AskAnswerItem[]
    // 深链进来的那条**默认展开全文** —— 用户点「看全文」要的就是全文，
    // 落地之后再让他自己找一次「展开全文」，等于没解决当初「点不开」的问题。
    // （手动点主题「回顾」时 `targetAnswerId` 为 null，不受影响。）
    const t = targetAnswerId.value
    if (t != null && answers.value.some((a) => a.id === t)) {
      expanded.value = new Set([t])
    }
  } catch {
    ElMessage.error('加载该主题的回答失败')
    answers.value = []
  } finally {
    detailLoading.value = false
  }
}

/**
 * 深链入口：`?topic=<主题 id>&answer=<回答 id>`（汇总总览「一条旧结论」卡的「看全文 →」）。
 *
 * 卡上只放得下摘要，判断依据与完整回答都在这里 ⇒ 落地必须**直接到那一条**。
 * 只给 `topic` 不给 `answer` 是不够的：一个主题常挂多条回答，
 * 用户还得自己在一串回答里找是哪一条。
 */
async function openFromQuery() {
  const topicQ = route.query.topic
  if (!topicQ) {
    // 不是深链进来的（例如从问答库点「回顾」）：不留上一次的定位与高亮
    targetAnswerId.value = null
    return
  }
  const row = groups.value.flatMap((g) => g.topics).find((t) => String(t.id) === String(topicQ))
  if (!row) {
    // 主题被删掉 / 链接过期：说清楚，别静默停在列表页让人以为「点了没反应」
    ElMessage.warning('这条结论对应的主题已经不在了')
    return
  }
  const answerQ = route.query.answer
  targetAnswerId.value = answerQ ? Number(answerQ) : null
  await openReview(row)
  // 抽屉有展开过渡，等一帧再滚；滚不到也不影响「高亮标住是哪一条」
  await nextTick()
  document.querySelector('.review-body .answer-card.is-target')
    ?.scrollIntoView({ block: 'start', behavior: 'smooth' })
}

async function saveAnswer(a: AskAnswerItem) {
  savingId.value = a.id
  try {
    await updateAskAnswer(a.id, { verdict: a.verdict, note: a.note })
    ElMessage.success('已保存')
    await load()
    // 统计与分组刷新后，抽屉里的行引用要换到新数据上（否则 concluded_count 还是旧的）
    const id = current.value?.id
    if (id != null) {
      const fresh = groups.value.flatMap((g) => g.topics).find((t) => t.id === id)
      if (fresh) current.value = fresh
    }
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingId.value = null
  }
}

function toggleExpand(id: number) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

function verdictType(v: string): 'success' | 'warning' | 'danger' | 'info' {
  if (v === '采纳') return 'success'
  if (v === '备用') return 'warning'
  if (v === '不采用') return 'danger'
  return 'info'
}

/** 后端下发的是带时区的 ISO 串，直接切片取到分钟 —— 不 `new Date()`，避免两把尺子 */
function fmtTime(iso: string): string {
  if (!iso || iso.length < 16) return ''
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`
}

onMounted(async () => {
  await load()
  await openFromQuery()
})

// 同一条路由**只换 query** 时组件会被复用、不再触发 mounted
// （「汇总总览 → 看全文 → 返回 → 再看全文」走的正是这条路径）
// ⇒ 深链必须监听 query，否则第二次点「看全文」什么都不会发生。
watch(
  () => route.query,
  () => {
    if (route.name === 'ask-library-review') void openFromQuery()
  },
)
</script>

<style scoped lang="scss">
.ask-review {
  padding: 20px;

  .head-bar { margin-bottom: 8px; }

  .page-title {
    margin: 0 0 4px;
    font-size: 22px;
    font-weight: 600;
    color: #1f2937;
  }

  .subtitle {
    margin: 0 0 16px;
    font-size: 13px;
    color: #6b7280;
  }

  .stats-card {
    border: none;
    border-radius: 10px;
    margin-bottom: 16px;

    :deep(.el-card__body) { padding: 14px 16px; }
  }

  .stats-row {
    display: flex;
    align-items: center;
    gap: 24px;
    font-size: 13px;
    color: #4b5563;

    .stat b { font-size: 17px; margin-right: 4px; }
    .stat.done b { color: #16a34a; }
    .stat.todo b { color: #d97706; }
  }

  .stats-hint {
    margin: 10px 0 0;
    font-size: 12px;
    line-height: 1.7;
    color: #9ca3af;

    &.ok { color: #16a34a; }
  }

  .group-card {
    border: none;
    border-radius: 10px;
    margin-bottom: 14px;

    :deep(.el-card__body) { padding: 0 16px 12px; }
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 10px;

    .card-title { font-size: 15px; font-weight: 600; color: #1f2937; }
  }

  .topic-title {
    font-size: 13px;
    font-weight: 500;
    color: #1f2937;
  }

  .topic-q {
    margin-top: 2px;
    font-size: 12px;
    color: #9ca3af;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .idle-plain { font-size: 12px; color: #6b7280; }

  .chart-empty {
    padding: 28px 0;
    text-align: center;
    font-size: 13px;
    color: #9ca3af;
  }

  .review-body {
    padding: 0 4px 20px;

    .review-question {
      padding: 12px 14px;
      border-radius: 8px;
      background: #f8fafc;

      .q-label {
        font-size: 12px;
        color: #9ca3af;
      }

      .q-text {
        margin: 6px 0 0;
        font-size: 13px;
        line-height: 1.7;
        color: #374151;
        white-space: pre-wrap;
      }
    }

    .mark-hint {
      margin: 14px 0;
      font-size: 12px;
      line-height: 1.7;
      color: #9ca3af;
    }

    .answer-card {
      padding: 14px;
      margin-bottom: 14px;
      border: 1px solid #eef0f3;
      border-radius: 10px;

      /* 深链定位到的那条：从首页「看全文」进来时要一眼认出是哪一条 */
      &.is-target {
        border-color: var(--el-color-primary-light-5);
        box-shadow: 0 0 0 2px var(--el-color-primary-light-8);
      }
    }

    .answer-head {
      display: flex;
      align-items: center;
      gap: 8px;

      .answer-time { font-size: 12px; color: #9ca3af; }
      .expand-btn { margin-left: auto; }
    }

    .answer-subq {
      margin-top: 8px;
      font-size: 12px;
      color: #6b7280;
    }

    .answer-text {
      margin: 10px 0 0;
      font-size: 13px;
      line-height: 1.75;
      color: #374151;
      white-space: pre-wrap;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;

      &.expanded {
        display: block;
        -webkit-line-clamp: unset;
        overflow: visible;
      }
    }

    .mark-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 12px 0 10px;
    }
  }
}
</style>
