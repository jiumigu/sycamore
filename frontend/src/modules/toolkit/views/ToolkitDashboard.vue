<template>
  <div class="toolkit-dashboard">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">🛠️ 工具集</h1>
        <el-tag type="warning" class="module-tag">实用工具</el-tag>
      </div>
      <div class="header-actions">
        <el-input v-model="searchText" placeholder="搜索工具..." clearable style="width:200px" @input="onSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button text @click="$router.push('/toolkit/history')">
          <el-icon><Timer /></el-icon> 执行历史
        </el-button>
      </div>
    </div>

    <!-- 分类标签（卡片式） -->
    <div class="category-tabs">
      <div
        v-for="cat in categoryList"
        :key="cat.key"
        class="category-tab"
        :class="{ active: activeCategory === cat.key }"
        @click="switchCategory(cat.key)"
      >
        <span class="cat-label">{{ cat.label }}</span>
        <span class="cat-count">{{ cat.count }}</span>
      </div>
    </div>

    <!-- 工具网格 -->
    <div v-loading="store.loading" class="tool-grid">
      <div v-for="tool in filteredTools" :key="tool.tool_key" class="tool-card" @click="$router.push(`/toolkit/${tool.tool_key}`)">
        <div class="tool-icon">{{ tool.icon }}</div>
        <div class="tool-name">{{ tool.name }}</div>
        <div class="tool-desc">{{ tool.description }}</div>
        <el-button size="small" type="primary" round class="tool-btn">使用</el-button>
      </div>
      <el-empty v-if="!store.loading && filteredTools.length === 0" description="暂无工具" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Timer } from '@element-plus/icons-vue'
import { useToolkitStore } from '../stores/toolkitStore'
import { CATEGORY_LABELS } from '../types/toolkitTypes'

const store = useToolkitStore()
const searchText = ref('')
const activeCategory = ref('')

const categoryList = computed(() => {
  const all = { key: '', label: '全部', count: store.tools.length }
  return [all, ...store.categories]
})

const filteredTools = computed(() => {
  let list = store.tools
  if (activeCategory.value) {
    list = list.filter(t => t.category === activeCategory.value)
  }
  if (searchText.value.trim()) {
    const q = searchText.value.trim().toLowerCase()
    list = list.filter(t => t.name.includes(q) || t.description.includes(q))
  }
  return list
})

function switchCategory(cat: string) {
  activeCategory.value = cat
}

function onSearch() {
  /* no-op: computed reactivity handles it */
}

onMounted(async () => {
  await store.fetchTools()
})
</script>

<style scoped lang="scss">
.toolkit-dashboard {
  padding: 20px; background: #F5F7FA; min-height: 100vh;

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
    .header-left { display: flex; align-items: center; gap: 12px;
      .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    }
    .header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  }

  .category-tabs {
    display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap;
    .category-tab {
      display: flex; align-items: center; gap: 6px;
      padding: 8px 16px; border-radius: 20px; cursor: pointer;
      background: #fff; border: 1px solid #e5e7eb;
      font-size: 13px; color: #6B7280; transition: all 0.2s;
      &:hover { border-color: #A78BFA; color: #7C3AED; }
      &.active { background: #7C3AED; border-color: #7C3AED; color: #fff;
        .cat-count { background: rgba(255,255,255,0.2); color: #fff; }
      }
      .cat-count {
        font-size: 11px; padding: 1px 7px; border-radius: 10px;
        background: #f3f4f6; color: #9CA3AF;
      }
    }
  }

  .tool-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px;
    min-height: 200px;

    .tool-card {
      background: #fff; border: 1px solid #f0f0f0; border-radius: 12px;
      padding: 24px 20px; cursor: pointer;
      display: flex; flex-direction: column; align-items: center; text-align: center;
      transition: all 0.25s;
      &:hover { border-color: #c4b5fd; box-shadow: 0 4px 16px rgba(139,92,246,0.1); transform: translateY(-3px); }

      .tool-icon { font-size: 36px; margin-bottom: 12px; }
      .tool-name { font-size: 16px; font-weight: 600; color: #1F2937; margin-bottom: 6px; }
      .tool-desc { font-size: 13px; color: #9CA3AF; line-height: 1.5; margin-bottom: 16px; flex: 1; }
      .tool-btn { flex-shrink: 0; }
    }
  }
}
</style>
