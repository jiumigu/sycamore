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

      <!-- 实时计时（在任何页面都能开始/结束一段计时） -->
      <TimerWidget />
    </div>

    <!-- 右侧：自我运转入口、主题、通知、用户 -->
    <div class="header-right">
      <!-- 自我运转入口（v3.63.23）
           🔴 这个位置原来叫「日视图 / 周视图 / 月视图 / 年视图」，是个**空壳**：
              点一下只改自己的标签，然后 `dispatchEvent('time-dimension-change')` ——
              全仓**没有一个监听者**，点什么都不会发生（用户原话「这个框架中的视图没有真正用起来」）。
           现在它真的能用：点哪项就进自我运转的那一页，侧边栏因此不再列那四项
           （`menuConfig.ts` 里已撤）—— 一个入口，四处直达。
           ⚠️ 不在自我运转里时显示模块名「自我运转」；在里面时显示当前页名，
              免得人以为「我点的是周状态，怎么标签还写着自我运转」。 -->
      <el-dropdown trigger="click" @command="goSelfRun">
        <span class="selfrun-entry" :class="{ 'is-in': isInSelfRun }">
          <el-icon><Odometer /></el-icon>
          <span>{{ selfRunEntryLabel }}</span>
          <el-icon class="arrow"><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="e in SELF_RUN_ENTRIES" :key="e.key" :command="e.key"
            >
              <el-icon><component :is="e.icon" /></el-icon>{{ e.label }}
              <span v-if="e.key === currentSelfRunEntry" class="entry-cur">· 当前</span>
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
import { ref, computed, onMounted, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Platform, Plus,
  ArrowDown, Odometer,
  // 自我运转四个入口的图标（与原来的侧边栏图标同义）
  // ⚠️ 现在是五个入口（v3.64.19 加了「阶段账本」，图标 `DataAnalysis`）
  EditPen, Calendar, Histogram, Clock, DataAnalysis,
  Moon, Sunny, Bell,
  Lock, Unlock,
  User, Setting, SwitchButton,
} from '@element-plus/icons-vue'
import NotificationCenter from './NotificationCenter.vue'
import QuickRecordPanel from '@/shared/components/QuickRecordPanel.vue'
import SearchBar from '@/shared/components/SearchBar.vue'
import TimerWidget from '@/shared/components/TimerWidget.vue'

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
const showQuickPanel = ref(false)

/**
 * 自我运转的四个入口 —— **页头就是它唯一的常驻入口**（v3.63.23 起侧边栏不再列）。
 *
 * 🔴 这里只做「路由名」映射，**不另存 current 状态**：
 *    当前在哪一页由 `route.name` 决定（与 `SelfRunHub` 的页签同源）。
 *    另存一个 ref 的话，从别处点进来 / 浏览器后退都会让它和页签分家。
 * ⚠️ 「阶段总结」不在这里：它是模块内的深层页，只从页内页签进
 *    （四次点开里有几次会看总结？占一个常驻入口等于让低频页抢高频位）。
 */
const SELF_RUN_ENTRIES: { key: string; route: string; label: string; icon: Component }[] = [
  { key: 'setup', route: 'selfrun-setup', label: '制定配置', icon: EditPen },
  { key: 'week', route: 'selfrun-week', label: '本周状态', icon: Calendar },
  { key: 'month', route: 'selfrun-month', label: '本月状态', icon: Histogram },
  { key: 'review', route: 'selfrun-review', label: '历史复盘', icon: Clock },
  // v3.64.19：「一段长路」的账本（钱 / 时间 / 作品 / 它下面的小阶段）。
  // 🔴 路由是 `stage/:id?` —— **这里刻意不带 id**（页头拿不到「哪一段路」），
  //    由页面自己取「正在跑的那个长阶段」。带一个猜出来的 id 只会更容易开到错的阶段。
  { key: 'stage', route: 'selfrun-stage', label: '阶段账本', icon: DataAnalysis },
]

/**
 * 路由名 → 入口 key。
 * ⚠️ 「制定配置」的三个页内子页面（模板库 / 按期修订 / 变更留痕）都归到 `setup` ——
 *    它们不是并列的入口，页头这时该说「制定配置」，而不是跳到子页标题上。
 */
const SELF_RUN_ENTRY_OF_ROUTE: Record<string, string> = {
  'selfrun-setup': 'setup',
  'selfrun-setup-templates': 'setup',
  'selfrun-setup-targets': 'setup',
  'selfrun-setup-logs': 'setup',
  'selfrun-week': 'week',
  'selfrun-month': 'month',
  'selfrun-review': 'review',
  'selfrun-summary': 'review',   // 总结是「历史复盘」旁边的深层页，归在同一个入口下
  'selfrun-stage': 'stage',
}

// ============================================
// 计算属性
// ============================================
const breadcrumbs = computed(() => {
  const matched = route.matched.filter(record => record.meta?.title)
  return matched.slice(1)
})

const currentSelfRunEntry = computed(() => SELF_RUN_ENTRY_OF_ROUTE[String(route.name ?? '')] ?? '')
const isInSelfRun = computed(() => !!currentSelfRunEntry.value)

/** 在里面显示当前页名，在外面显示模块名 —— 否则读不出「这个按钮现在指向哪」 */
const selfRunEntryLabel = computed(() => {
  const cur = SELF_RUN_ENTRIES.find(e => e.key === currentSelfRunEntry.value)
  return cur ? cur.label : '自我运转'
})

// ============================================
// 方法
// ============================================
const goToDashboard = () => {
  router.push('/dashboard')
}

const goSelfRun = (key: string) => {
  const entry = SELF_RUN_ENTRIES.find(e => e.key === key)
  if (entry) router.push({ name: entry.route })
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
    // 520 → 620：右侧多了常驻的计时入口（窄屏下仍会先压缩搜索框）
    max-width: 620px;

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

    // 自我运转入口
    .selfrun-entry {
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

      // 在自我运转里时给一点「这里是当前模块」的提示（不抢眼，只是不再是一片灰）
      &.is-in {
        color: var(--lm-primary-color);
      }

      .arrow {
        font-size: 12px;
        color: var(--lm-text-secondary);
      }
    }

    // 🔴 注意：下拉菜单里那一项**不能**写在这层嵌套里 —— 菜单被 teleport 到 body，
    //    `.header-right .entry-cur` 的祖先链在真实 DOM 里断了，规则一条都不会命中
    //    （不报错，只是「当前」两个字永远没样式）。它写在下方的**顶层**规则里。

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

/* 自我运转下拉里「· 当前」的标记。
   🔴 必须是**顶层**选择器：`el-dropdown-menu` 被 teleport 到 body，
      写成 `.header-right .entry-cur` 的话祖先链在真实 DOM 里不存在 ⇒ 一条都不命中。
   ⚠️ 内容仍是在本组件模板里编译的，带 scope id ⇒ 顶层 scoped 规则能命中。 */
.entry-cur {
  margin-left: 6px;
  font-size: 12px;
  color: var(--el-color-primary);
}
</style>

