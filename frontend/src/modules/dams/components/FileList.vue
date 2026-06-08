<template>
  <div class="file-list">
    <div class="toolbar">
      <el-button type="primary" @click="emit('add')">新增文件</el-button>
      <el-select
        v-model="filters.category"
        placeholder="分类筛选"
        clearable
        style="width: 140px"
        @change="emit('filter', filters)"
      >
        <el-option
          v-for="opt in FILE_CATEGORY_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-select
        v-model="filters.organized"
        placeholder="整理状态"
        clearable
        style="width: 140px"
        @change="emit('filter', filters)"
      >
        <el-option label="已整理" :value="true" />
        <el-option label="未整理" :value="false" />
      </el-select>
      <el-select
        v-model="filters.duplicate"
        placeholder="重复状态"
        clearable
        style="width: 140px"
        @change="emit('filter', filters)"
      >
        <el-option label="重复" :value="true" />
        <el-option label="非重复" :value="false" />
      </el-select>
    </div>

    <el-table :data="files" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="name" label="文件名" min-width="200" show-overflow-tooltip />
      <el-table-column prop="file_category_label" label="分类" width="100" />
      <el-table-column prop="file_size_mb" label="大小(MB)" width="100" align="right">
        <template #default="{ row }">
          {{ row.file_size_mb?.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column prop="access_count" label="访问次数" width="90" align="center" />
      <el-table-column label="状态" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_duplicate" type="warning" size="small">重复</el-tag>
          <el-tag v-if="row.is_organized" type="success" size="small">已整理</el-tag>
          <span v-if="!row.is_duplicate && !row.is_organized" class="text-muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="emit('edit', row)">编辑</el-button>
          <el-button
            v-if="!row.is_organized"
            link
            type="success"
            size="small"
            @click="emit('organize', row.id)"
          >
            标记整理
          </el-button>
          <el-popconfirm title="确定删除？" @confirm="emit('delete', row.id)">
            <template #reference>
              <el-button link type="danger" size="small">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { FILE_CATEGORY_OPTIONS } from '../types/damsTypes'
import type { DamsFileResourceList } from '../types/damsTypes'

defineProps<{
  files: DamsFileResourceList[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'add'): void
  (e: 'edit', file: DamsFileResourceList): void
  (e: 'delete', id: number): void
  (e: 'organize', id: number): void
  (e: 'filter', filters: Record<string, unknown>): void
}>()

const filters = reactive<Record<string, unknown>>({
  category: undefined,
  organized: undefined,
  duplicate: undefined,
})
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.text-muted {
  color: var(--el-text-color-placeholder);
}
</style>
