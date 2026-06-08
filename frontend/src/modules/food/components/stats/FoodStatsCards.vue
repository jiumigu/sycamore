<template>
  <el-row :gutter="16" class="stats-row">
    <el-col :span="4">
      <el-card class="stat-card" shadow="never">
        <div class="stat-content">
          <div class="stat-icon" style="background: #FEF3C7"><span class="icon-text">🍽️</span></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_records }}</div>
            <div class="stat-label">总记录</div>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="5">
      <el-card class="stat-card" shadow="never">
        <div class="stat-content">
          <div class="stat-icon" style="background: #DBEAFE"><span class="icon-text">🏙️</span></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_cities }}</div>
            <div class="stat-label">到访城市</div>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="5">
      <el-card class="stat-card" shadow="never">
        <div class="stat-content">
          <div class="stat-icon" style="background: #D1FAE5"><span class="icon-text">⭐</span></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.avg_rating.toFixed(1) }}</div>
            <div class="stat-label">平均评分</div>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="5">
      <el-card class="stat-card" shadow="never">
        <div class="stat-content">
          <div class="stat-icon" style="background: #FCE7F3"><span class="icon-text">🔥</span></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.want_visit_again_count }}</div>
            <div class="stat-label">最想再去</div>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="5">
      <el-card class="stat-card" shadow="never">
        <div class="stat-content">
          <div class="stat-icon" style="background: #FEF3C7"><span class="icon-text">📅</span></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.this_month_count }}</div>
            <div class="stat-label">本月新增</div>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import type { FoodStats } from '../../types/foodTypes'

defineProps<{
  stats: FoodStats
}>()
</script>

<style scoped lang="scss">
.stats-row { margin-bottom: 20px; }

.stat-card {
  border: 1px solid #E5E7EB;
  border-radius: 12px;

  :deep(.el-card__body) { padding: 16px; }

  .stat-content {
    display: flex;
    align-items: center;
    gap: 10px;

    .stat-icon {
      width: 40px;
      height: 40px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      flex-shrink: 0;
    }

    .stat-info {
      .stat-value { font-size: 20px; font-weight: 700; line-height: 1; margin-bottom: 4px; color: #1F2937; }
      .stat-label { font-size: 12px; color: #6B7280; }
    }
  }
}
</style>
