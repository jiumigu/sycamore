<script setup lang="ts">
/**
 * 展厅媒体展示（预览页用，只读）。
 * 图片用 el-image 支持点击放大；视频用原生 <video controls>。
 * 与编辑态的 MediaPicker 分开：那边有上传/删除，这边只呈现。
 */
import { computed } from 'vue'
import type { ShowroomMedia } from '../types/showroomTypes'

const props = defineProps<{
  media: ShowroomMedia[]
}>()

const images = computed(() => props.media.filter(m => m.type === 'image').map(m => m.url))
const videos = computed(() => props.media.filter(m => m.type === 'video'))
</script>

<template>
  <div v-if="media.length" class="media-gallery">
    <div v-if="images.length" class="img-grid">
      <el-image
        v-for="src in images"
        :key="src"
        :src="src"
        :preview-src-list="images"
        :initial-index="images.indexOf(src)"
        fit="cover"
        class="img-cell"
      />
    </div>
    <div v-for="v in videos" :key="v.url" class="vid-cell">
      <video :src="v.url" controls preload="metadata" />
    </div>
  </div>
</template>

<style scoped>
.media-gallery {
  margin-top: 12px;
}
.img-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.img-cell {
  width: 120px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
  cursor: zoom-in;
}
.vid-cell {
  margin-top: 8px;
}
.vid-cell video {
  width: 100%;
  max-width: 480px;
  border-radius: 8px;
  background: #000;
  display: block;
}
</style>
