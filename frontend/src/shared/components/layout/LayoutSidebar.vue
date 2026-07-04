<!-- src/shared/components/layout/LayoutSidebar.vue -->
<template>
  <aside class="layout-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 折叠/展开按钮 -->
    <div class="sidebar-toggle" @click="toggleCollapse">
      <el-icon v-if="isCollapsed"><Expand /></el-icon>
      <el-icon v-else><Fold /></el-icon>
    </div>

    <!-- 模块导航菜单 -->
    <div class="module-navigation">

      <!-- ========== 总览 ========== -->
      <div class="nav-section">
        <div class="section-title" v-if="!isCollapsed">总览</div>

        <router-link
          to="/dashboard"
          class="nav-item"
          :class="{ active: isRouteActive('/dashboard') }"
        >
          <el-icon><DataAnalysis /></el-icon>
          <span v-if="!isCollapsed">仪表盘</span>
        </router-link>

        <router-link
          to="/summary"
          class="nav-item"
          :class="{ active: isRouteActive('/summary') && route.path === '/summary' }"
        >
          <el-icon><PieChart /></el-icon>
          <span v-if="!isCollapsed">汇总总览</span>
        </router-link>

        <router-link
          to="/summary/quarterly"
          class="nav-item"
          :class="{ active: isRouteActive('/summary/quarterly') }"
        >
          <el-icon><TrendCharts /></el-icon>
          <span v-if="!isCollapsed">季度决策</span>
        </router-link>

        <router-link
          to="/summary/profile"
          class="nav-item"
          :class="{ active: isRouteActive('/summary/profile') }"
        >
          <el-icon><User /></el-icon>
          <span v-if="!isCollapsed">个人画像</span>
        </router-link>

        <router-link
          to="/inbox"
          class="nav-item"
          :class="{ active: isRouteActive('/inbox') }"
          :style="getModuleStyle('inbox')"
        >
          <el-icon><MessageBox /></el-icon>
          <span v-if="!isCollapsed">收件箱</span>
          <el-badge
            v-if="inboxStats.pending > 0 && !isCollapsed"
            :value="inboxStats.pending"
            :max="99"
            class="nav-badge"
          />
        </router-link>
      </div>

      <!-- ========== 时间感知 ========== -->
      <div class="nav-section">
        <div class="section-title" v-if="!isCollapsed">时间感知</div>

        <router-link
          to="/temporal/daily"
          class="nav-item"
          :class="{ active: isRouteActive('/temporal/daily') }"
          :style="getModuleStyle('temporal')"
        >
          <el-icon><Calendar /></el-icon>
          <span v-if="!isCollapsed">日记流</span>
        </router-link>

        <router-link
          to="/temporal"
          class="nav-item"
          :class="{ active: isRouteActive('/temporal') && !isRouteActive('/temporal/daily') }"
          :style="getModuleStyle('temporal')"
        >
          <el-icon><Timer /></el-icon>
          <span v-if="!isCollapsed">时间统计</span>
        </router-link>

        <router-link
          to="/temporal/weekly-tracking"
          class="nav-item"
          :class="{ active: isRouteActive('/temporal/weekly-tracking') }"
          :style="getModuleStyle('temporal')"
        >
          <el-icon><TrendCharts /></el-icon>
          <span v-if="!isCollapsed">周度追踪</span>
        </router-link>

        <router-link
          to="/temporal/schedule"
          class="nav-item"
          :class="{ active: isRouteActive('/temporal/schedule') }"
          :style="getModuleStyle('temporal')"
        >
          <el-icon><Calendar /></el-icon>
          <span v-if="!isCollapsed">日程视图</span>
        </router-link>
      </div>

      <!-- ========== 目标与项目 ========== -->
      <div class="nav-section">
        <div class="section-title" v-if="!isCollapsed">目标与项目</div>

        <router-link
          to="/goals"
          class="nav-item"
          :class="{ active: isRouteActive('/goals') }"
          :style="getModuleStyle('goals')"
        >
          <el-icon><Flag /></el-icon>
          <span v-if="!isCollapsed">人生目标</span>
        </router-link>

        <!-- 快乐银行 -->
        <router-link
          to="/reward"
          class="nav-item"
          :class="{ active: isRouteActive('/reward') && !isRouteActive('/reward/gifts') }"
          :style="getModuleStyle('reward')"
        >
          <el-icon>
            <component :is="Trophy" />
          </el-icon>
          <span v-if="!isCollapsed">快乐银行</span>
        </router-link>

        <!-- 礼物清单（独立同级） -->
        <router-link
          to="/reward/gifts"
          class="nav-item"
          :class="{ active: isRouteActive('/reward/gifts') }"
          :style="getModuleStyle('reward')"
        >
          <el-icon><Present /></el-icon>
          <span v-if="!isCollapsed">礼物清单</span>
        </router-link>

        <router-link
          to="/output"
          class="nav-item"
          :class="{ active: isRouteActive('/output') }"
          :style="getModuleStyle('goals')"
        >
          <el-icon><Briefcase /></el-icon>
          <span v-if="!isCollapsed">个人良品率</span>
        </router-link>
      </div>

      <!-- ========== 身心健康 ========== -->
      <div class="nav-section">
        <div class="section-title" v-if="!isCollapsed">身心健康</div>

        <router-link
          to="/health"
          class="nav-item"
          :class="{ active: isRouteActive('/health') }"
          :style="getModuleStyle('health')"
        >
          <el-icon><FirstAidKit /></el-icon>
          <span v-if="!isCollapsed">健康管理</span>
        </router-link>

        <router-link
          to="/health/weight"
          class="nav-item"
          :class="{ active: isRouteActive('/health/weight') }"
          :style="getModuleStyle('health')"
        >
          <el-icon><TrendCharts /></el-icon>
          <span v-if="!isCollapsed">体重管理</span>
        </router-link>

        <router-link
          to="/health/menstrual"
          class="nav-item"
          :class="{ active: isRouteActive('/health/menstrual') }"
          :style="getModuleStyle('health')"
        >
          <el-icon><FirstAidKit /></el-icon>
          <span v-if="!isCollapsed">好朋友跟踪</span>
        </router-link>

        <router-link
          to="/dance"
          class="nav-item archived-item"
          :class="{ active: isRouteActive('/dance') }"
          :style="getModuleStyle('dance')"
        >
          <el-icon><Star /></el-icon>
          <span v-if="!isCollapsed">舞蹈记录</span>
          <el-tag v-if="!isCollapsed" size="small" type="info" class="archived-tag">归档</el-tag>
        </router-link>
      </div>

      <!-- ========== 精神滋养 ========== -->
      <div class="nav-section">
        <div class="section-title" v-if="!isCollapsed">精神滋养</div>

        <router-link
          to="/books"
          class="nav-item"
          :class="{ active: isRouteActive('/books') }"
          :style="getModuleStyle('book')"
        >
          <el-icon><Reading /></el-icon>
          <span v-if="!isCollapsed">书籍阅读</span>
        </router-link>

        <router-link
          to="/sugar"
          class="nav-item"
          :class="{ active: isRouteActive('/sugar') }"
          :style="getModuleStyle('sugar')"
        >
          <el-icon><Present /></el-icon>
          <span v-if="!isCollapsed">小确幸</span>
        </router-link>

        <router-link
          to="/treasure"
          class="nav-item"
          :class="{ active: isRouteActive('/treasure') }"
          :style="getModuleStyle('treasure')"
        >
          <el-icon><Star /></el-icon>
          <span v-if="!isCollapsed">好东西</span>
        </router-link>
      </div>

      <!-- ========== 财富管理 ========== -->
      <div class="nav-section">
        <div class="section-title" v-if="!isCollapsed">财富管理</div>

        <router-link
          to="/wealth"
          class="nav-item"
          :class="{ active: isRouteActive('/wealth') }"
          :style="getModuleStyle('wealth')"
        >
          <el-icon><Money /></el-icon>
          <span v-if="!isCollapsed">财务管理</span>
        </router-link>

        <router-link
          to="/dams"
          class="nav-item"
          :class="{ active: isRouteActive('/dams') }"
          :style="getModuleStyle('dams')"
        >
          <el-icon><Cpu /></el-icon>
          <span v-if="!isCollapsed">数字资产</span>
        </router-link>
      </div>

      <!-- ========== 连接与足迹 ========== -->
      <div class="nav-section">
        <div class="section-title" v-if="!isCollapsed">连接与足迹</div>

        <router-link
          to="/food"
          class="nav-item"
          :class="{ active: isRouteActive('/food') }"
          :style="getModuleStyle('food')"
        >
          <el-icon><Food /></el-icon>
          <span v-if="!isCollapsed">美食地图</span>
        </router-link>

        <router-link
          to="/travel"
          class="nav-item"
          :class="{ active: isRouteActive('/travel') }"
          :style="getModuleStyle('travel')"
        >
          <el-icon><Location /></el-icon>
          <span v-if="!isCollapsed">旅行记录</span>
        </router-link>

        <router-link
          to="/relation"
          class="nav-item"
          :class="{ active: isRouteActive('/relation') && route.path === '/relation' }"
          :style="getModuleStyle('relation')"
        >
          <el-icon><User /></el-icon>
          <span v-if="!isCollapsed">关系管理</span>
        </router-link>

        <router-link
          to="/relation/conflicts"
          class="nav-item sub-item"
          :class="{ active: isRouteActive('/relation/conflicts') }"
          :style="getModuleStyle('relation')"
        >
          <el-icon><Sunny /></el-icon>
          <span v-if="!isCollapsed">成长记录</span>
        </router-link>
      </div>

      <!-- ========== 工具箱 ========== -->
      <div class="nav-section">
        <div class="section-title" v-if="!isCollapsed">工具箱</div>

        <router-link
          to="/toolkit"
          class="nav-item"
          :class="{ active: isRouteActive('/toolkit') }"
        >
          <el-icon><Tools /></el-icon>
          <span v-if="!isCollapsed">工具箱</span>
        </router-link>

        <router-link
          to="/toolkit/history"
          class="nav-item sub-item"
          :class="{ active: isRouteActive('/toolkit/history') }"
        >
          <el-icon><Timer /></el-icon>
          <span v-if="!isCollapsed">执行历史</span>
        </router-link>

        <router-link
          to="/toolkit/decision-log"
          class="nav-item sub-item"
          :class="{ active: isRouteActive('/toolkit/decision-log') }"
        >
          <el-icon><WarningFilled /></el-icon>
          <span v-if="!isCollapsed">决策日志</span>
        </router-link>
        <router-link
          to="/toolkit/free-spending"
          class="nav-item sub-item"
          :class="{ active: isRouteActive('/toolkit/free-spending') }"
        >
          <el-icon><Money /></el-icon>
          <span v-if="!isCollapsed">自由支配额度</span>
        </router-link>
        <router-link
          to="/toolkit/review-toolbox"
          class="nav-item sub-item"
          :class="{ active: isRouteActive('/toolkit/review-toolbox') }"
        >
          <el-icon><List /></el-icon>
          <span v-if="!isCollapsed">复盘工具箱</span>
        </router-link>
      </div>

      <!-- ========== 系统运维 ========== -->
      <div class="nav-section">
        <div class="section-title" v-if="!isCollapsed">系统运维</div>

        <router-link
          to="/admin/tag-manager"
          class="nav-item"
          :class="{ active: isRouteActive('/admin/tag-manager') }"
        >
          <el-icon><PriceTag /></el-icon>
          <span v-if="!isCollapsed">标签管理器</span>
        </router-link>
      </div>

    </div>

    <!-- 折叠提示 -->
    <div class="collapse-hint" v-if="isCollapsed">
      <span>点击展开</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import request from '@/shared/utils/request'
