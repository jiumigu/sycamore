<template>
  <div class="records-section">
    <div class="section-header">
      <span class="section-title">📋 历史记录</span>
      <span class="section-total" v-if="total > 0">共 {{ total }} 条</span>
    </div>

    <!-- 🔴 三种状态要分开说：加载中 / 真没有 / 有数据。
         用 `records.length === 0` 一律画「暂无记录」⇒ 翻页那一下会闪一句假话。 -->
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="records.length === 0" class="empty">暂无记录</div>
    <div v-else class="records-list">
      <div v-for="r in records" :key="r.id" class="record-row">
        <div class="record-date">{{ r.record_date }}</div>
        <div class="record-weight">
          <strong>{{ r.weight_jin }}</strong> 斤
        </div>
        <div class="record-meta" v-if="r.body_fat">体脂 {{ r.body_fat }}%</div>
        <div class="record-time" v-if="r.measure_time">{{ measureTimeLabel(r.measure_time) }}</div>
        <div class="record-notes" v-if="r.notes">{{ r.notes }}</div>
        <div class="record-actions">
          <el-button text size="small" @click="$emit('edit', r)">编辑</el-button>
          <el-popconfirm title="确定删除？" @confirm="$emit('delete', r.id)">
            <template #reference>
              <el-button text size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </div>

    <!-- 分页由后端给：`records` 只有当前页，`total` 是过滤器之外的全量条数。
         ⚠️ layout 里**不放 `total`** —— 卡头已经有「共 N 条」，两处都写就是同一事实两把尺子 -->
    <el-pagination
      v-if="total > 0"
      class="records-pager"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="pageSizes"
      :total="total"
      layout="sizes, prev, pager, next"
      background
      small
      @current-change="onPageChange"
      @size-change="onSizeChange"
    />
  </div>
</template>

<script setup lang="ts">
import { MEASURE_TIME_OPTIONS } from '../../types/healthTypes'
import type { WeightRecord } from '../../types/healthTypes'

defineProps<{
  records: WeightRecord[]
  /** 全量条数（后端 `count`）—— 不是 `records.length` */
  total: number
  page: number
  pageSize: number
  pageSizes: number[]
  loading?: boolean
}>()

const emit = defineEmits<{
  'page-change': [page: number]
  'size-change': [size: number]
  edit: [record: WeightRecord]
  delete: [id: number]
}>()

const onPageChange = (page: number) => emit('page-change', page)
// el-pagination 的 size-change 只给新条数；父组件收到后回第 1 页重取
const onSizeChange = (size: number) => emit('size-change', size)

const measureTimeLabel = (val: string) => {
  const opt = MEASURE_TIME_OPTIONS.find(o => o.value === val)
  return opt?.label || val
}
</script>

<style scoped>
.records-section { background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; padding: 20px; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-title { font-size: 16px; font-weight: 600; color: #1F2937; }
.section-total { font-size: 12px; color: #9CA3AF; }
.empty { text-align: center; padding: 32px; color: #9CA3AF; font-size: 14px; }
.records-list { display: flex; flex-direction: column; gap: 6px; }
.record-row { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 8px; background: #F9FAFB; font-size: 13px; flex-wrap: wrap; }
.record-date { font-size: 12px; color: #6B7280; min-width: 85px; }
.record-weight { color: #1F2937; min-width: 100px; }
.record-jin { font-size: 12px; color: #9CA3AF; }
.record-meta, .record-time, .record-notes { color: #6B7280; font-size: 12px; }
.record-notes { flex: 1; min-width: 100px; }
.record-actions { margin-left: auto; white-space: nowrap; }
.records-pager { margin-top: 16px; justify-content: flex-end; }
.records-pager :deep(.el-pagination__total) { font-size: 12px; color: #9CA3AF; }
</style>
