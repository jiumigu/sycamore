<template>
  <div class="regular-deposit">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>💰 定期存款管理</h2>
        <el-tag size="small" type="warning" effect="plain">管理银行定期存款，追踪收益和到期时间</el-tag>
      </div>
      <div class="header-actions">
        <el-button size="small" @click="store.openForm()">+ 新增存款</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <RegularStatsCards :stats="store.stats" />

    <!-- 到期提醒 -->
    <ExpiringAlert :items="store.expiringItems" @mature="handleMature" />

    <!-- 筛选栏 -->
    <RegularFilter
      v-model:bank="store.filterBank"
      v-model:flag="store.filterFlag"
      v-model:keyword="store.filterKeyword"
      :banks="store.banks"
      @change="handleFilterChange"
      @reset="handleReset"
    />

    <!-- 列表卡片 -->
    <el-card shadow="hover" class="list-card">
      <template #header>
        <div class="card-header">
          <span>📋 定期存款列表</span>
          <el-button size="small" :loading="store.loading" @click="store.fetchAll">刷新</el-button>
        </div>
      </template>
      <el-table :data="store.list" v-loading="store.loading" stripe size="small" style="width: 100%">
        <el-table-column label="银行" width="60">
          <template #default="{ row }">
            <span class="bank-name">{{ maskName(row.bankinfo || '未知', privacyStore.privacyMode) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="90" align="right">
          <template #default="{ row }">{{ maskAmount(row.value, privacyStore.privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="利率" width="60" align="right" prop="rate">
          <template #default="{ row }">{{ privacyStore.privacyMode ? '*.**%' : (row.rate ?? '-') + '%' }}</template>
        </el-table-column>
        <el-table-column label="期限" width="70" align="right" prop="term_days">
          <template #default="{ row }">{{ row.term_days }}天</template>
        </el-table-column>
        <el-table-column label="存入" width="90">
          <template #default="{ row }">{{ row.begin_date }}</template>
        </el-table-column>
        <el-table-column label="到期" width="90">
          <template #default="{ row }">{{ row.end_date }}</template>
        </el-table-column>
        <el-table-column label="利息" width="75" align="right">
          <template #default="{ row }">{{ maskAmount(row.interest, privacyStore.privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="70">
          <template #default="{ row }">
            <el-tag :type="flagType(row.flag)" size="small" effect="plain">
              {{ row.flag_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="80" show-overflow-tooltip>
          <template #default="{ row }">{{ privacyStore.privacyMode ? '***' : (row.remark || '-') }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link @click="store.openForm(row)">编辑</el-button>
            <el-button
              v-if="row.flag === 0"
              type="warning"
              size="small"
              link
              @click="handleMature(row)"
            >
              处理
            </el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!store.list.length && !store.loading" class="empty-state">
        暂无定期存款记录
      </div>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <RegularForm
      v-model:visible="store.formVisible"
      :editing="store.editingItem"
      :banks="store.banks"
      :saving="store.saving"
      @save="store.saveForm"
    />

    <!-- 到期处理弹窗 -->
    <MatureHandler
      v-model:visible="store.matureVisible"
      :item="store.matureTarget"
      :saving="store.saving"
      @save="store.processMature"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { maskName, maskAmount } from '@/shared/utils/privacy'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { useRegularStore } from '../stores/regularStore'
import RegularStatsCards from '../components/regular/RegularStatsCards.vue'
import ExpiringAlert from '../components/regular/ExpiringAlert.vue'
import RegularFilter from '../components/regular/RegularFilter.vue'
import RegularForm from '../components/regular/RegularForm.vue'
import MatureHandler from '../components/regular/MatureHandler.vue'
import type { RegularItem, ExpiringItem } from '../types/wealthTypes'

const store = useRegularStore()
const privacyStore = usePrivacyStore()

function flagType(flag: number): 'success' | 'warning' | 'info' | 'danger' | '' {
  const map: Record<number, 'success' | 'warning' | 'info'> = { 0: 'success', 1: 'warning', 2: 'info' }
  return map[flag] || 'info'
}

function handleMature(item: RegularItem | ExpiringItem) {
  store.openMature(item as RegularItem)
}

function handleFilterChange() {
  store.fetchList()
}

function handleReset() {
  store.resetFilters()
  store.fetchList()
}

async function handleDelete(row: RegularItem) {
  try {
    const delBank = maskName(row.bankinfo || '', privacyStore.privacyMode)
    const delAmount = maskAmount(row.value, privacyStore.privacyMode)
    await ElMessageBox.confirm(`确定删除 ${delBank} ${delAmount} 的定期存款记录？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await store.removeItem(row.id)
    ElMessage.success('已删除')
  } catch {
    // cancelled
  }
}

onMounted(() => {
  store.fetchAll()
})
</script>

<style scoped>
.regular-deposit {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-left h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.list-card {
  border: none;
  border-radius: 10px;
}
.list-card :deep(.el-card__body) {
  padding: 12px 16px 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
}

.bank-name {
  font-weight: 600;
  font-size: 13px;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
  color: #9CA3AF;
  font-size: 13px;
}
</style>
