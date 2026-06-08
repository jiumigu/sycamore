<template>
  <div class="food-dashboard">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-title">
        <span class="title-icon">🍜</span>
        <h1>美食记录</h1>
      </div>
      <el-button type="primary" @click="openAddDialog">
        <el-icon><Plus /></el-icon>
        添加美食
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <FoodStatsCards v-if="store.stats" :stats="store.stats" />

    <!-- 筛选栏 -->
    <el-card class="filter-bar" shadow="never">
      <el-row :gutter="12" align="middle">
        <el-col :span="5">
          <el-select v-model="filters.category" placeholder="分类" clearable style="width: 100%" @change="handleFilter">
            <el-option label="全部分类" value="" />
            <el-option
              v-for="item in CATEGORY_OPTIONS"
              :key="item.value"
              :label="`${item.icon} ${item.label}`"
              :value="item.value"
            />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.taste_level" placeholder="美味等级" clearable style="width: 100%" @change="handleFilter">
            <el-option label="全部等级" value="" />
            <el-option
              v-for="[val, cfg] in tasteLevelEntries"
              :key="val"
              :label="`${cfg.icon} ${cfg.label}`"
              :value="val"
            />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-date-picker
            v-model="filters.year"
            type="year"
            value-format="YYYY"
            placeholder="年份"
            clearable
            style="width: 100%"
            @change="handleFilter"
          />
        </el-col>
        <el-col :span="8">
          <el-input
            v-model="filters.search"
            placeholder="搜索店铺、菜品、备注..."
            clearable
            @input="handleSearchInput"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="2" style="text-align: right">
          <el-button text @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 美食列表 -->
    <div v-if="store.loading" class="loading-state">
      <el-skeleton :rows="3" animated />
    </div>

    <template v-else-if="store.records.length === 0">
      <el-empty description="还没有美食记录">
        <el-button type="primary" @click="openAddDialog">+ 添加第一条记录</el-button>
      </el-empty>
    </template>

    <div v-else class="food-list">
      <div
        v-for="record in store.records"
        :key="record.id"
        class="food-card"
        @click="openEditDialog(record)"
      >
        <div class="card-cover">
          <img
            v-if="record.cover_image"
            :src="record.cover_image"
            :alt="record.name"
          />
          <div v-else class="cover-placeholder">🍽️</div>
        </div>
        <div class="card-body">
          <div class="card-header">
            <h3 class="card-name">{{ record.name }}</h3>
            <span
              class="taste-badge"
              :style="{ background: tasteColor(record.taste_level), color: '#fff' }"
            >
              {{ tasteIcon(record.taste_level) }} {{ record.taste_level_display }}
            </span>
          </div>
          <div v-if="record.dish_name" class="card-dish">{{ record.dish_name }}</div>
          <div class="card-meta">
            <span v-if="record.category_display" class="meta-tag">
              {{ categoryIcon(record.category) }} {{ record.category_display }}
            </span>
            <span class="meta-tag">📍 {{ record.city }}</span>
            <span class="meta-tag">📅 {{ record.eat_date }}</span>
          </div>
          <div class="card-footer">
            <el-rate
              v-if="record.rating"
              :model-value="record.rating"
              :max="5"
              disabled
              size="small"
            />
            <span v-if="record.price" class="card-price">¥{{ record.price }}</span>
          </div>
          <div v-if="record.notes" class="card-notes">{{ record.notes }}</div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="pagination-wrap">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="totalCount"
        layout="prev, pager, next, total"
        @current-change="handlePageChange"
      />
    </div>

    <!-- 添加/编辑弹窗 -->
    <FoodForm
      v-model="dialogVisible"
      :record="editingRecord"
      :submitting="store.submitting"
      @submit="handleSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useFoodStore } from '../stores/foodStore'
