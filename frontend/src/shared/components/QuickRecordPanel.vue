<template>
  <el-dialog
    v-model="dialogVisible"
    title="快速记录"
    :width="isBill ? '460px' : '420px'"
    append-to-body
    @update:model-value="onVisibleChange"
    @keydown.ctrl.enter="onHotkey"
    @keydown.meta.enter="onHotkey"
  >
    <el-form>
      <el-form-item label="类型">
        <el-radio-group v-model="form.module">
          <el-radio value="temporal">日记</el-radio>
          <el-radio value="sugar">小确幸</el-radio>
          <el-radio value="goals">待办</el-radio>
          <el-radio value="wealth">记账</el-radio>
        </el-radio-group>
      </el-form-item>

      <!--
        🔴 记账走的是 `POST /wealth/bill/create/`（与月度页「记一笔」同一个接口），
           不是 `core/QuickRecordView` —— 后者只认 diary/sugar/todo 三类文本记录。
      -->
      <QuickBillInlineForm v-if="isBill" ref="billRef" />

      <el-form-item v-else label="内容">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="3"
          placeholder="记录此刻的想法..."
          @keyup.enter.ctrl="handleSave"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button
        v-if="isBill"
        type="primary"
        :loading="billSaving"
        @click="saveBill"
      >保存</el-button>
      <el-button v-else type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { quickRecord } from '@/shared/api/coreApi'
import QuickBillInlineForm from '@/modules/wealth/components/common/QuickBillInlineForm.vue'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [v: boolean] }>()

const dialogVisible = ref(false)
const form = ref({ module: 'temporal', content: '' })

const billRef = ref<InstanceType<typeof QuickBillInlineForm> | null>(null)
const billSaving = ref(false)

const isBill = computed(() => form.value.module === 'wealth')

watch(() => props.visible, (v) => {
  dialogVisible.value = v
  if (v) form.value = { module: 'temporal', content: '' }
})

const onVisibleChange = (v: boolean) => {
  emit('update:visible', v)
}

/** ⌘/Ctrl + Enter 在任何一种类型下都能保存 —— 记账面板里没有 textarea，热键要提到外层 */
function onHotkey() {
  if (isBill.value) saveBill()
  else handleSave()
}

async function saveBill() {
  if (!billRef.value || billSaving.value) return
  billSaving.value = true
  try {
    await billRef.value.submit()
  } finally {
    billSaving.value = false
  }
}

const handleSave = async () => {
  if (!form.value.content.trim()) {
    ElMessage.warning('请先写点什么')
    return
  }
  try {
    await quickRecord({ module: form.value.module, content: form.value.content })
    dialogVisible.value = false
    emit('update:visible', false)
    ElMessage.success('已记录')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '记录失败')
  }
}
</script>
