<template>
  <div class="template-card" @click="handleQuickRecord">
    <div class="card-icon">{{ template.icon }}</div>
    <div class="card-name">{{ template.name }}</div>
    <div class="card-points">+{{ template.points }}</div>
    <el-dropdown
      class="card-actions"
      trigger="click"
      @command="handleCommand"
      @click.stop
    >
      <el-icon class="more-btn"><MoreFilled /></el-icon>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="edit">
            <el-icon><Edit /></el-icon> 编辑
          </el-dropdown-item>
          <el-dropdown-item command="delete" divided>
            <el-icon><Delete /></el-icon> 删除
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { MoreFilled, Edit, Delete } from '@element-plus/icons-vue'
import type { SugarTemplate } from '../types/sugarTypes'

const props = defineProps<{
  template: SugarTemplate
}>()

const emit = defineEmits<{
  (e: 'quickRecord', template: SugarTemplate): void
  (e: 'edit', template: SugarTemplate): void
  (e: 'delete', template: SugarTemplate): void
}>()

function handleQuickRecord() {
  emit('quickRecord', props.template)
}

function handleCommand(cmd: string) {
  if (cmd === 'edit') emit('edit', props.template)
  if (cmd === 'delete') emit('delete', props.template)
}
</script>

<style scoped lang="scss">
.template-card {
  position: relative;
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  padding: 16px 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;

  &:hover {
    border-color: var(--el-color-primary);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    transform: translateY(-2px);

    .card-actions { opacity: 1; }
  }

  &:active {
    transform: scale(0.96);
  }

  .card-icon {
    font-size: 28px;
    margin-bottom: 6px;
    line-height: 1;
  }

  .card-name {
    font-size: 13px;
    color: #1F2937;
    font-weight: 500;
    margin-bottom: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-points {
    font-size: 12px;
    color: var(--el-color-primary);
    font-weight: 600;
  }

  .card-actions {
    position: absolute;
    top: 4px;
    right: 4px;
    opacity: 0;
    transition: opacity 0.2s;

    .more-btn {
      font-size: 16px;
      color: #9CA3AF;
      padding: 2px;
      border-radius: 4px;

      &:hover {
        background: #F3F4F6;
        color: #374151;
      }
    }
  }
}
</style>
