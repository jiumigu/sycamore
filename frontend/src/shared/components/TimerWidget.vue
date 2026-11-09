<!-- 顶栏便捷计时入口（＋ 号右侧） -->
<template>
  <div class="timer-widget">
    <el-popover
      v-if="!isRunning"
      v-model:visible="pickerVisible"
      placement="bottom-start"
      :width="320"
      trigger="click"
    >
      <template #reference>
        <el-button class="timer-idle" size="small" :loading="loading">
          <el-icon><Timer /></el-icon>
          <span>计时</span>
        </el-button>
      </template>
      <!-- key 递增 ⇒ 每次打开都重建 ⇒ 候选重拉（不同阶段关注点不同，不缓存） -->
      <TimerTaskPicker :key="pickerKey" @started="pickerVisible = false" />
    </el-popover>

    <div v-else class="timer-running">
      <el-tooltip :content="`${session?.task_name}：正在计时`" placement="bottom">
        <span class="running-name">{{ session?.task_name }}</span>
      </el-tooltip>
      <span class="running-elapsed">{{ elapsedText }}</span>
      <el-button class="running-stop" size="small" type="primary" link @click="stopVisible = true">
        结束
      </el-button>
    </div>

    <TimerStopDialog v-model="stopVisible" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Timer } from '@element-plus/icons-vue'
import { useTimer } from '@/shared/composables/useTimer'
import TimerStopDialog from '@/shared/components/TimerStopDialog.vue'
import TimerTaskPicker from '@/modules/temporal/components/TimerTaskPicker.vue'

const { session, isRunning, loading, elapsedText, init } = useTimer()

const pickerVisible = ref(false)
const pickerKey = ref(0)
const stopVisible = ref(false)

watch(pickerVisible, (open) => {
  if (open) pickerKey.value += 1
})

// 计时在别处结束时（页内面板停下、另一个标签页停下），停止弹窗要跟着关，
// 否则会留下一个「对着已结束会话点保存」的空弹窗。
watch(isRunning, (running) => {
  if (!running) stopVisible.value = false
})

// 顶栏常驻：这里做一次就行（模块内幂等，多次调用只拉一次）
onMounted(init)
</script>

<style scoped lang="scss">
.timer-widget {
  display: flex;
  align-items: center;
  flex-shrink: 0;

  .timer-idle {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 32px;
    padding: 0 12px;
    border-radius: 16px;
    font-size: 13px;
  }

  .timer-running {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 32px;
    padding: 0 6px 0 12px;
    border-radius: 16px;
    background: #ecfdf5;
    border: 1px solid #a7f3d0;

    .running-name {
      max-width: 96px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 12px;
      color: #0f766e;
    }

    .running-elapsed {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
      font-weight: 600;
      color: #0f766e;
      font-variant-numeric: tabular-nums;
    }

    .running-stop {
      padding: 0 2px;
      font-size: 12px;
    }
  }
}
</style>
