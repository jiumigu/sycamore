<!-- src/shared/components/layout/LayoutSidebar.vue -->
<template>
  <aside class="layout-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 折叠/展开按钮 -->
    <div class="sidebar-toggle" @click="toggleCollapse">
      <el-icon v-if="isCollapsed"><Expand /></el-icon>
      <el-icon v-else><Fold /></el-icon>
    </div>

    <!-- 模块导航菜单（由 menuConfig + 用户偏好动态渲染） -->
    <div class="module-navigation">
      <template v-for="group in visibleGroups" :key="group.group_key">
        <div
          v-if="groupMenus(group.group_key).length > 0"
          class="nav-group"
          :class="`nav-group--${group.group_key}`"
        >
          <div class="group-title" v-if="!isCollapsed">{{ group.group_name }}</div>
          <router-link
            v-for="item in groupMenus(group.group_key)"
            :key="item.key"
            :to="item.path"
            class="nav-item"
            :class="{ active: isRouteActive(item.path) }"
          >
            <el-icon><component :is="iconMap[item.icon]" /></el-icon>
            <span v-if="!isCollapsed">{{ item.label }}</span>
            <el-badge
              v-if="item.key === 'inbox' && inboxStats.pending > 0 && !isCollapsed"
              :value="inboxStats.pending"
              :max="99"
              class="nav-badge"
            />
          </router-link>
        </div>
      </template>

      <!-- 归档菜单折叠区（系统运维分组下方，可展开） -->
      <div v-if="archivedMenus.length > 0" class="archived-section">
        <div class="archived-toggle" @click="showArchived = !showArchived">
          <el-icon><Box /></el-icon>
          <span v-if="!isCollapsed">归档菜单 ({{ archivedMenus.length }})</span>
          <el-icon v-if="!isCollapsed" class="archived-arrow">
            <ArrowUp v-if="showArchived" /><ArrowDown v-else />
          </el-icon>
        </div>
        <div v-show="showArchived && !isCollapsed" class="archived-body">
          <router-link
            v-for="item in archivedMenus"
            :key="item.key"
            :to="item.path"
            class="nav-item archived-item"
            :class="{ active: isRouteActive(item.path) }"
          >
            <el-icon><component :is="iconMap[item.icon]" /></el-icon>
            <span>{{ item.label }}</span>
            <el-tag size="small" type="info" class="archived-tag">归档</el-tag>
          </router-link>
        </div>
      </div>
    </div>

    <!-- 折叠提示 -->
    <div class="collapse-hint" v-if="isCollapsed">
      <span>点击展开</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { Component } from 'vue'
import * as ElementPlusIcons from '@element-plus/icons-vue'
// 模板中直接使用的固定图标（script setup 需显式注册）
import { Expand, Fold, Box, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import request from '@/shared/utils/request'
import { allMenuItems, defaultGroups, type MenuItem } from '@/shared/config/menuConfig'
import { getMenuPrefs, getMenuGroups, type MenuGroupData } from '@/shared/api/coreApi'

const route = useRoute()

// ========== 响应式数据 ==========
const isCollapsed = ref(false)
const showArchived = ref(true)
const inboxStats = ref({ pending: 0 })

/** 用户菜单偏好：menu_key -> { is_favorite, sort_order } */
const menuPrefs = ref<Record<string, { is_favorite: boolean; sort_order?: number }>>({})
/** 分组配置（后端权威），加载失败时回退 defaultGroups */
const groups = ref<(MenuGroupData & { group_name: string })[]>([])

// ========== 图标映射 ==========
const iconMap = ElementPlusIcons as Record<string, Component>

// ========== 计算属性 ==========
/** 可见分组（按 sort_order 排序，过滤隐藏组） */
const visibleGroups = computed(() => {
  const list = groups.value.length > 0
    ? groups.value
    : defaultGroups.map(g => ({ group_key: g.key, group_name: g.name, sort_order: g.sort, is_visible: true }))
  return list
    .filter(g => g.is_visible !== false)
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
})

/** 是否归档：有偏好记录看记录；无记录看 defaultArchived */
const isArchived = (item: MenuItem): boolean => {
  const pref = menuPrefs.value[item.key]
  if (pref) return !pref.is_favorite
  return !!item.defaultArchived
}

/** 某分组下的常用菜单 */
const groupMenus = (groupKey: string): MenuItem[] => {
  return allMenuItems.filter(m => m.group === groupKey && !isArchived(m))
}

/** 全部归档菜单 */
const archivedMenus = computed<MenuItem[]>(() => {
  return allMenuItems.filter(m => isArchived(m))
})

// ========== 方法 ==========
const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem('sidebarCollapsed', isCollapsed.value.toString())
}

