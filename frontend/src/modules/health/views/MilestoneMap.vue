<template>
  <div class="milestone-map">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <el-button text @click="$router.back()">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <h1 class="page-title">🗺️ 生命步数里程碑地图</h1>
      </div>
      <div class="header-info">
        {{ store.milestones?.total_steps ? formatNumber(store.milestones.total_steps) + ' / ' + formatNumber(TARGET_STEPS) + ' 步' : '' }}
      </div>
    </div>

    <!-- 总进度 -->
    <el-card class="section-card" v-if="store.summary">
      <div class="overall-progress">
        <div class="progress-stat">
          <span class="stat-num">{{ store.summary.completed_milestones }}</span>
          <span class="stat-label">已达成</span>
        </div>
        <div class="progress-stat current-stat">
          <span class="stat-num">{{ store.summary.total_milestones }}</span>
          <span class="stat-label">总里程碑</span>
        </div>
        <div class="progress-stat">
          <span class="stat-num">{{ store.summary.progress_percent }}%</span>
          <span class="stat-label">总体进度</span>
        </div>
        <div class="progress-stat">
          <span class="stat-num">{{ formatNumber(store.summary.next_milestone_distance) }}</span>
          <span class="stat-label">距下一里程碑</span>
        </div>
      </div>
    </el-card>

    <!-- 里程碑网格 5×10 -->
    <el-card class="section-card">
      <template #header>
        <div class="section-header">
          <span>50个里程碑 · 每200万步一个里程碑</span>
          <div class="legend">
            <span class="legend-item"><span class="dot completed"></span> 已完成</span>
            <span class="legend-item"><span class="dot current"></span> 当前</span>
            <span class="legend-item"><span class="dot pending"></span> 未完成</span>
          </div>
        </div>
      </template>

      <div class="milestone-grid">
        <div
          v-for="m in milestoneList"
          :key="m.number"
          class="milestone-cell"
          :class="{ completed: m.is_completed, current: m.is_current }"
          @click="selectMilestone(m)"
        >
          <div class="cell-icon">{{ m.is_completed ? '🏆' : m.is_current ? '🌟' : '📍' }}</div>
          <div class="cell-number">第{{ m.number }}个</div>
          <div class="cell-range">{{ formatNumber(m.start / 10000) }}w - {{ formatNumber(m.end / 10000) }}w</div>
          <div v-if="m.is_current && !m.is_completed" class="cell-progress">
            <div class="cell-progress-bar">
              <div class="cell-progress-fill" :style="{ width: Math.min(m.progress_percent || 0, 100) + '%' }"></div>
            </div>
            <div class="cell-progress-text">{{ m.progress_percent?.toFixed(1) }}%</div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 里程碑详情弹窗 -->
    <el-dialog v-model="detailVisible" title="里程碑详情" width="400px">
      <template v-if="selectedMilestone">
        <div class="detail-content">
          <div class="detail-icon">{{ selectedMilestone.is_completed ? '🏆' : selectedMilestone.is_current ? '🌟' : '📍' }}</div>
          <h2 class="detail-title">第{{ selectedMilestone.number }}个里程碑</h2>
          <div class="detail-range">
            {{ formatNumber(selectedMilestone.start / 10000) }}万步 →
            {{ formatNumber(selectedMilestone.end / 10000) }}万步
          </div>

          <el-divider />

          <div class="detail-info">
            <div class="info-row">
              <span class="info-label">状态</span>
              <span class="info-value">
                <el-tag v-if="selectedMilestone.is_completed" type="success" effect="dark">已完成</el-tag>
                <el-tag v-else-if="selectedMilestone.is_current" type="warning" effect="dark">进行中</el-tag>
                <el-tag v-else type="info" effect="plain">未开始</el-tag>
              </span>
            </div>

            <div v-if="selectedMilestone.is_completed && selectedMilestone.completed_date" class="info-row">
              <span class="info-label">达成日期</span>
              <span class="info-value">{{ selectedMilestone.completed_date }}</span>
            </div>

            <div v-if="selectedMilestone.is_completed && selectedMilestone.days_taken" class="info-row">
              <span class="info-label">耗时</span>
              <span class="info-value">{{ selectedMilestone.days_taken }} 天</span>
            </div>

            <div v-if="selectedMilestone.is_current && !selectedMilestone.is_completed" class="info-row">
              <span class="info-label">当前进度</span>
              <span class="info-value">{{ formatNumber(selectedMilestone.current_progress || 0) }} / {{ formatNumber(selectedMilestone.end - selectedMilestone.start) }} 步</span>
            </div>

            <div v-if="selectedMilestone.is_current && !selectedMilestone.is_completed" class="info-row">
              <span class="info-label">还需</span>
              <span class="info-value">{{ formatNumber((selectedMilestone.end - selectedMilestone.start) - (selectedMilestone.current_progress || 0)) }} 步</span>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useHealthStore } from '../stores/healthStore'
