<template>
  <div class="sub-header">
    <div class="sub-left">
      <!-- 🔴 返回目标写死 `health-weight`，不用 `router.back()`：
           从收藏 / 刷新直接进子页面时没有上一页，`back()` 会把人送出站外。 -->
      <el-button link class="back-btn" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        <span>体重管理</span>
      </el-button>
      <h2 class="sub-title">{{ title }}</h2>
      <p class="sub-subtitle" v-if="subtitle">{{ subtitle }}</p>
    </div>
    <div class="sub-actions">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'

defineProps<{
  title: string
  subtitle?: string
}>()

const router = useRouter()

function goBack() {
  router.push({ name: 'health-weight' })
}
</script>

<style scoped>
.sub-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.sub-left { min-width: 0; }
.back-btn { padding: 0; margin-bottom: 6px; font-size: 13px; color: #6B7280; }
.back-btn:hover { color: #10B981; }
.sub-title { margin: 0; font-size: 22px; font-weight: 700; color: #1F2937; }
.sub-subtitle { margin: 4px 0 0; font-size: 13px; color: #6B7280; }
.sub-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
</style>
