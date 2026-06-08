<template>
  <div
    class="treasure-card"
    :class="{
      'is-bad': thing.record_type === '歹',
      unavailable: thing.record_type === '好' && !thing.still_available,
    }"
  >
    <div class="card-header">
      <span class="card-type-badge" :class="thing.record_type === '歹' ? 'badge-bad' : 'badge-good'">
        {{ thing.record_type_display || (thing.record_type === '歹' ? '👎 歹物' : '👍 好物') }}
      </span>
      <span class="card-category">{{ thing.category_display || thing.category }}</span>
    </div>

    <h3 class="card-name">{{ thing.name }}</h3>

    <!-- 好物 -->
    <template v-if="thing.record_type === '好'">
      <p class="card-text">{{ thing.why_good }}</p>
      <div class="card-meta">
        <span v-if="thing.where_to_find" class="meta-location">📍 {{ thing.where_to_find }}</span>
        <span v-if="thing.scene" class="meta-scene">{{ thing.scene }}</span>
        <el-tag v-if="thing.still_available" size="small" type="success">✅ 还能找到</el-tag>
        <el-tag v-else size="small" type="danger">❌ 已找不到</el-tag>
      </div>
    </template>

    <!-- 歹物 -->
    <template v-else>
      <div class="bad-section">
        <div class="bad-field">
          <span class="bad-label">💥 踩坑：</span>
          <span>{{ thing.avoid_reason }}</span>
        </div>
        <div v-if="thing.consequence" class="bad-field">
          <span class="bad-label">😵 后果：</span>
          <span>{{ thing.consequence }}</span>
        </div>
        <div v-if="thing.scene" class="bad-field">
          <span class="bad-label">📍 场景：</span>
          <span>{{ thing.scene }}</span>
        </div>
      </div>
      <div class="card-meta">
        <el-tag size="small" type="warning">⚠️ 避免再犯</el-tag>
      </div>
    </template>

    <div class="card-actions">
      <el-button text size="small" @click="$emit('edit', thing)">
        <el-icon><Edit /></el-icon> 编辑
      </el-button>
      <el-button text size="small" type="danger" @click="$emit('delete', thing)">
        <el-icon><Delete /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Edit, Delete } from '@element-plus/icons-vue'
import type { GoodThing } from '../types/treasureTypes'

defineProps<{ thing: GoodThing }>()

defineEmits<{
  edit: [thing: GoodThing]
  delete: [thing: GoodThing]
}>()
</script>

<style scoped lang="scss">
.treasure-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  transition: all 0.2s;
  border: 1px solid #f0f0f0;

  &:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); transform: translateY(-1px); }

  &.unavailable {
    opacity: 0.65;
    background: #fafafa;
  }

  &.is-bad {
    border-color: #ffd8bf;
    background: #fffaf5;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    .card-category { font-size: 13px; color: #666; }
  }

  .card-type-badge {
    font-size: 12px;
    padding: 1px 8px;
    border-radius: 4px;
    &.badge-good { background: #e6f7e6; color: #389e0d; }
    &.badge-bad { background: #fff1f0; color: #cf1322; }
  }

  .card-name { margin: 0 0 6px; font-size: 16px; font-weight: 600; }

  .card-text {
    margin: 0 0 10px;
    font-size: 14px;
    color: #444;
    line-height: 1.6;
  }

  .bad-section {
    margin-bottom: 10px;
    .bad-field {
      font-size: 14px;
      color: #444;
      line-height: 1.6;
      margin-bottom: 4px;
      .bad-label { font-weight: 500; color: #cf1322; }
    }
  }

  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    font-size: 12px;
    color: #888;
    margin-bottom: 8px;
  }

  .card-actions {
    display: flex;
    justify-content: flex-end;
    gap: 4px;
    border-top: 1px solid #f0f0f0;
    padding-top: 8px;
  }
}
</style>
