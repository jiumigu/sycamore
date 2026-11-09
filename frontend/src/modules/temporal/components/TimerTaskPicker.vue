<!-- 计时任务选择器（顶栏与时间页共用同一份实现） -->
<template>
  <div class="timer-task-picker">
    <div v-if="loadingNames" class="picker-hint">正在读取最近常用任务…</div>
    <div v-else-if="names.length" class="chips">
      <el-tooltip
        v-for="n in names"
        :key="n.task_name"
        :content="`${n.record_count} 次 · ${n.total_hours} 小时`"
        placement="top"
      >
        <el-button class="chip" size="small" :disabled="starting" @click="begin(n.task_name)">
          {{ n.task_name }}
        </el-button>
      </el-tooltip>
    </div>
    <div v-else-if="namesError" class="picker-hint picker-warn">
      常用任务没读出来，可直接输入任务名
    </div>
    <!-- 与「读取失败」分开说：真没有历史记录，而不是接口挂了 -->
    <div v-else class="picker-hint">还没有常用任务，先输入一个就能开始</div>

    <div class="manual">
      <el-input
        v-model="typed"
        size="small"
        placeholder="或直接输入任务名"
        :disabled="starting"
        @keyup.enter="begin(typed)"
      />
      <el-button size="small" type="primary" :loading="starting" @click="begin(typed)">
        开始
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useTimer } from '@/shared/composables/useTimer'
import { getFrequentTaskNames } from '@/modules/temporal/api/temporalApi'
import type { FrequentTaskName } from '@/modules/temporal/types/temporalTypes'

const emit = defineEmits<{ (e: 'started'): void }>()

const timer = useTimer()

const names = ref<FrequentTaskName[]>([])
const loadingNames = ref(false)
const namesError = ref(false)
const typed = ref('')
const starting = ref(false)

/**
 * 候选每次挂载都重拉：不同阶段关注点不同（口径在后端 `get_frequent_names`，
 * 前端不自己算「最近 30 天 top 8」——那是同一件事的第二把尺子）。
 */
function loadNames() {
  loadingNames.value = true
  namesError.value = false
  getFrequentTaskNames({ months: 3, limit: 10 })
    .then((res) => { names.value = res.data?.items ?? [] })
    .catch(() => {
      // 读不到要明说，别让一片空白被读成「我本来就没有常用任务」
      names.value = []
      namesError.value = true
    })
    .finally(() => { loadingNames.value = false })
}

async function begin(name: string) {
  if (starting.value) return
  const value = (name || '').trim()
  if (!value) {
    // 必填校验：选候选与手输走同一个出口
    return
  }
  starting.value = true
  try {
    const ok = await timer.start(value)
    if (ok) {
      typed.value = ''
      emit('started')
    }
  } finally {
    starting.value = false
  }
}

onMounted(loadNames)
</script>

<style scoped lang="scss">
.timer-task-picker {
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .chip { margin: 0; font-size: 12px; }
  .manual { display: flex; gap: 8px; align-items: center; }
  .picker-hint { margin-top: 8px; font-size: 12px; line-height: 1.6; color: #94a3b8; }
  .picker-warn { color: #b45309; }
}
</style>
