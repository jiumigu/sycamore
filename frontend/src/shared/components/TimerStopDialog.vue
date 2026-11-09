<!-- 结束计时确认（顶栏与时间页共用同一份实现） -->
<template>
  <el-dialog
    v-model="visible"
    title="结束计时"
    width="420px"
    append-to-body
    :close-on-click-modal="false"
  >
    <div class="stop-body">
      <div class="stop-head">
        <span class="stop-task">{{ session?.task_name }}</span>
        <span class="stop-elapsed">{{ elapsedText }}</span>
      </div>

      <!-- 4 小时这个数是后端给的门槛，前端只在 409 之后才显示这句 -->
      <div v-if="tooLong" class="stop-warn">
        这段已超过 4 小时。确认按 {{ elapsedText }} 记入吗？
      </div>

      <el-form label-width="56px" size="small">
        <el-form-item label="备注">
          <el-input v-model="notes" type="textarea" :rows="3" placeholder="这次做了什么？（选填）" />
        </el-form-item>
      </el-form>

      <!-- 🔴 按钮区放在默认插槽里，不用 #footer 插槽：
           el-dialog 的具名插槽只渲染一次，`tooLong` 变化时按钮文案不会跟着变。 -->
      <div class="stop-actions">
        <el-button size="small" :loading="busy" @click="drop">丢弃</el-button>
        <el-button size="small" type="primary" :loading="busy" @click="confirm">
          {{ tooLong ? '仍要记入' : '保存' }}
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useTimer } from '@/shared/composables/useTimer'
import type { TimerStopResult } from '@/shared/types/timer'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'closed', result: TimerStopResult): void
}>()

const { session, elapsedText, stop, discard } = useTimer()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const notes = ref('')
const tooLong = ref(false)
const busy = ref(false)

watch(() => props.modelValue, (open) => {
  if (!open) return
  notes.value = ''
  tooLong.value = false
  busy.value = false
})

function close() {
  emit('update:modelValue', false)
}

/** 结果提示按 outcome 分支，不猜文案里写了什么 */
function finish(result: TimerStopResult) {
  if (result.outcome === 'saved') {
    ElMessage.success(`已记入 ${result.duration_hours ?? 0} 小时`)
  } else if (result.outcome === 'too_short') {
    ElMessage.warning(`不到 ${result.min_seconds ?? 30} 秒，没有记录`)
  } else if (result.outcome === 'already_closed') {
    ElMessage.info('这条计时已经结束过了')
  }
  emit('closed', result)
  close()
}

async function confirm() {
  if (busy.value) return
  busy.value = true
  try {
    finish(await stop(notes.value, tooLong.value))
  } catch (e: any) {
    const data = e?.response?.data
    if (e?.response?.status === 409 && data?.code === 'too_long') {
      tooLong.value = true
      return
    }
    ElMessage.error(data?.error || '保存失败')
  } finally {
    busy.value = false
  }
}

async function drop() {
  if (busy.value) return
  busy.value = true
  try {
    const result = await discard()
    ElMessage.info('已丢弃，没有写入记录')
    emit('closed', result)
    close()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '丢弃失败')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped lang="scss">
.stop-body {
  .stop-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 10px;

    .stop-task { font-size: 15px; font-weight: 600; color: #1f2937; }
    .stop-elapsed {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 18px;
      font-weight: 600;
      color: #0f766e;
    }
  }
  .stop-warn {
    margin-bottom: 10px;
    padding: 8px 10px;
    border-radius: 6px;
    background: #fff7ed;
    color: #b45309;
    font-size: 12px;
    line-height: 1.6;
  }
  .stop-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
}
</style>
