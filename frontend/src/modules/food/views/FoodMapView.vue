<template>
  <div class="food-dashboard">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-title">
        <span class="title-icon">🍜</span>
        <h1>美食地图</h1>
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

    <div v-else class="food-grid">
      <div
        v-for="item in store.records"
        :key="item.id"
        class="food-card"
        @click="openEditDialog(item)"
      >
        <!-- 顶部图片 -->
        <div
          class="food-card__image"
          :style="item.image_url ? { backgroundImage: `url(${item.image_url})` } : {}"
        >
          <div v-if="!item.image_url" class="food-card__image--empty">
            <el-icon :size="40"><Picture /></el-icon>
          </div>
        </div>

        <!-- 底部信息 -->
        <div class="food-card__body">
          <h4 class="food-card__name">{{ item.name }}</h4>
          <p class="food-card__location">
            📍 {{ item.city }}{{ item.location ? ' ' + item.location : '' }}
          </p>
          <p class="food-card__rating">
            {{ tasteIcon(item.taste_level) }} {{ item.taste_level_display }}
          </p>
          <div class="food-card__meta">
            <span v-if="item.price != null">💰 ¥{{ item.price }}</span>
            <span v-if="item.want_visit_again">🔁 还想去</span>
          </div>
          <p v-if="item.notes" class="food-card__notes">{{ item.notes }}</p>
          <span class="food-card__date">{{ item.eat_date }}</span>
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search, Picture } from '@element-plus/icons-vue'
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

function tasteIcon(level: string): string {
  return TASTE_LEVELS[level]?.icon || '😋'
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

.food-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.food-card {
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  border: 1px solid #E5E7EB;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  }

  &__image {
    height: 160px;
    background-size: cover;
    background-position: center;
    background-color: #F3F4F6;

    &--empty {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: #D1D5DB;
    }
  }

  &__body {
    padding: 12px 16px 16px;
  }

  &__name {
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 6px;
    color: #1F2937;
  }

  &__location, &__rating, &__notes {
    font-size: 13px;
    color: #6B7280;
    margin: 0 0 4px;
  }

  &__notes {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__meta {
    display: flex;
    gap: 16px;
    font-size: 13px;
    margin: 6px 0;

    span { color: #1F2937; }
  }

  &__date {
    font-size: 11px;
    color: #9CA3AF;
    margin-top: 8px;
    display: block;
  }
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