import {
  Expand, Fold, DataAnalysis, PieChart,
  Calendar, Timer, TrendCharts, Check,
  Flag, Briefcase,
  FirstAidKit, Star,
  Sunny, Reading, Trophy, Present,
  Money, Cpu,
  Location, User, Tools, Food, WarningFilled, PriceTag,
  Histogram, Connection, MessageBox, List,
} from '@element-plus/icons-vue'

const route = useRoute()

// ========== 响应式数据 ==========
const isCollapsed = ref(false)

// 模拟数据（后续从各模块 store 获取）
const inboxStats = ref({ pending: 0 })

// ========== 模块颜色映射 ==========
const moduleColors: Record<string, string> = {
  temporal: '#3498db',
  goals: '#8e44ad',
  projects: '#e67e22',
  health: '#2ecc71',
  dance: '#16a085',
  nourishment: '#e74c3c',
  book: '#9b59b6',
  sugar: '#e67e22',
  wealth: '#f39c12',
  reward: '#e74c3c',
  dams: '#34495e',
  food: '#F59E0B',
  travel: '#e74c3c',
  relation: '#d35400',
  inbox: '#3B82F6',
  treasure: '#F59E0B',
}

// ========== 方法 ==========
const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem('sidebarCollapsed', isCollapsed.value.toString())
}

