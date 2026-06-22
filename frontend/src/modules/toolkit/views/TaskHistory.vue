<template>
  <div class="task-history">
    <div class="back-bar">
      <el-button text @click="$router.push('/toolkit')">
        <el-icon><ArrowLeft /></el-icon> 返回工具集
      </el-button>
    </div>

    <div class="page-header">
      <h1 class="page-title">📋 执行历史</h1>
      <div class="header-actions">
        <el-select v-model="filterTool" placeholder="按工具筛选" clearable size="default" style="width:140px" @change="refresh">
          <el-option v-for="t in store.tools" :key="t.tool_key" :label="t.name" :value="t.tool_key" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="按状态筛选" clearable size="default" style="width:120px" @change="refresh">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="执行中" value="running" />
        </el-select>
        <el-button @click="refresh"><el-icon><Refresh /></el-icon> 刷新</el-button>
      </div>
    </div>

    <el-card class="section-card">
      <div v-loading="loading">
        <div v-if="records.length === 0" class="empty-state">
          <el-empty description="暂无执行记录" />
        </div>

        <div v-else class="history-list">
          <div v-for="item in records" :key="item.id" class="history-item">
            <div class="item-icon">{{ item.tool_icon }}</div>
            <div class="item-info">
              <div class="item-tool">{{ item.tool_name }}</div>
              <div class="item-time">{{ item.created_at }}</div>
            </div>
            <div class="item-status">
              <el-tag :type="statusType(item.status)" size="small">
                {{ statusLabel(item.status) }}
              </el-tag>
              <div v-if="item.execution_time_ms" class="item-duration">{{ item.execution_time_ms }}ms</div>
            </div>
            <div class="item-actions">
              <el-button v-if="item.status === 'failed' && item.error_message" text size="small" @click="showError(item)">
                详情
              </el-button>
              <el-button v-if="item.status === 'success' && item.output_file" text size="small" @click="downloadFile(item.output_file!)">
                下载
              </el-button>
            </div>
          </div>
        </div>

        <el-pagination
          v-if="store.historyTotal > pageSize"
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="store.historyTotal"
          layout="prev, pager, next"
          small
          class="pagination"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 错误详情弹窗 -->
    <el-dialog v-model="errorDialogVisible" title="错误详情" width="480px">
      <div class="error-detail">{{ errorDetail }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { useToolkitStore } from '../stores/toolkitStore'
import type { ExecutionRecord, ExecutionStatus } from '../types/toolkitTypes'
import { STATUS_CONFIG } from '../types/toolkitTypes'

const store = useToolkitStore()
const filterTool = ref('')
const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = 20
const loading = ref(false)
const errorDialogVisible = ref(false)
const errorDetail = ref('')

const records = computed(() => store.history)

function statusType(status: string): any {
  return STATUS_CONFIG[status as ExecutionStatus]?.type || 'info'
}

function statusLabel(status: string): string {
  return STATUS_CONFIG[status as ExecutionStatus]?.label || status
}

function showError(item: ExecutionRecord) {
  errorDetail.value = item.error_message || '未知错误'
  errorDialogVisible.value = true
}

function downloadFile(path: string) {
  const a = document.createElement('a')
  a.href = path
  a.download = path.split('/').pop() || 'download'
  a.click()
}

async function refresh() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: currentPage.value, page_size: pageSize }
    if (filterTool.value) params.tool_key = filterTool.value
    if (filterStatus.value) params.status = filterStatus.value
    await store.fetchHistory(params)
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  currentPage.value = p
  refresh()
}

onMounted(async () => {
  [await store.fetchTools()]
  await refresh()
})
</script>

<style scoped lang="scss">
.task-history {
  padding: 20px; background: #F5F7FA; min-height: 100vh;

  .back-bar { margin-bottom: 16px; }

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
    .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    .header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  }

  .section-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    .pagination { margin-top: 16px; justify-content: flex-end; }
  }

  .empty-state { padding: 40px 0; }

  .history-list {
    .history-item {
      display: flex; align-items: center; gap: 16px; padding: 14px 4px;
      border-bottom: 1px solid #f5f5f5;
      &:last-child { border-bottom: none; }

      .item-icon { font-size: 28px; width: 40px; text-align: center; }
      .item-info { flex: 1;
        .item-tool { font-size: 14px; font-weight: 500; color: #1F2937; }
        .item-time { font-size: 12px; color: #9CA3AF; margin-top: 2px; }
      }
      .item-status { text-align: center;
        .item-duration { font-size: 11px; color: #9CA3AF; margin-top: 4px; }
      }
      .item-actions { display: flex; gap: 4px; flex-shrink: 0; }
    }
  }

  .error-detail {
    font-size: 14px; color: #EF4444; line-height: 1.6;
    background: #fef2f2; padding: 16px; border-radius: 8px;
  }
}
</style>
