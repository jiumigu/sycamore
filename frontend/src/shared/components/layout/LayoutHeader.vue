<!-- src/shared/components/layout/LayoutHeader.vue -->
<template>
  <header class="layout-header">
    <!-- 左侧：Logo 和系统名称 -->
    <div class="header-left">
      <div class="logo-container" @click="goToDashboard">
        <el-icon class="logo-icon"><Platform /></el-icon>
        <span class="system-name">Sycamore</span>
      </div>

      <!-- 面包屑导航 -->
      <el-breadcrumb separator="/" class="breadcrumb">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
          {{ item.meta?.title || item.name }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <!-- 中部：全局搜索和快捷操作 -->
    <div class="header-center">
      <SearchBar />

      <!-- 快捷记录按钮 -->
      <el-tooltip content="快速记录" placement="bottom">
        <el-button type="primary" circle class="quick-add-btn" @click="showQuickPanel = true">
          <el-icon><Plus /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <!-- 右侧：时间维度、主题、通知、用户 -->
    <div class="header-right">
      <!-- 时间维度切换 -->
      <el-dropdown @command="handleTimeDimensionChange">
        <span class="time-dimension-selector">
          <el-icon><Clock /></el-icon>
          <span>{{ currentTimeDimensionLabel }}</span>
          <el-icon class="arrow"><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="day">
              <el-icon><Sunrise /></el-icon>日视图
            </el-dropdown-item>
            <el-dropdown-item command="week">
              <el-icon><Calendar /></el-icon>周视图
            </el-dropdown-item>
            <el-dropdown-item command="month">
              <el-icon><Calendar /></el-icon>月视图
            </el-dropdown-item>
            <el-dropdown-item command="year">
              <el-icon><DataAnalysis /></el-icon>年视图
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <!-- 主题切换 -->
      <el-tooltip :content="theme === 'light' ? '深色模式' : '浅色模式'" placement="bottom">
        <el-button type="text" class="theme-switch" @click="toggleTheme">
          <el-icon><Moon v-if="theme === 'light'" /><Sunny v-else /></el-icon>
        </el-button>
      </el-tooltip>

      <!-- 隐私模式切换 -->
      <el-tooltip :content="privacyStore.privacyMode ? '关闭脱敏' : '脱敏模式'" placement="bottom">
        <el-button type="text" class="privacy-switch" @click="privacyStore.togglePrivacyMode()">
          <el-icon :class="{ active: privacyStore.privacyMode }"><Lock v-if="privacyStore.privacyMode" /><Unlock v-else /></el-icon>
        </el-button>
      </el-tooltip>

      <!-- 通知中心 -->
      <el-popover
        placement="bottom-end"
        :width="380"
        trigger="click"
        popper-class="notification-popover"
      >
        <template #reference>
          <div class="notification-bell">
            <el-badge :value="notificationStore.unreadCount" :max="99" :hidden="notificationStore.unreadCount === 0">
              <el-icon><Bell /></el-icon>
            </el-badge>
          </div>
        </template>

        <NotificationCenter @notification-click="handleNotificationClick" />
      </el-popover>

      <!-- 用户菜单 -->
      <el-dropdown @command="handleUserCommand">
        <div class="user-avatar">
          <el-avatar :size="32">
            {{ userDisplayName?.charAt(0) || 'S' }}
          </el-avatar>
          <span class="user-name">{{ userDisplayName || 'Sycamore' }}</span>
          <el-icon class="arrow"><ArrowDown /></el-icon>
        </div>

        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon>个人偏好
            </el-dropdown-item>
            <el-dropdown-item command="settings">
              <el-icon><Setting /></el-icon>系统设置
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon>退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <QuickRecordPanel v-model:visible="showQuickPanel" />
  </header>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Platform, Plus,
  Clock, ArrowDown, Sunrise, Calendar,
  DataAnalysis, Moon, Sunny, Bell,
  Lock, Unlock,
  User, Setting, SwitchButton,
} from '@element-plus/icons-vue'
import NotificationCenter from './NotificationCenter.vue'
import QuickRecordPanel from '@/shared/components/QuickRecordPanel.vue'
import SearchBar from '@/shared/components/SearchBar.vue'

const route = useRoute()
const router = useRouter()

// ============================================
// Store（按新架构路径）
// ============================================
import { useNotificationStore } from '@/core/notifications/stores/notificationStore'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'

const notificationStore = useNotificationStore()
const privacyStore = usePrivacyStore()

