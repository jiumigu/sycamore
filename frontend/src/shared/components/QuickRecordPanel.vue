<template>
  <el-dialog v-model="dialogVisible" title="快速记录" width="420px" append-to-body @update:model-value="onVisibleChange">
    <el-form>
      <el-form-item label="类型">
        <el-radio-group v-model="form.module">
          <el-radio value="temporal">日记</el-radio>
          <el-radio value="sugar">小确幸</el-radio>
          <el-radio value="goals">待办</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="内容">
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
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { quickRecord } from '@/shared/api/coreApi'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [v: boolean] }>()

const dialogVisible = ref(false)
const form = ref({ module: 'temporal', content: '' })

watch(() => props.visible, (v) => {
  dialogVisible.value = v
  if (v) form.value = { module: 'temporal', content: '' }
})

const onVisibleChange = (v: boolean) => {
  emit('update:visible', v)
}

const handleSave = async () => {
  if (!form.value.content.trim()) return
  try {
    await quickRecord(form.value)
    dialogVisible.value = false
    emit('update:visible', false)
    ElMessage.success('已记录')
  } catch {
    ElMessage.error('记录失败')
  }
}
</script>
