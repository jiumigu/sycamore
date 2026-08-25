<template>
  <div class="lifesample-page">
    <!-- 标题 + 操作栏 -->
    <div class="page-header">
      <div class="header-left">
        <h2>📚 人生样本</h2>
        <span class="header-subtitle">轻量索引 · 深度内容存放在 Obsidian</span>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 新建
        </el-button>
        <el-button @click="handleSync" :loading="store.syncing">
          <el-icon><Refresh /></el-icon> 同步
        </el-button>
        <el-button @click="openObsidianFolder">
          📂 打开
        </el-button>
      </div>
    </div>

    <!-- 第一行：核心统计卡片（点击筛选/清除） -->
    <el-row :gutter="12" class="stats-row">
      <el-col v-for="item in statItems" :key="item.key" :span="4">
        <div
          class="stat-card compact"
          :class="{ active: item.active }"
          @click="item.click ? item.click() : null"
        >
          <div class="stat-number">{{ item.value }}</div>
          <div class="stat-label">{{ item.icon }} {{ item.label }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 第二行：评级摘要（点击筛选） -->
    <div class="relevance-summary">
      <span class="relevance-label">借鉴价值：</span>
      <span
        v-for="item in relevanceItems"
        :key="item.key"
        class="relevance-item"
        :class="{ active: item.active }"
        @click="item.click ? item.click() : null"
      >
        {{ item.icon }} {{ item.label }} <strong>{{ item.value }}</strong>
      </span>
    </div>

    <!-- 第三行：筛选器 -->
    <div class="filter-bar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索姓名..."
        clearable
        :prefix-icon="Search"
        style="width: 180px"
        size="small"
        @input="handleSearch"
      />
      <el-select
        v-model="filterType"
        placeholder="类型"
        clearable
        size="small"
        style="width: 110px"
        @change="handleSearch"
      >
        <el-option
          v-for="(label, value) in SampleTypeLabels"
          :key="value"
          :label="label"
          :value="value"
        />
      </el-select>
      <el-select
        v-model="filterStatus"
        placeholder="状态"
        clearable
        size="small"
        style="width: 110px"
        @change="handleSearch"
      >
        <el-option
          v-for="(config, key) in StatusConfig"
          :key="key"
          :label="`${config.icon} ${config.label}`"
          :value="key"
        />
      </el-select>
      <el-select
        v-model="filterRelevance"
        placeholder="评级"
        clearable
        size="small"
        style="width: 110px"
        @change="handleSearch"
      >
        <el-option
          v-for="(config, key) in RelevanceConfig"
          :key="key"
          :label="`${config.icon} ${config.label}`"
          :value="key"
        />
      </el-select>
      <el-select
        v-model="filterTag"
        placeholder="标签"
        clearable
        filterable
        size="small"
        style="width: 120px"
        @change="handleSearch"
      >
        <el-option v-for="tag in store.allTags" :key="tag" :label="tag" :value="tag" />
      </el-select>
      <span class="result-count">共 {{ store.samples.length }} 个</span>
    </div>

    <!-- 样本卡片墙 -->
    <div v-loading="loading" class="sample-grid">
      <SampleCard
        v-for="sample in store.samples"
        :key="sample.id"
        :sample="sample"
        @click="handleCardClick"
      />

      <div v-if="!loading && store.samples.length === 0" class="empty-state">
        <p>暂无人生样本</p>
        <p class="hint">点击「新建」添加第一个样本，或「同步Obsidian」导入已有文件</p>
      </div>
    </div>

    <!-- 新建/编辑弹窗 -->
    <SampleForm
      v-model="showDialog"
      :initial-data="editingSample"
      :existing-tags="store.allTags"
      @submit="handleFormSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { useSampleStore } from '../stores/sample'
import type { SampleQueryParams } from '../stores/sample'
import { SampleCard, SampleForm } from '../components'
import { SampleTypeLabels, StatusConfig, RelevanceConfig } from '../types'
import type { LifeSample, LifeSampleForm, SampleRelevance, SampleStatus } from '../types'
import { sampleApi } from '../api'

const store = useSampleStore()

const loading = ref(false)
const searchQuery = ref('')
const filterType = ref('')
const filterStatus = ref<SampleStatus | ''>('')
const filterRelevance = ref<SampleRelevance | ''>('')
const filterTag = ref('')
const showDialog = ref(false)
const editingSample = ref<LifeSample | null>(null)

const loadData = async () => {
  loading.value = true
  try {
    const params: SampleQueryParams = {}
    if (searchQuery.value) params.search = searchQuery.value
    if (filterType.value) params.type = filterType.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterRelevance.value) params.relevance = filterRelevance.value
    if (filterTag.value) params.tag = filterTag.value
    await store.loadAll(params)
  } catch {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  loadData()
}

interface StatItem {
  key: string
  label: string
  icon: string
  value: number
  active: boolean
  click: (() => void) | null
}

// 第一行：核心统计卡片
const statItems = computed<StatItem[]>(() => {
  const s = store.stats
  return [
    { key: 'total', label: '总样本', icon: '📊', value: s?.total || 0, active: false, click: clearAll },
    {
      key: 'collected',
      label: '已收集',
      icon: '📥',
      value: s?.status?.collected || 0,
      active: filterStatus.value === 'collected',
      click: () => toggleFilter('status', 'collected'),
    },
    {
      key: 'verified',
      label: '已核实',
      icon: '🔍',
      value: s?.status?.verified || 0,
      active: filterStatus.value === 'verified',
      click: () => toggleFilter('status', 'verified'),
    },
    {
      key: 'reviewed',
      label: '已审阅',
      icon: '✅',
      value: s?.status?.reviewed || 0,
      active: filterStatus.value === 'reviewed',
      click: () => toggleFilter('status', 'reviewed'),
    },
    { key: 'synced', label: '已关联', icon: '📂', value: s?.synced || 0, active: false, click: null },
  ]
})

// 第二行：评级摘要
const relevanceItems = computed<StatItem[]>(() => {
  const s = store.stats
  return [
    {
      key: 'high',
      label: '高度借鉴',
      icon: '🔥',
      value: s?.relevance?.high || 0,
      active: filterRelevance.value === 'high',
      click: () => toggleFilter('relevance', 'high'),
    },
    {
      key: 'reference',
      label: '参考',
      icon: '📖',
      value: s?.relevance?.reference || 0,
      active: filterRelevance.value === 'reference',
      click: () => toggleFilter('relevance', 'reference'),
    },
    {
      key: 'knowledge',
      label: '了解',
      icon: '👀',
      value: s?.relevance?.knowledge || 0,
      active: filterRelevance.value === 'knowledge',
      click: () => toggleFilter('relevance', 'knowledge'),
    },
  ]
})

const toggleFilter = (type: 'status' | 'relevance', value: SampleStatus | SampleRelevance) => {
  if (type === 'status') {
    filterStatus.value = filterStatus.value === value ? '' : (value as SampleStatus)
  } else {
    filterRelevance.value = filterRelevance.value === value ? '' : (value as SampleRelevance)
  }
  handleSearch()
}

const clearFilters = () => {
  searchQuery.value = ''
  filterType.value = ''
  filterStatus.value = ''
  filterRelevance.value = ''
  filterTag.value = ''
}

const clearAll = () => {
  clearFilters()
  handleSearch()
}

const openCreate = () => {
  editingSample.value = null
  showDialog.value = true
}

const handleCardClick = (sample: LifeSample) => {
  editingSample.value = sample
  showDialog.value = true
}

const handleFormSubmit = async (data: LifeSampleForm) => {
  try {
    if (editingSample.value) {
      await store.updateSample(editingSample.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await store.createSample(data)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    editingSample.value = null
  } catch {
    ElMessage.error('保存失败')
  }
}

const handleSync = async () => {
  try {
    const result = await store.syncFromObsidian()
    if (result.success) {
      ElMessage.success(result.message)
      const migratedCount = result.migrated?.length ?? 0
      if (result.created.length > 0 || result.updated.length > 0 || migratedCount > 0) {
        ElMessageBox.alert(
          `📁 扫描到 ${result.total} 个文件\n` +
            `✅ 新增：${result.created.length} 个\n` +
            `🔄 更新：${result.updated.length} 个\n` +
            `🔁 迁移：${migratedCount} 个（路径变更）\n` +
            `⏭️ 跳过：${result.skipped.length} 个`,
          '同步结果',
          { confirmButtonText: '知道了', type: 'info' },
        )
      }
    } else {
      ElMessage.warning(result.message || '同步失败，请检查 Obsidian 配置')
    }
  } catch (error) {
    ElMessage.error((error as { response?: { data?: { message?: string } } })?.response?.data?.message || '同步失败')
  }
}

const openObsidianFolder = async () => {
  try {
    const res = await sampleApi.getObsidianConfig()
    if (!res.data.enabled || !res.data.vault_path) {
      ElMessage.warning('请先在「系统设置」中启用并配置 Obsidian 仓库路径')
      return
    }
    window.open(`obsidian://open?path=${encodeURIComponent(res.data.vault_path)}`, '_blank')
  } catch {
    ElMessage.warning('请先在「系统设置」中启用并配置 Obsidian 仓库路径')
  }
}

onMounted(loadData)
</script>

<style scoped lang="scss">
.lifesample-page {
  padding: 24px;
  background: #f5f7fa;
  min-height: 100vh;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .header-left {
      display: flex;
      align-items: baseline;
      gap: 12px;

      h2 {
        margin: 0;
        font-size: 20px;
        font-weight: 700;
        color: #1f2937;
      }

      .header-subtitle {
        font-size: 13px;
        color: var(--el-text-color-secondary);
      }
    }

    .header-actions {
      display: flex;
      gap: 8px;
    }
  }

  .stats-row {
    margin-bottom: 8px;

    .stat-card.compact {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 10px 4px;
      background: var(--el-bg-color);
      border-radius: 8px;
      border: 1px solid var(--el-border-color-light);
      cursor: pointer;
      transition: all 0.2s;
      user-select: none;

      &:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
      }

      &.active {
        border-color: var(--el-color-primary);
        background: var(--el-color-primary-light-9);
      }

      .stat-number {
        font-size: 22px;
        font-weight: 700;
        line-height: 1.2;
        color: var(--el-text-color-primary);
      }

      .stat-label {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        margin-top: 2px;
      }
    }
  }

  .relevance-summary {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 16px;
    background: var(--el-fill-color-light);
    border-radius: 6px;
    margin-bottom: 12px;
    font-size: 13px;
    flex-wrap: wrap;

    .relevance-label {
      color: var(--el-text-color-secondary);
      font-weight: 500;
    }

    .relevance-item {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      color: var(--el-text-color-secondary);
      cursor: pointer;
      padding: 2px 8px;
      border-radius: 12px;
      transition: all 0.2s;

      &:hover {
        background: var(--el-fill-color);
      }

      &.active {
        background: var(--el-color-primary-light-9);
        color: var(--el-color-primary);
      }

      strong {
        color: var(--el-text-color-primary);
        font-weight: 600;
      }
    }
  }

  .filter-bar {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 16px;
    flex-wrap: wrap;

    .result-count {
      font-size: 13px;
      color: var(--el-text-color-secondary);
      margin-left: auto;
    }
  }

  .sample-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    min-height: 200px;
  }

  .empty-state {
    grid-column: 1 / -1;
    text-align: center;
    padding: 60px 20px;
    color: var(--el-text-color-secondary);

    .hint {
      font-size: 14px;
      margin-top: 8px;
    }
  }
}
</style>
