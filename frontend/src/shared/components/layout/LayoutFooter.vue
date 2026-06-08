<!-- src/shared/components/layout/LayoutFooter.vue -->
<template>
  <footer class="layout-footer">
    <div class="footer-content">

      <!-- 左侧：系统信息 -->
      <div class="footer-left">
        <div class="system-info">
          <span class="system-name">Sycamore</span>
          <span class="system-version">v3.0.0</span>
        </div>

      </div>

      <!-- 中部：快捷操作 -->
      <div class="footer-center">
        <div class="quick-links">
          <a href="#" class="footer-link" @click.prevent="handleBackup">
            <el-icon><CopyDocument /></el-icon>
            <span>数据备份</span>
          </a>
        </div>
      </div>

      <!-- 右侧：状态与时间 -->
      <div class="footer-right">
        <!-- 同步状态 -->
        <el-tooltip :content="`最后同步：${lastSyncTime}`" placement="top">
          <span class="sync-status" :class="{ syncing: isSyncing }">
            <el-icon>
              <Loading v-if="isSyncing" class="spin" />
              <CircleCheck v-else />
            </el-icon>
          </span>
        </el-tooltip>

        <!-- 通知快览 -->
        <el-tooltip :content="`${notificationStore.unreadCount} 条未读消息`" placement="top">
          <span class="notification-quick" @click="openNotificationCenter">
            <el-icon><Bell /></el-icon>
            <span v-if="notificationStore.unreadCount > 0" class="badge">{{ notificationStore.unreadCount > 99 ? '99+' : notificationStore.unreadCount }}</span>
          </span>
        </el-tooltip>

        <!-- 当前时间 -->
        <div class="current-time">
          <span class="date">{{ currentDate }}</span>
          <span class="time">{{ currentTime }}</span>
        </div>
      </div>
    </div>

    <!-- 底部进度条（导出/备份时显示） -->
    <transition name="slide-up">
      <div v-if="showProgressBar" class="progress-overlay">
        <div class="progress-content">
          <el-icon v-if="!progressError" :class="{ spin: progressPercentage < 100 }">
            <Loading />
          </el-icon>
          <el-icon v-else class="error-icon"><WarningFilled /></el-icon>
          <span class="progress-text">{{ progressText }}</span>
          <el-progress
            :percentage="progressPercentage"
            :stroke-width="4"
            :show-text="false"
            :status="progressError ? 'exception' : undefined"
            class="progress-bar"
          />
          <el-button
            v-if="showCancelButton"
            type="text"
            size="small"
            @click="cancelProgress"
          >
            取消
          </el-button>
        </div>
      </div>
    </transition>
  </footer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  CopyDocument,
  Loading, CircleCheck, Bell,
  WarningFilled,
} from '@element-plus/icons-vue'
import { backupDatabase } from '@/shared/api/coreApi'
import { useNotificationStore } from '@/core/notifications/stores/notificationStore'

const notificationStore = useNotificationStore()

// ============================================
// 响应式数据
// ============================================

const currentTime = ref('')
const isSyncing = ref(false)
const lastSyncTime = ref('10分钟前')

// 进度条
const showProgressBar = ref(false)
const progressText = ref('')
const progressPercentage = ref(0)
const progressError = ref(false)
const showCancelButton = ref(false)

// ============================================
// 计算属性
// ============================================

const currentDate = computed(() => {
  return new Date().toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
})

// ============================================
// 方法
// ============================================

const updateCurrentTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// 进度条通用逻辑
const runProgress = (text: string, onComplete?: () => void) => {
  showProgressBar.value = true
  progressText.value = text
  progressPercentage.value = 0
  progressError.value = false
  showCancelButton.value = true

  const interval = setInterval(() => {
    if (progressPercentage.value < 100) {
      progressPercentage.value += Math.random() * 15 + 5
      if (progressPercentage.value > 100) progressPercentage.value = 100
    } else {
      clearInterval(interval)
      onComplete?.()
      setTimeout(() => {
        showProgressBar.value = false
      }, 1200)
    }
  }, 300)

  return interval
}