const isRouteActive = (path: string) => {
  return route.path.startsWith(path)
}

const getModuleStyle = (module: string) => {
  const color = moduleColors[module] || '#3498db'
  return {
    '--module-color': color,
    '--module-color-light': `${color}20`,
    '--module-color-dark': `${color}40`
  }
}

// ========== 生命周期 ==========
onMounted(() => {
  const savedState = localStorage.getItem('sidebarCollapsed')
  if (savedState) {
    isCollapsed.value = savedState === 'true'
  }
  // 收件箱未处理数
  request<{ pending: number }>({ url: '/inbox/items/stats/', method: 'get' })
    .then(r => { inboxStats.value = { pending: r.data.pending } })
    .catch(() => {})
})

// ========== 事件 ==========
const emit = defineEmits(['collapseChange'])
watch(isCollapsed, (newVal) => {
  emit('collapseChange', newVal)
})
</script>

<style scoped lang="scss">
.layout-sidebar {
  width: 260px;
  background: var(--lm-bg-primary);
  border-right: 1px solid var(--lm-border-color);
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  position: relative;
  height: 100%;

  &.collapsed {
    width: 70px;

    .module-navigation {
      .section-title { display: none; }

      .nav-item {
        justify-content: center;
        padding: 12px;

        span { display: none; }
        .nav-badge { display: none; }
      }
    }

    .collapse-hint { display: flex; }
    }
  }

  .sidebar-toggle {
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-bottom: 1px solid var(--lm-border-color);
    cursor: pointer;
    transition: all 0.3s;

    &:hover {
      background: var(--lm-bg-secondary);
      .el-icon { color: var(--lm-primary-color); }
    }

    .el-icon {
      font-size: 18px;
      color: var(--lm-text-secondary);
    }
  }

  .module-navigation {
    flex: 1;
    overflow-y: auto;
    padding: 16px 12px;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: var(--lm-border-color);
      border-radius: 4px;

      &:hover {
        background: var(--lm-text-secondary);
      }
    }

    .nav-section {
      margin-bottom: 24px;

      .section-title {
        font-size: 12px;
        color: var(--lm-text-secondary);
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
        padding-left: 12px;
        font-weight: 600;
      }

      .nav-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        border-radius: 8px;
        text-decoration: none;
        color: var(--lm-text-primary);
        transition: all 0.3s;
        position: relative;
        margin-bottom: 4px;

        &.sub-item {
          padding-left: 24px;
        }

        &:hover {
          background: var(--lm-bg-secondary);
          color: var(--lm-primary-color);

          .el-icon { color: var(--lm-primary-color); }
        }

        &.active {
          background: linear-gradient(
            to right,
            var(--module-color-light, rgba(52, 152, 219, 0.1)),
            transparent
          );
          color: var(--module-color, #3498db);
          font-weight: 500;

          &::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: var(--module-color, #3498db);
            border-radius: 0 2px 2px 0;
          }

          .el-icon { color: var(--module-color, #3498db); }
        }

        .el-icon {
          font-size: 18px;
          color: var(--lm-text-secondary);
          transition: all 0.3s;
          flex-shrink: 0;
        }

        span {
          flex: 1;
          font-size: 14px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .nav-badge {
          position: absolute;
          right: 12px;
          top: 50%;
          transform: translateY(-50%);

          :deep(.el-badge__content) {
            background-color: var(--module-color, #3498db);
            border: 2px solid var(--lm-bg-primary);
          }
        }

        &.archived-item {
          opacity: 0.5;
          &:hover { opacity: 0.8; }
        }

        .archived-tag {
          margin-left: auto;
          font-size: 10px;
          transform: scale(0.85);
        }
      }
    }
  }

  .collapse-hint {
    display: none;
    position: absolute;
    bottom: 20px;
    left: 0;
    right: 0;
    justify-content: center;

    span {
      font-size: 12px;
      color: var(--lm-text-secondary);
      writing-mode: vertical-rl;
      text-orientation: mixed;
      letter-spacing: 2px;
      opacity: 0.5;
      cursor: default;
    }
  }
</style>