import { CATEGORY_OPTIONS, TASTE_LEVELS } from '../types/foodTypes'
import type { FoodFormData, FoodRecord, FoodRecordList } from '../types/foodTypes'
import * as foodApi from '../api/foodApi'
import FoodStatsCards from '../components/stats/FoodStatsCards.vue'
import FoodForm from '../components/FoodForm.vue'

const store = useFoodStore()

const tasteLevelEntries = Object.entries(TASTE_LEVELS)

// Filters
const filters = ref({
  category: '',
  taste_level: '',
  year: '',
  search: '',
})
let searchTimer: ReturnType<typeof setTimeout> | null = null

// Pagination
const currentPage = ref(1)
const pageSize = ref(10)
const totalCount = ref(0)
const totalPages = computed(() => Math.ceil(totalCount.value / pageSize.value))

// Dialog
const dialogVisible = ref(false)
const editingRecord = ref<FoodRecord | null>(null)

function tasteColor(level: string): string {
  return TASTE_LEVELS[level]?.color || '#6B7280'
}

function tasteIcon(level: string): string {
  return TASTE_LEVELS[level]?.icon || '😋'
}

function categoryIcon(cat: string | null): string {
  const found = CATEGORY_OPTIONS.find(c => c.value === cat)
  return found?.icon || '🍽️'
}

async function loadRecords() {
  const params: Record<string, unknown> = {
    page: currentPage.value,
    page_size: pageSize.value,
  }
  if (filters.value.category) params.category = filters.value.category
  if (filters.value.taste_level) params.taste_level = filters.value.taste_level
  if (filters.value.year) params.year = filters.value.year
  if (filters.value.search) params.search = filters.value.search

  const data = await store.fetchRecords(params)
  if (data?.count !== undefined) {
    totalCount.value = data.count
  }
}

function handleFilter() {
  currentPage.value = 1
  loadRecords()
}

function handleSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    loadRecords()
  }, 300)
}

function resetFilters() {
  filters.value = { category: '', taste_level: '', year: '', search: '' }
  currentPage.value = 1
  loadRecords()
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadRecords()
}

function openAddDialog() {
  editingRecord.value = null
  dialogVisible.value = true
}

async function openEditDialog(record: FoodRecordList) {
  try {
    const res = await foodApi.getFoodDetail(record.id)
    editingRecord.value = res.data
  } catch {
    editingRecord.value = record as any
  }
  dialogVisible.value = true
}

async function handleSubmit(data: FoodFormData) {
  try {
    if (editingRecord.value) {
      await store.updateRecord(editingRecord.value.id, data as any)
      ElMessage.success('更新成功')
    } else {
      await store.createRecord(data as any)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadRecords()
    store.fetchStats()
  } catch {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  loadRecords()
  store.fetchStats()
})
</script>

<style scoped lang="scss">
.food-dashboard {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;

  .page-title {
    display: flex;
    align-items: center;
    gap: 12px;

    .title-icon { font-size: 28px; }
    h1 { margin: 0; font-size: 24px; font-weight: 700; color: #1F2937; }
  }
}

.filter-bar {
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  margin-bottom: 20px;

  :deep(.el-card__body) { padding: 16px; }
}

.loading-state {
  padding: 40px;
}

.food-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.food-card {
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;

  &:hover {
    border-color: #3B82F6;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
    transform: translateY(-2px);
  }

  .card-cover {
    height: 160px;
    background: #F3F4F6;
    overflow: hidden;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .cover-placeholder {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 48px;
      opacity: 0.4;
    }
  }

  .card-body {
    padding: 16px;
  }

  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 4px;

    .card-name {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: #1F2937;
      flex: 1;
    }
  }

  .taste-badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .card-dish {
    font-size: 13px;
    color: #6B7280;
    margin-bottom: 8px;
  }

  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 8px;

    .meta-tag {
      font-size: 12px;
      color: #6B7280;
    }
  }

  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 4px;

    .card-price {
      font-size: 14px;
      font-weight: 600;
      color: #10B981;
    }
  }

  .card-notes {
    font-size: 12px;
    color: #9CA3AF;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
