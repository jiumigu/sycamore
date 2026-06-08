<!-- src/shared/components/layout/AppLayout.vue -->
<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
    <!-- 隐私模式横幅 -->
    <div v-if="privacyStore.privacyMode" class="privacy-banner">
      <el-icon><Lock /></el-icon>
      <span>隐私模式已开启 — 金额、姓名、地点等敏感信息已脱敏</span>
    </div>

    <!-- 顶部导航 -->
    <LayoutHeader />

    <!-- 主体区域 -->
    <div class="layout-body">
      <!-- 侧边栏 -->
      <LayoutSidebar @collapse-change="handleSidebarCollapse" />

      <!-- 主内容区 -->
      <main class="layout-main">
        <div class="main-content">
          <router-view v-slot="{ Component, route }">
            <transition name="page-fade" mode="out-in">
              <keep-alive :include="keepAliveRoutes">
                <component :is="Component" :key="route.path" />
              </keep-alive>
            </transition>
          </router-view>
        </div>
      </main>
    </div>

    <!-- 底部栏 -->
    <LayoutFooter />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Lock } from '@element-plus/icons-vue'
import LayoutHeader from './LayoutHeader.vue'
import LayoutSidebar from './LayoutSidebar.vue'
import LayoutFooter from './LayoutFooter.vue'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'

const route = useRoute()

const privacyStore = usePrivacyStore()

onMounted(() => {
  privacyStore.fetchProfile()
})

// ============================================
// 侧边栏折叠状态
// ============================================
const isSidebarCollapsed = ref(false)

const handleSidebarCollapse = (collapsed: boolean) => {
  isSidebarCollapsed.value = collapsed
}

// ============================================
// 页面缓存策略
// ============================================
const keepAliveRoutes = computed(() => {
  return route.matched
    .filter(r => r.meta?.keepAlive && r.name)
    .map(r => r.name as string)
})
</script>

<style scoped lang="scss">
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 100vh;
  overflow: hidden;
  background: var(--lm-bg-primary);
}

// ============================================
// 隐私模式横幅
// ============================================
.privacy-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px 16px;
  background: var(--lm-primary-color, #409eff);
  color: #fff;
  font-size: 13px;
  flex-shrink: 0;

  .el-icon {
    font-size: 16px;
  }
}

// ============================================
// 主体区域（Header 以下、Footer 以上）
// ============================================
.layout-body {
  display: flex;
  flex: 1;
  min-height: 0; // flex 子元素允许收缩
  overflow: hidden;
}

// ============================================
// 主内容区
// ============================================
.layout-main {
  flex: 1;
  min-width: 0; // 防止内容溢出
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--lm-bg-secondary);
  transition: margin-left 0.3s ease;

  .main-content {
    min-height: 100%;
    padding: 24px;
  }
}

// ============================================
// 页面切换动画
// ============================================
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>