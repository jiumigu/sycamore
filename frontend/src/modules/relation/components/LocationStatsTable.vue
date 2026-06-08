<template>
  <div class="location-stats-table">
    <el-table :data="locations" stripe style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="地点" min-width="140">
        <template #default="{ row }">
          <div class="location-name">📍 {{ row.name }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="total" label="人数" width="80" align="center" sortable />
      <el-table-column label="🟢 滋养型" min-width="100" align="center">
        <template #default="{ row }">
          <span class="count-green">{{ row.nourishing }}</span>
        </template>
      </el-table-column>
      <el-table-column label="⚪ 中性" min-width="80" align="center">
        <template #default="{ row }">
          <span class="count-gray">{{ row.neutral }}</span>
        </template>
      </el-table-column>
      <el-table-column label="🟡 消耗型" min-width="100" align="center">
        <template #default="{ row }">
          <span class="count-yellow">{{ row.draining }}</span>
        </template>
      </el-table-column>
      <el-table-column label="🔴 有害型" min-width="100" align="center">
        <template #default="{ row }">
          <span class="count-red">{{ row.toxic }}</span>
        </template>
      </el-table-column>
      <el-table-column label="滋养率" min-width="120" align="center" sortable>
        <template #default="{ row }">
          <el-tag :color="rateColor(row.nourishing_rate)" effect="dark" size="small">
            {{ row.nourishing_rate }}%
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import type { LocationStatsItem } from '../types/relationshipTypes'

defineProps<{
  locations: LocationStatsItem[]
  loading: boolean
}>()

function rateColor(rate: number): string {
  if (rate >= 60) return '#10B981'
  if (rate >= 40) return '#34D399'
  if (rate >= 20) return '#FBBF24'
  return '#F87171'
}
</script>

<style scoped lang="scss">
.location-stats-table {
  margin-top: 16px;

  .location-name { font-weight: 500; }

  .count-green { color: #10B981; font-weight: 600; }
  .count-gray { color: #9CA3AF; }
  .count-yellow { color: #F59E0B; font-weight: 600; }
  .count-red { color: #EF4444; font-weight: 600; }
}
</style>
