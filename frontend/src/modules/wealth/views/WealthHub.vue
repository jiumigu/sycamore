<template>
  <div class="wealth-hub">
    <!-- 统一导航标签 -->
    <div class="wealth-hub__tabs-wrapper">
      <div class="wealth-hub__tabs">
        <div
          v-for="tab in tabs"
          :key="tab.name"
          class="wealth-hub__tab"
          :class="{ active: activeTab === tab.name }"
          @click="switchTab(tab.name)"
        >
          <el-icon class="wealth-hub__tab-icon">
            <component :is="tab.icon" />
          </el-icon>
          <span>{{ tab.label }}</span>
        </div>
      </div>
    </div>

    <!-- 子模块内容区 -->
    <div class="wealth-hub__content">
      <router-view />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Grid, Calendar, DataAnalysis, Money, Timer,
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

const tabs = [
  { name: 'wealth-heatmap', label: '宏观热力图', icon: Grid },
  { name: 'wealth-monthly', label: '月度日历', icon: Calendar },
  { name: 'wealth-review', label: '月度复盘', icon: DataAnalysis },
  { name: 'wealth-regular', label: '定期存款', icon: Timer },
  { name: 'wealth-cashflow', label: '现金盘点', icon: Money },
]

const activeTab = computed(() => {
  return route.name as string || 'wealth-heatmap'
})

function switchTab(name: string) {
  if (route.name !== name) {
    router.push({ name })
  }
}
</script>

<style scoped>
.wealth-hub {
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.wealth-hub__tabs-wrapper {
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
  position: sticky;
  top: 0;
  z-index: 100;
}

.wealth-hub__tabs {
  display: flex;
  max-width: 700px;
  margin: 0 auto;
}

.wealth-hub__tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 14px 8px;
  cursor: pointer;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  user-select: none;

  &:hover {
    color: var(--el-text-color-primary);
    background: var(--el-fill-color-light);
  }

  &.active {
    color: #f39c12;
    border-bottom-color: #f39c12;
    font-weight: 600;
  }
}

.wealth-hub__tab-icon {
  font-size: 16px;
}

.wealth-hub__content {
  /* child views have their own padding */
}
</style>
