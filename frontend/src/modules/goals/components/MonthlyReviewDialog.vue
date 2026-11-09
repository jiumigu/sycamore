<template>
  <el-dialog
    :model-value="visible"
    width="620"
    append-to-body
    class="monthly-review-dialog"
    @update:model-value="$emit('update:visible', $event)"
  >
    <template #header>
      <div class="mr-head">
        <div class="mr-title">本月复盘 · {{ monthLabel }}</div>
        <div class="mr-question">这个月，哪条计划该放弃？</div>
      </div>
    </template>

    <p class="mr-why">
      放弃不是失败 —— 是把资源从<b>不再成立的方向</b>上收回来。
      只需一句理由，不用打分、不用写长文。
    </p>

    <!-- 本月已放弃的（留痕可见，不隐藏） -->
    <div v-if="abandoned.length" class="mr-done">
      <div class="mr-done-title">本月已放弃 {{ abandoned.length }} 条</div>
      <div v-for="r in abandoned" :key="r.id" class="mr-done-row">
        <span class="mr-done-name">{{ r.goal_title || '（目标已删除）' }}</span>
        <span class="mr-done-reason">{{ r.what_blocked }}</span>
      </div>
    </div>

    <!-- 候选：只列还在推进 / 计划中的 -->
    <div v-loading="loading" class="mr-body">
      <div v-if="candidates.length" class="mr-list">
        <el-radio-group v-model="pickedId" class="mr-radios">
          <el-radio v-for="g in candidates" :key="g.id" :value="g.id" class="mr-radio">
            <span class="mr-name">{{ g.title }}</span>
            <span class="mr-meta">
              {{ g.status === 'planning' ? '计划中' : '进行中' }}
              <template v-if="g.deadline"> · 截止 {{ g.deadline }}</template>
              <template v-if="g.progress_percentage"> · 已推进 {{ g.progress_percentage }}%</template>
            </span>
          </el-radio>
        </el-radio-group>
      </div>
      <el-empty
        v-else-if="!loading"
        description="没有可放弃的计划 —— 手上这些都在推进"
        :image-size="80"
      />
    </div>

    <div class="mr-reason">
      <div class="mr-reason-label">为什么放弃它？</div>
      <el-input
        v-model="reason"
        type="textarea"
        :rows="2"
        maxlength="200"
        show-word-limit
        placeholder="例如：这件事的前提变了 / 它已经不是我要的方向 / 我高估了能投入的时间"
      />
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button
        type="danger"
        :loading="saving"
        :disabled="!pickedId || !reason.trim()"
        @click.stop="submit"
      >
        确认放弃
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as goalApi from '../api/goalApi'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  'update:visible': [v: boolean]
  done: []
}>()

interface Candidate {
  id: number
  title: string
  status: string
  deadline?: string | null
  progress_percentage?: number
}

interface ReviewRow {
  id: number
  what_blocked: string
  goal_title?: string
}

const loading = ref(false)
const saving = ref(false)
const candidates = ref<Candidate[]>([])
const abandoned = ref<ReviewRow[]>([])
const pickedId = ref<number | null>(null)
const reason = ref('')

const now = new Date()
const monthKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const monthLabel = `${now.getFullYear()} 年 ${now.getMonth() + 1} 月`

/** request 返回的是 AxiosResponse（拦截器不解包），列表可能带分页壳 */
function unwrap(resp: { data?: unknown }): unknown[] {
  const d = resp?.data as { results?: unknown[] } | unknown[] | undefined
  if (Array.isArray(d)) return d
  return (d?.results as unknown[]) ?? []
}

async function load() {
  loading.value = true
  try {
    const [a, b, reviews] = await Promise.all([
      goalApi.getGoalList({ status: 'in-progress', page_size: 100 }),
      goalApi.getGoalList({ status: 'planning', page_size: 100 }),
      goalApi.getReviewList({ review_type: 'monthly', month: monthKey }),
    ])
    candidates.value = [...unwrap(a), ...unwrap(b)] as Candidate[]
    abandoned.value = unwrap(reviews) as ReviewRow[]
  } finally {
    loading.value = false
  }
}

const picked = computed(() => candidates.value.find((g) => g.id === pickedId.value) || null)

async function submit() {
  if (!picked.value || !reason.value.trim()) return
  saving.value = true
  try {
    await goalApi.abandonGoal(picked.value.id, reason.value.trim())
    ElMessage.success(`已放弃「${picked.value.title}」，理由已记进本月复盘`)
    pickedId.value = null
    reason.value = ''
    emit('done')
    emit('update:visible', false)
  } catch (e: unknown) {
    // 后端 400/409 的 detail 要原样透出，不能只说「保存失败」
    const resp = e as { response?: { data?: Record<string, unknown> } }
    const data = resp?.response?.data
    const msg =
      (data?.detail as string) ||
      (Array.isArray(data?.reason) ? (data?.reason as string[])[0] : '') ||
      '放弃失败，请重试'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      pickedId.value = null
      reason.value = ''
      load()
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.mr-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.mr-title {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.mr-question {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.mr-why {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}

.mr-done {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}
.mr-done-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.mr-done-row {
  display: flex;
  gap: 10px;
  font-size: 13px;
  padding: 3px 0;
}
.mr-done-name {
  color: var(--el-text-color-primary);
  flex-shrink: 0;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mr-done-reason {
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mr-list {
  max-height: 260px;
  overflow-y: auto;
  padding-right: 4px;
}
.mr-radios {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 2px;
}
.mr-radio {
  height: auto;
  padding: 8px 6px;
  margin-right: 0;
  border-radius: 6px;
}
.mr-radio:hover {
  background: var(--el-fill-color-light);
}
.mr-name {
  font-size: 14px;
  color: var(--el-text-color-primary);
}
.mr-meta {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.mr-reason {
  margin-top: 14px;
}
.mr-reason-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin-bottom: 6px;
}
</style>
