<!-- 时间任务清单页内的完整计时面板 -->
<template>
  <el-drawer
    v-model="visible"
    title="⏱ 实时计时"
    size="400px"
    :append-to-body="true"
  >
    <div class="timer-panel">
      <div v-if="isRunning" class="running-card">
        <div class="running-task">{{ session?.task_name }}</div>
        <div class="running-elapsed">{{ elapsedText }}</div>
        <div class="running-actions">
          <el-button type="primary" size="small" @click="stopVisible = true">结束并记录</el-button>
          <el-button size="small" @click="dropNow">丢弃</el-button>
        </div>
      </div>
      <div v-else class="idle-card">
        还没开始。点下面的常用任务就能开始计时，结束后自动落成一条时间记录。
      </div>

      <el-divider content-position="left">
        {{ isRunning ? '切换到别的任务（当前这段会先自动结束）' : '开始计时' }}
      </el-divider>

      <TimerTaskPicker @started="onStarted" />

      <TimerStopDialog v-model="stopVisible" @closed="onClosed" />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTimer } from '@/shared/composables/useTimer'
import TimerStopDialog from '@/shared/components/TimerStopDialog.vue'
import TimerTaskPicker from '@/modules/temporal/components/TimerTaskPicker.vue'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  /** 记录有增删 —— 让外层刷新列表 */
  (e: 'changed'): void
}>()

const { session, isRunning, elapsedText, discard } = useTimer()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const stopVisible = ref(false)

function onStarted() {
  // 开始计时不产生记录，不需要刷新列表
}

function onClosed() {
  emit('changed')
}

async function dropNow() {
  try {
    await ElMessageBox.confirm('丢弃后不会写入时间记录。继续？', '丢弃这次计时', {
      type: 'warning',
      confirmButtonText: '丢弃',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await discard()
    ElMessage.info('已丢弃，没有写入记录')
    emit('changed')
  } catch {
    ElMessage.error('丢弃失败')
  }
}
</script>

<style scoped lang="scss">
.timer-panel {
  .running-card {
    padding: 16px;
    border-radius: 10px;
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    text-align: center;

    .running-task {
      font-size: 15px;
      font-weight: 600;
      color: #065f46;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .running-elapsed {
      margin: 6px 0 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 30px;
      font-weight: 600;
      color: #0f766e;
      font-variant-numeric: tabular-nums;
    }
  }

  .idle-card {
    padding: 14px 16px;
    border-radius: 10px;
    background: #f8fafc;
    color: #64748b;
    font-size: 13px;
    line-height: 1.7;
  }
}
</style>
