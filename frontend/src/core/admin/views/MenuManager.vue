<template>
  <div class="menu-manager">
    <h2>📋 菜单管理</h2>
    <p class="subtitle">标记常用的菜单显示在侧边栏，不常用的收进「归档菜单」折叠区；取消归档自动回到原本分组。</p>

    <!-- 分组管理 -->
    <el-card class="group-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>分组管理</span>
          <el-button size="small" type="primary" plain @click="addGroup">+ 新增分组</el-button>
        </div>
      </template>
      <div v-for="(g, i) in groups" :key="g.group_key" class="group-row">
        <el-button-group size="small">
          <el-button :disabled="i === 0" @click="moveGroup(g, -1)"><el-icon><ArrowUp /></el-icon></el-button>
          <el-button :disabled="i === groups.length - 1" @click="moveGroup(g, 1)"><el-icon><ArrowDown /></el-icon></el-button>
        </el-button-group>
        <el-input v-model="g.group_name" size="small" style="width: 160px" @change="renameGroup(g)" />
        <el-tag size="small" type="info">{{ g.group_key }}</el-tag>
        <el-switch
          v-model="g.is_visible"
          active-text="显示"
          inactive-text="隐藏"
          @change="toggleGroupVisible(g)"
        />
        <el-button size="small" type="danger" plain @click="removeGroup(g)">删除</el-button>
      </div>
      <div v-if="groups.length === 0" class="empty-tip">暂无分组，点击「新增分组」创建</div>
    </el-card>

    <!-- 菜单项管理 -->
    <el-card class="menu-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>菜单项管理</span>
          <span class="header-hint">切换后点「保存全部」生效</span>
        </div>
      </template>
      <div v-for="group in groups" :key="group.group_key" class="menu-group-section">
        <div class="group-title">{{ group.group_name }}</div>
        <div v-for="item in menusByGroup(group.group_key)" :key="item.key" class="menu-row">
          <span class="menu-icon"><el-icon><component :is="iconMap[item.icon]" /></el-icon></span>
          <span class="menu-label">{{ item.label }}</span>
          <el-tag v-if="item.defaultArchived" size="small" type="info" effect="plain">默认归档</el-tag>
          <span class="menu-path">{{ item.path }}</span>
          <el-switch
            :model-value="isFavorite(item.key)"
            @change="(v: boolean) => toggleFavorite(item.key, v)"
            active-text="常用"
            inactive-text="归档"
          />
        </div>
        <div v-if="menusByGroup(group.group_key).length === 0" class="empty-tip">该分组暂无菜单项</div>
      </div>
    </el-card>

    <div class="footer-bar">
      <el-button type="primary" @click="saveAll">保存全部</el-button>
      <el-button @click="loadData">放弃修改</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Component } from 'vue'
import * as ElementPlusIcons from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { allMenuItems, defaultGroups } from '@/shared/config/menuConfig'
import {
  getMenuPrefs, getMenuGroups, batchUpdateMenus,
  createMenuGroup, updateMenuGroup, deleteMenuGroup,
  type MenuGroupData,
} from '@/shared/api/coreApi'

const iconMap = ElementPlusIcons as Record<string, Component>

/** 分组行（id 一定存在：来自后端或新建返回） */
interface GroupRow {
  id: number
  group_key: string
  group_name: string
  sort_order?: number
  is_visible?: boolean
}

// ========== 状态 ==========
const groups = ref<GroupRow[]>([])
/** 本地菜单态：menu_key -> is_favorite（未记录时用 defaultArchived 兜底） */
const prefs = ref<Record<string, boolean>>({})

// ========== 数据加载 ==========
const loadData = async () => {
  try {
    const [gRes, pRes] = await Promise.all([getMenuGroups(), getMenuPrefs()])
    groups.value = ((gRes.data?.results?.length ? gRes.data.results : gRes.data || []) as GroupRow[])
    if (groups.value.length === 0) {
      groups.value = defaultGroups.map(g => ({ id: -1, group_key: g.key, group_name: g.name, sort_order: g.sort, is_visible: true }))
    }
    const p: Record<string, boolean> = {}
    ;(pRes.data as Array<{ menu_key: string; is_favorite: boolean }>).forEach(x => { p[x.menu_key] = x.is_favorite })
    prefs.value = p
  } catch (e) {
    console.error('加载菜单配置失败', e)
    ElMessage.error('加载菜单配置失败')
  }
}
onMounted(loadData)

