<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="780px"
    append-to-body
    @update:model-value="$emit('update:visible', $event)"
  >
    <div v-if="summary" class="daily-summary">{{ summary }}</div>
    <el-table :data="data" v-loading="loading" stripe size="small" max-height="420">
      <el-table-column
        v-for="col in columns"
        :key="col.prop"
        :label="col.label"
        :prop="col.prop"
        :width="col.width"
        :align="col.align || 'left'"
        :min-width="col.minWidth"
      >
        <template v-if="col.formatter" #default="{ row }">
          {{ col.formatter(row[col.prop], row) }}
        </template>
      </el-table-column>
      <template v-if="!data.length && !loading">
        <div class="empty-tip">该日暂无记录</div>
      </template>
    </el-table>
  </el-dialog>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  title: string
  data: any[]
  columns: Array<{ prop: string; label: string; width?: number; minWidth?: number; align?: 'left' | 'right' | 'center'; formatter?: (v: any, row: any) => string }>
  loading?: boolean
  summary?: string
}>()

defineEmits<{
  'update:visible': [boolean]
}>()
</script>

<style scoped>
.daily-summary {
  font-size: 13px;
  color: #4B5563;
  margin-bottom: 10px;
  padding: 6px 10px;
  background: #F3F4F6;
  border-radius: 6px;
}
.empty-tip {
  text-align: center;
  color: #9CA3AF;
  font-size: 13px;
  padding: 30px 0;
}
</style>
