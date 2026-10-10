<template>
  <div class="snapshot-history">
    <div class="snapshot-history__header">
      <h3>盘点历史记录</h3>
    </div>

    <div class="snapshot-table-wrapper">
      <el-table :data="items" v-loading="loading" stripe size="small" style="width: 100%; white-space: nowrap;">
        <el-table-column prop="yearmon" label="年月" width="90" fixed="left" />
        <el-table-column label="支付宝" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.zplay, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="微信" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.wechat, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="现金" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.cash, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="建行" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.jianbank, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="工行" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.gongbank, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="中国银行" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.zhongbank, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="农信社" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.nongbank, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="公积金" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.accumulationfund, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="应收借出" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.lend, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="负债" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.borrow, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="流动资金" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.flow_total, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="金融资产" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.financial_assets, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="净资产" width="90" align="right" class-name="col-amount">
          <template #default="{ row }">{{ maskAmount(row.net_worth, privacyMode) }}</template>
        </el-table-column>
        <el-table-column prop="btime" label="复盘时间" width="100" />
        <el-table-column label="备注" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ maskFreeText(row.remarks, privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button size="small" @click="$emit('edit', row)">编辑</el-button>
              <el-popconfirm title="确认删除？" @confirm="$emit('delete', row.baid)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div v-if="total > pageSize" class="snapshot-history__pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        small
        layout="prev, pager, next"
        @current-change="$emit('pageChange', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SnapshotListItem } from '../../types/wealthTypes'
import { maskAmount, maskFreeText } from '@/shared/utils/privacy'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'

const props = withDefaults(defineProps<{
  items: SnapshotListItem[]
  total?: number
  page?: number
  pageSize?: number
  loading?: boolean
}>(), {
  total: 0, page: 1, pageSize: 12, loading: false,
})

defineEmits<{
  edit: [row: SnapshotListItem]
  delete: [baid: number]
  pageChange: [page: number]
}>()

const privacyStore = usePrivacyStore()
const privacyMode = computed(() => privacyStore.privacyMode)

const page = ref(props.page)
</script>

<style scoped>
.snapshot-history__header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
}
.snapshot-history__header h3 {
  margin: 0; font-size: 16px; font-weight: 600;
}
.snapshot-history__pagination {
  margin-top: 12px; display: flex; justify-content: center;
}
.snapshot-table-wrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;

  :deep(.el-table) {
    min-width: 1440px;
    white-space: nowrap;
  }

  :deep(.col-amount) {
    white-space: nowrap;
    .cell {
      white-space: nowrap;
    }
  }
}

.action-btns {
  display: flex;
  gap: 4px;
  flex-wrap: nowrap;
  white-space: nowrap;

  :deep(.el-button) {
    padding: 4px 8px;
    font-size: 12px;
    flex-shrink: 0;
  }
}
</style>
