<script setup lang="ts">
/**
 * 展厅媒体选择器（案例 / 馆藏作品表单共用，媒体编辑逻辑只此一份）。
 * v-model: ShowroomMedia[] —— 上传成功后由后端返回 type（image | video），前端不再判。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
// 🔴 模板里的图标组件必须具名导入（同 MenuManager 的教训：只 import * 解析不到）
import { Close, Plus } from '@element-plus/icons-vue'
import { uploadShowroomMedia } from '../api/showroomApi'
import type { ShowroomMedia } from '../types/showroomTypes'

const props = defineProps<{
  modelValue: ShowroomMedia[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ShowroomMedia[]]
}>()

const uploading = ref(false)

async function doUpload(options: UploadRequestOptions) {
  uploading.value = true
  try {
    const res = await uploadShowroomMedia(options.file as File)
    emit('update:modelValue', [...props.modelValue, { type: res.data.type, url: res.data.url }])
  } catch {
    ElMessage.error('上传失败 —— 请确认文件类型（图片 ≤10MB，视频 ≤100MB）')
  } finally {
    uploading.value = false
  }
}

function removeAt(index: number) {
  const next = [...props.modelValue]
  next.splice(index, 1)
  emit('update:modelValue', next)
}
</script>

<template>
  <div class="media-picker">
    <div class="media-list">
      <div v-for="(m, i) in modelValue" :key="m.url" class="media-item">
        <img v-if="m.type === 'image'" :src="m.url" class="media-thumb" alt="">
        <video v-else :src="m.url" class="media-thumb" muted />
        <span class="media-type">{{ m.type === 'image' ? '图' : '视频' }}</span>
        <el-button
          class="media-remove"
          size="small"
          type="danger"
          circle
          @click="removeAt(i)"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
      <el-upload
        :show-file-list="false"
        :http-request="doUpload"
        accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime,video/webm"
        multiple
      >
        <div v-loading="uploading" class="media-add">
          <el-icon><Plus /></el-icon>
          <span>上传图片 / 视频</span>
        </div>
      </el-upload>
    </div>
    <div class="media-tip">图片 ≤10MB，视频 ≤100MB；首图会在预览中当封面</div>
  </div>
</template>

<style scoped>
.media-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-start;
}
.media-item {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
}
.media-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.media-type {
  position: absolute;
  left: 4px;
  bottom: 4px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 11px;
}
.media-remove {
  position: absolute;
  right: 4px;
  top: 4px;
}
.media-add {
  width: 96px;
  height: 96px;
  border: 1px dashed var(--el-border-color);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  cursor: pointer;
}
.media-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
</style>