import { TARGET_STEPS } from '../types/healthTypes'
import type { MilestoneItem } from '../types/healthTypes'

const store = useHealthStore()

const milestoneList = computed(() => store.milestones?.milestones || [])
const detailVisible = ref(false)
const selectedMilestone = ref<MilestoneItem | null>(null)

function formatNumber(n: number | undefined | null): string {
  if (n === undefined || n === null) return '0'
  if (n >= 100000000) return (n / 100000000).toFixed(2) + '亿'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function selectMilestone(m: MilestoneItem) {
  selectedMilestone.value = m
  detailVisible.value = true
}

onMounted(async () => {
  if (!store.milestones) {
    await Promise.all([
      store.fetchSummary(),
      store.fetchMilestones(),
    ])
  }
})
</script>

<style scoped lang="scss">
.milestone-map {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    .header-left { display: flex; align-items: center; gap: 8px;
      .page-title { margin: 0; font-size: 22px; font-weight: 600; color: #1F2937; }
    }
    .header-info { font-size: 13px; color: #909399; }
  }

  .section-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px;
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
  }

  .overall-progress {
    display: flex; justify-content: space-around; padding: 10px 0;
    .progress-stat { text-align: center;
      .stat-num { display: block; font-size: 28px; font-weight: 700; color: #1F2937; }
      .stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
      &.current-stat .stat-num { color: #1890ff; }
    }
  }

  .section-header {
    display: flex; justify-content: space-between; align-items: center;
    .legend { display: flex; gap: 16px;
      .legend-item { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px;
        .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%;
          &.completed { background: #52c41a; }
          &.current { background: #fa8c16; box-shadow: 0 0 4px rgba(250,140,22,0.5); }
          &.pending { background: #d9d9d9; }
        }
      }
    }
  }

  .milestone-grid {
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: 8px;
    padding: 8px;

    .milestone-cell {
      border: 1px solid #e8e8e8;
      border-radius: 8px;
      padding: 8px 4px;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s;
      background: #fafafa;

      &.completed { background: #f6ffed; border-color: #b7eb8f;
        .cell-icon { font-size: 20px; }
        .cell-number { color: #52c41a; font-weight: 600; }
        .cell-range { color: #73d13d; }
      }
      &.current { background: #fffbe6; border-color: #ffe58f; border-width: 2px; box-shadow: 0 0 8px rgba(250,173,20,0.3);
        .cell-icon { font-size: 22px; }
        .cell-number { color: #fa8c16; font-weight: 600; }
        .cell-range { color: #faad14; }
      }
      &:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }

      .cell-icon { font-size: 18px; margin-bottom: 4px; }
      .cell-number { font-size: 12px; color: #606266; }
      .cell-range { font-size: 10px; color: #bfbfbf; margin-top: 2px; }

      .cell-progress { margin-top: 6px;
        .cell-progress-bar { height: 4px; background: #f0f0f0; border-radius: 2px; overflow: hidden;
          .cell-progress-fill { height: 100%; background: linear-gradient(90deg, #faad14, #fa8c16); border-radius: 2px; transition: width 0.5s; }
        }
        .cell-progress-text { font-size: 10px; color: #fa8c16; margin-top: 2px; }
      }
    }
  }
}

.detail-content {
  text-align: center;
  .detail-icon { font-size: 48px; margin-bottom: 8px; }
  .detail-title { font-size: 20px; font-weight: 600; color: #1F2937; margin: 0 0 4px; }
  .detail-range { font-size: 14px; color: #909399; }

  .detail-info { text-align: left;
    .info-row { display: flex; justify-content: space-between; padding: 8px 0; align-items: center;
      .info-label { font-size: 13px; color: #909399; }
      .info-value { font-size: 14px; color: #1F2937; font-weight: 500; }
    }
  }
}
</style>