const handleBackup = async () => {
  showProgressBar.value = true
  progressText.value = '正在备份数据库...'
  progressPercentage.value = 30
  progressError.value = false

  try {
    const res = await backupDatabase()
    progressPercentage.value = 100
    progressText.value = `备份完成：${res.data.filename}`
    setTimeout(() => { showProgressBar.value = false }, 2000)
  } catch {
    progressError.value = true
    progressText.value = '备份失败，请检查数据库连接'
  }
}

const cancelProgress = () => {
  showProgressBar.value = false
  progressPercentage.value = 0
  progressError.value = false
  isSyncing.value = false
}

const openNotificationCenter = () => {
  window.dispatchEvent(new CustomEvent('open-notification-center'))
}

// ============================================
// 生命周期
// ============================================

let timer: ReturnType<typeof setInterval>

onMounted(() => {
  updateCurrentTime()
  notificationStore.fetchUnreadCount()
  timer = setInterval(updateCurrentTime, 1000)
})

onUnmounted(() => {
  clearInterval(timer)
})
</script>

<style scoped lang="scss">
.layout-footer {
  height: 48px;
  background: var(--lm-bg-primary);
  border-top: 1px solid var(--lm-border-color);
  position: relative;
  z-index: 10;

  .footer-content {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
  }

  // ========== 左侧 ==========
  .footer-left {
    display: flex;
    align-items: center;
    gap: 16px;

    .system-info {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;

      .system-name {
        font-weight: 600;
        color: var(--lm-text-primary);
        letter-spacing: 0.5px;
      }

      .system-version {
        background: var(--lm-bg-secondary);
        padding: 1px 6px;
        border-radius: 10px;
        font-size: 11px;
        color: var(--lm-text-secondary);
      }
    }
  }

  // ========== 中部 ==========
  .footer-center {
    .quick-links {
      display: flex;
      gap: 20px;

      .footer-link {
        display: flex;
        align-items: center;
        gap: 4px;
        text-decoration: none;
        font-size: 12px;
        color: var(--lm-text-secondary);
        transition: color 0.2s;

        &:hover {
          color: var(--lm-primary-color);
        }

        .el-icon {
          font-size: 14px;
        }
      }
    }
  }

  // ========== 右侧 ==========
  .footer-right {
    display: flex;
    align-items: center;
    gap: 16px;

    .sync-status {
      font-size: 14px;
      color: #52c41a;
      cursor: default;

      &.syncing {
        color: var(--lm-primary-color);
      }
    }

    .notification-quick {
      position: relative;
      cursor: pointer;
      font-size: 16px;
      color: var(--lm-text-secondary);
      transition: color 0.2s;

      &:hover {
        color: var(--lm-primary-color);
      }

      .badge {
        position: absolute;
        top: -6px;
        right: -8px;
        background: #f44336;
        color: #fff;
        font-size: 10px;
        padding: 1px 5px;
        border-radius: 10px;
        line-height: 1.2;
        min-width: 16px;
        text-align: center;
      }
    }

    .current-time {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--lm-text-secondary);
      font-variant-numeric: tabular-nums;

      .time {
        color: var(--lm-text-primary);
        font-weight: 500;
        font-size: 14px;
        letter-spacing: 0.5px;
      }
    }
  }

  // ========== 进度条覆盖层 ==========
  .progress-overlay {
    position: absolute;
    bottom: 100%;
    left: 0;
    right: 0;
    height: 36px;
    background: var(--lm-bg-primary);
    border-top: 1px solid var(--lm-border-color);
    display: flex;
    align-items: center;
    justify-content: center;

    .progress-content {
      display: flex;
      align-items: center;
      gap: 10px;

      .el-icon {
        font-size: 14px;
        color: var(--lm-primary-color);
      }

      .error-icon {
        color: #f44336;
      }

      .progress-text {
        font-size: 13px;
        color: var(--lm-text-primary);
        white-space: nowrap;
      }

      .progress-bar {
        width: 150px;
      }
    }
  }
}

// ========== 动画 ==========
.spin {
  animation: spin 1.5s linear infinite;
}

@keyframes spin {
  0%   { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}

// ========== 响应式 ==========
@media (max-width: 900px) {
  .footer-center {
    display: none;
  }
}

@media (max-width: 600px) {
  .layout-footer {
    height: auto;
    padding: 8px 0;

    .footer-content {
      flex-direction: column;
      gap: 6px;
      padding: 0 12px;
    }

    .footer-left {
      .system-info { display: none; }
    }
  }
}
</style>