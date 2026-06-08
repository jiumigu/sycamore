<template>
  <div class="records-section">
    <div class="section-header">
      <span class="section-title">📋 历史记录</span>
      <el-button text type="primary" v-if="showAll" @click="$emit('toggle-show')">收起</el-button>
      <el-button text type="primary" v-else @click="$emit('toggle-show')">查看全部</el-button>
    </div>
    <div v-if="records.length === 0" class="empty">暂无记录</div>
    <div v-else class="records-list">
      <div v-for="r in displayRecords" :key="r.id" class="record-row">
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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MEASURE_TIME_OPTIONS } from '../../types/healthTypes'
import type { WeightRecord } from '../../types/healthTypes'

const props = defineProps<{
  records: WeightRecord[]
  showAll: boolean
}>()

defineEmits<{
  'toggle-show': []
  edit: [record: WeightRecord]
  delete: [id: number]
}>()

const displayRecords = computed(() => props.showAll ? props.records : props.records.slice(0, 5))

const measureTimeLabel = (val: string) => {
  const opt = MEASURE_TIME_OPTIONS.find(o => o.value === val)
  return opt?.label || val
}
</script>

<style scoped>
.records-section { background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; padding: 20px; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-title { font-size: 16px; font-weight: 600; color: #1F2937; }
.empty { text-align: center; padding: 32px; color: #9CA3AF; font-size: 14px; }
.records-list { display: flex; flex-direction: column; gap: 6px; }
.record-row { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 8px; background: #F9FAFB; font-size: 13px; flex-wrap: wrap; }
.record-date { font-size: 12px; color: #6B7280; min-width: 85px; }
.record-weight { color: #1F2937; min-width: 100px; }
.record-jin { font-size: 12px; color: #9CA3AF; }
.record-meta, .record-time, .record-notes { color: #6B7280; font-size: 12px; }
.record-notes { flex: 1; min-width: 100px; }
.record-actions { margin-left: auto; white-space: nowrap; }
</style>
