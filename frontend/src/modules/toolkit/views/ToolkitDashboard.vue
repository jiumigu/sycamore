<template>
  <div class="toolkit-dashboard">
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

    <!-- 筛选标签 -->
    <div class="filter-tabs">
      <el-radio-group v-model="activeFilter" size="small">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="环境侦查">🔍 环境侦查</el-radio-button>
        <el-radio-button value="图片处理">🖼️ 图片处理</el-radio-button>
        <el-radio-button value="财务">💰 财务</el-radio-button>
        <el-radio-button value="文字">📝 文字</el-radio-button>
        <el-radio-button value="健康">🩺 健康</el-radio-button>
        <el-radio-button value="其他">🧰 其他</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 工具卡片网格 -->
    <div v-loading="store.loading" class="tool-grid">
      <el-card
        v-for="tool in filteredTools"
        :key="tool.tool_key"
        class="tool-card"
        shadow="hover"
        @click="$router.push(`/toolkit/${tool.tool_key}`)"
      >
        <div class="tool-icon">{{ tool.icon }}</div>
        <div class="tool-name">{{ tool.name }}</div>
        <div class="tool-desc">{{ tool.description }}</div>
      </el-card>

      <el-empty v-if="!store.loading && filteredTools.length === 0" description="该分类下暂无工具" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Timer } from '@element-plus/icons-vue'
import { useToolkitStore } from '../stores/toolkitStore'

const store = useToolkitStore()
const searchText = ref('')
const activeFilter = ref('')

// 工具分类映射（按 tool_key）
const toolCategoryMap: Record<string, string> = {
  'career-energy-audit': '环境侦查',
  'environment-audit': '环境侦查',
  'decision-log': '环境侦查',
  'img2gif': '图片处理',
  'trad2simp': '文字',
  'free-spending': '财务',
  'hourly-wage': '财务',
  'quote-tool': '文字',
  'health-self-check': '健康',
}

function getToolCategory(tool: { tool_key: string }): string {
  return toolCategoryMap[tool.tool_key] || '其他'
}

const filteredTools = computed(() => {
  let list = store.tools
  if (activeFilter.value) {
    list = list.filter(t => getToolCategory(t) === activeFilter.value)
  }
  if (searchText.value.trim()) {
    const q = searchText.value.trim().toLowerCase()
    list = list.filter(t => t.name.includes(q) || t.description.includes(q))
  }
  return list
})

function onSearch() {
  /* no-op: computed reactivity handles it */
}

onMounted(async () => {
  await store.fetchTools()
})
</script>

<style scoped>
.toolkit-dashboard {
  padding: 20px; background: #F5F7FA; min-height: 100vh;

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
    .header-left { display: flex; align-items: center; gap: 12px;
      .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    }
    .header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  }

  .filter-tabs {
    margin-bottom: 16px;
  }

  .tool-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;

    @media (max-width: 1200px) { grid-template-columns: repeat(3, 1fr); }
    @media (max-width: 768px) { grid-template-columns: repeat(2, 1fr); }
  }

  .tool-card {
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    margin: 0;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    }

    :deep(.el-card__body) {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      padding: 24px 20px;
    }

    .tool-icon { font-size: 32px; margin-bottom: 8px; }
    .tool-name { font-size: 15px; font-weight: 600; color: #1F2937; margin-bottom: 4px; }
    .tool-desc { font-size: 12px; color: #9CA3AF; line-height: 1.4; }
  }
}
</style>
