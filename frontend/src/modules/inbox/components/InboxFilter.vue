<template>
  <div class="inbox-filter">
    <div class="filter-left">
      <el-input
        v-model="store.searchQuery"
        placeholder="🔍 搜索..."
        clearable
        size="small"
        style="width: 200px"
        @input="handleSearch"
      />
      <el-select v-model="store.filterCategory" placeholder="类别" size="small" clearable style="width: 100px" @change="store.search()">
        <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="`${c.icon} ${c.label}`" :value="c.value" />
      </el-select>
      <el-select v-model="store.filterPriority" placeholder="优先级" size="small" clearable style="width: 90px" @change="store.search()">
        <el-option label="🔴 高" value="high" />
        <el-option label="🟡 中" value="medium" />
        <el-option label="🟢 低" value="low" />
      </el-select>
    </div>
    <div class="filter-right">
      <el-button size="small" :type="batchMode ? 'warning' : 'default'" @click="toggleBatchMode">
        {{ batchMode ? '退出整理' : '📋 整理模式' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CATEGORY_OPTIONS } from '../types/inboxTypes'
import { useInboxStore } from '../stores/inboxStore'

const store = useInboxStore()

const batchMode = defineModel<boolean>('batchMode', { default: false })

let searchTimer: ReturnType<typeof setTimeout> | null = null
function handleSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => store.search(), 300)
}

function toggleBatchMode() {
  batchMode.value = !batchMode.value
  if (!batchMode.value) store.selectedIds = new Set()
}
</script>

<style scoped>
.inbox-filter {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.filter-left {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
</style>