const isRouteActive = (path: string) => {
  return route.path.startsWith(path)
}

// ========== 数据加载 ==========
const fetchMenuData = async () => {
  try {
    const [prefsRes, groupsRes] = await Promise.all([
      getMenuPrefs(),
      getMenuGroups(),
    ])
    const prefs: Record<string, { is_favorite: boolean; sort_order?: number }> = {}
    ;(prefsRes.data as Array<{ menu_key: string; is_favorite: boolean; sort_order?: number }>).forEach(p => {
      prefs[p.menu_key] = { is_favorite: p.is_favorite, sort_order: p.sort_order }
    })
    menuPrefs.value = prefs
    groups.value = groupsRes.data?.results?.length ? groupsRes.data.results : groupsRes.data || []
  } catch (e) {
    console.error('加载菜单配置失败，使用默认配置', e)
  }
}

// ========== 生命周期 ==========
onMounted(() => {
  const savedState = localStorage.getItem('sidebarCollapsed')
  if (savedState) {
    isCollapsed.value = savedState === 'true'
  }
  fetchMenuData()
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
  width: 220px;
  background: var(--lm-bg-primary);
  border-right: 1px solid var(--lm-border-color);
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  position: relative;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;

  &::-webkit-scrollbar {
    width: 4px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: #ddd;
    border-radius: 4px;
  }

  &.collapsed {
    width: 60px;

    .nav-group {
      padding: 4px;
    }

    .nav-item {
      padding: 10px 0;
      justify-content: center;

      span { display: none; }
      .nav-badge { display: none; }
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
  flex-shrink: 0;

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
  overflow-x: hidden;
  padding: 12px;

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

  // ========== 导航分组 ==========
  .nav-group {
    border-radius: 8px;
    padding: 6px;
    margin-bottom: 8px;

    &--overview { background: rgba(64, 158, 255, 0.06); }
    &--temporal { background: rgba(128, 90, 213, 0.06); }
    &--goals { background: rgba(230, 162, 60, 0.06); }
    &--health { background: rgba(46, 204, 113, 0.06); }
    &--nourishment { background: rgba(231, 76, 60, 0.06); }
    &--wealth { background: rgba(243, 156, 18, 0.06); }
    &--connection { background: rgba(211, 84, 0, 0.06); }
    &--tools { background: rgba(0, 0, 0, 0.03); }
    &--system { background: rgba(0, 0, 0, 0.02); }
  }

  .group-title {
    font-size: 11px;
    color: var(--lm-text-secondary);
    padding: 4px 8px 6px;
    letter-spacing: 1px;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-radius: 8px;
    text-decoration: none;
    color: var(--lm-text-primary);
    transition: all 0.3s;
    position: relative;
    margin-bottom: 2px;

    &.sub-item {
      padding-left: 20px;
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
      font-size: 16px;
      color: var(--lm-text-secondary);
      transition: all 0.3s;
      flex-shrink: 0;
    }

    span {
      flex: 1;
      font-size: 13px;
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
        font-size: 10px;
        height: 16px;
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

  // ========== 归档折叠区 ==========
  .archived-section {
    border-radius: 8px;
    padding: 6px;
    margin-bottom: 8px;
    background: rgba(0, 0, 0, 0.015);
  }

  .archived-toggle {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    color: var(--lm-text-secondary);
    font-size: 13px;
    transition: all 0.3s;

    &:hover {
      background: var(--lm-bg-secondary);
      color: var(--lm-primary-color);
    }

    .el-icon {
      font-size: 16px;
    }

    .archived-arrow {
      margin-left: auto;
      font-size: 12px;
    }
  }

  .archived-body {
    padding-top: 4px;
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