// 过渡期模拟
const theme = ref<'light' | 'dark'>('light')
const userDisplayName = ref('Sycamore')
const toggleTheme = () => {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
}

// ============================================
// 响应式数据
// ============================================
const currentTimeDimension = ref<'day' | 'week' | 'month' | 'year'>('week')
const showQuickPanel = ref(false)

// ============================================
// 计算属性
// ============================================
const breadcrumbs = computed(() => {
  const matched = route.matched.filter(record => record.meta?.title)
  return matched.slice(1)
})

const currentTimeDimensionLabel = computed(() => {
  const labels: Record<string, string> = {
    day: '日视图',
    week: '周视图',
    month: '月视图',
    year: '年视图',
  }
  return labels[currentTimeDimension.value] || '周视图'
})

// ============================================
// 方法
// ============================================
const goToDashboard = () => {
  router.push('/dashboard')
}

const handleTimeDimensionChange = (command: 'day' | 'week' | 'month' | 'year') => {
  currentTimeDimension.value = command
  window.dispatchEvent(new CustomEvent('time-dimension-change', { detail: { dimension: command } }))
}

const handleNotificationClick = (notification: any) => {
  if (notification.action_url) {
    router.push(notification.action_url)
  }
}

const handleUserCommand = (command: string) => {
  switch (command) {
    case 'profile':
      router.push('/settings/profile')
      break
    case 'settings':
      router.push('/settings/system')
      break
    case 'logout':
      // authStore.logout()
      router.push('/login')
      break
  }
}

onMounted(() => {
  notificationStore.fetchUnreadCount()
})
</script>

<style scoped lang="scss">
.layout-header {
  height: 56px;
  background: var(--lm-bg-primary);
  border-bottom: 1px solid var(--lm-border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  position: sticky;
  top: 0;
  z-index: 1000;
  gap: 16px;

  // ========== 左侧 ==========
  .header-left {
    display: flex;
    align-items: center;
    gap: 20px;
    flex-shrink: 0;

    .logo-container {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      user-select: none;

      .logo-icon {
        font-size: 22px;
        color: var(--lm-primary-color);
      }

      .system-name {
        font-size: 17px;
        font-weight: 600;
        color: var(--lm-text-primary);
        letter-spacing: 0.3px;
      }
    }

    .breadcrumb {
      :deep(.el-breadcrumb__inner) {
        color: var(--lm-text-secondary);
        font-size: 13px;
      }
    }
  }

  // ========== 中部 ==========
  .header-center {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    max-width: 520px;

    .quick-add-btn {
      width: 38px;
      height: 38px;
      font-size: 18px;
      flex-shrink: 0;
      transition: transform 0.2s;

      &:hover {
        transform: scale(1.05);
      }
    }
  }

  // ========== 右侧 ==========
  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0;

    // 时间维度切换
    .time-dimension-selector {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 16px;
      background: var(--lm-bg-secondary);
      cursor: pointer;
      user-select: none;
      transition: background 0.2s;
      font-size: 13px;
      color: var(--lm-text-primary);

      &:hover {
        background: var(--lm-bg-card);
      }

      .arrow {
        font-size: 12px;
        color: var(--lm-text-secondary);
      }
    }

    // 主题切换
    .theme-switch {
      font-size: 18px;
      color: var(--lm-text-secondary);
      padding: 4px;

      &:hover {
        color: var(--lm-primary-color);
      }
    }

    // 隐私模式切换
    .privacy-switch {
      font-size: 18px;
      color: var(--lm-text-secondary);
      padding: 4px;

      &:hover {
        color: var(--lm-primary-color);
      }

      .active {
        color: var(--lm-primary-color);
      }
    }

    // 通知铃铛
    .notification-bell {
      cursor: pointer;
      padding: 6px;
      border-radius: 8px;
      transition: background 0.2s;

      &:hover {
        background: var(--lm-bg-secondary);
      }

      .el-icon {
        font-size: 20px;
        color: var(--lm-text-secondary);
      }

      :deep(.el-badge__content) {
        border: 2px solid var(--lm-bg-primary);
      }
    }

    // 用户头像区
    .user-avatar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 3px 8px 3px 3px;
      border-radius: 20px;
      cursor: pointer;
      user-select: none;
      transition: background 0.2s;

      &:hover {
        background: var(--lm-bg-secondary);
      }

      .user-name {
        font-size: 13px;
        color: var(--lm-text-primary);
        max-width: 80px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .arrow {
        font-size: 12px;
        color: var(--lm-text-secondary);
      }
    }
  }
}
</style>