// ========== 菜单项逻辑 ==========
const isFavorite = (key: string): boolean => {
  if (key in prefs.value) return prefs.value[key]
  const item = allMenuItems.find(i => i.key === key)
  return !item?.defaultArchived
}

const toggleFavorite = (key: string, val: boolean) => {
  prefs.value[key] = val
}

const menusByGroup = (groupKey: string) => {
  return allMenuItems.filter(m => m.group === groupKey)
}

// ========== 分组操作 ==========
const renameGroup = async (g: GroupRow) => {
  if (!g.group_name.trim()) { g.group_name = g.group_name.trim(); return }
  await updateMenuGroup(g.id, { group_name: g.group_name.trim() })
  ElMessage.success('分组已重命名')
}

const moveGroup = async (g: GroupRow, dir: number) => {
  const idx = groups.value.indexOf(g)
  const target = groups.value[idx + dir]
  if (!target) return
  const tmp = g.sort_order
  g.sort_order = target.sort_order
  target.sort_order = tmp
  // 交换后按 sort_order 重排本地数组
  groups.value.sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
  await Promise.all([
    updateMenuGroup(g.id, { sort_order: g.sort_order }),
    updateMenuGroup(target.id, { sort_order: target.sort_order }),
  ])
  ElMessage.success('已调整顺序')
}

const toggleGroupVisible = async (g: GroupRow) => {
  await updateMenuGroup(g.id, { is_visible: g.is_visible })
  ElMessage.success(g.is_visible ? '分组已显示' : '分组已隐藏')
}

const removeGroup = async (g: GroupRow) => {
  const items = allMenuItems.filter(m => m.group === g.group_key)
  const hint = items.length > 0 ? `，组内 ${items.length} 个菜单将转为归档` : ''
  await ElMessageBox.confirm(`确定删除分组「${g.group_name}」？${hint}（菜单数据不受影响）`, '删除分组', { type: 'warning' })
  // 组内菜单转归档
  for (const item of items) prefs.value[item.key] = false
  await deleteMenuGroup(g.id)
  groups.value = groups.value.filter(x => x.group_key !== g.group_key)
  ElMessage.success('分组已删除')
}

const addGroup = async () => {
  const { value } = await ElMessageBox.prompt('输入新分组名称', '新增分组', { inputPlaceholder: '例如：学习成长' })
  if (!value?.trim()) return
  const key = `custom_${Date.now()}`
  const created = await createMenuGroup({ group_key: key, group_name: value.trim() })
  groups.value.push({ id: created.data.id, group_key: key, group_name: value.trim(), sort_order: 999, is_visible: true })
  groups.value.sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
  ElMessage.success('分组已创建')
}

// ========== 保存 ==========
const saveAll = async () => {
  const updates = allMenuItems.map(item => ({
    menu_key: item.key,
    is_favorite: isFavorite(item.key),
  }))
  await batchUpdateMenus(updates)
  ElMessage.success('菜单偏好已保存')
}
</script>

<style scoped lang="scss">
.menu-manager {
  padding: 8px;

  h2 { margin: 0 0 4px; }
  .subtitle { color: var(--lm-text-secondary); font-size: 13px; margin: 0 0 16px; }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;

    .header-hint { font-size: 12px; color: var(--lm-text-secondary); }
  }

  .group-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
    border-bottom: 1px dashed var(--lm-border-color);

    &:last-child { border-bottom: none; }
  }

  .menu-group-section {
    margin-bottom: 18px;

    .group-title {
      font-weight: 600;
      font-size: 14px;
      margin-bottom: 8px;
      padding-left: 8px;
      border-left: 3px solid var(--lm-primary-color);
    }

    .menu-row {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 6px 8px;
      border-radius: 6px;

      &:hover { background: var(--lm-bg-secondary); }

      .menu-icon .el-icon { font-size: 15px; color: var(--lm-text-secondary); }
      .menu-label { width: 120px; font-size: 13px; }
      .menu-path { flex: 1; font-size: 12px; color: var(--lm-text-secondary); opacity: 0.7; }
    }
  }

  .empty-tip { color: var(--lm-text-secondary); font-size: 12px; padding: 8px 0; }

  .footer-bar {
    margin-top: 16px;
    display: flex;
    gap: 12px;
  }
}
</style>
