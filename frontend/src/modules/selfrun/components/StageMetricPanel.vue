<template>
  <div class="sm-wrap">
    <el-card shadow="never">
      <template #header>
        <div class="sm-head">
          <span class="sm-title">本阶段 KPI（即时生效）</span>
          <span class="sm-hint">
            改目标 / 底线**立刻生效，且从现在起一直用它** —— 想只改某一期，去右侧「按期修订」。
            往期是快照，改的是以后。
          </span>
        </div>
      </template>

      <el-table :data="store.metrics" size="small" empty-text="还没有 KPI">
        <el-table-column prop="name" label="KPI" min-width="120" />
        <el-table-column label="周期" width="56">
          <template #default="{ row }">{{ row.period_type === 'weekly' ? '周' : '月' }}</template>
        </el-table-column>
        <el-table-column label="目标 / 底线" width="150">
          <template #default="{ row }">
            {{ fmt(row.goal_value, row.unit) }} / {{ fmt(row.floor_value, row.unit) }}
          </template>
        </el-table-column>
        <el-table-column label="口径" min-width="150">
          <template #default="{ row }">
            {{ SOURCE_KIND_LABEL[row.source_kind] ?? row.source_kind }} · {{ AGG_LABEL[row.agg] ?? row.agg }}
            <div v-if="row.template_key" class="sm-sub">来源模板：{{ row.template_key }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'" effect="plain">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openEdit(row)">改</el-button>
            <el-button
              v-if="row.status === 'active'" size="small" text type="danger"
              @click="doRetire(row)"
            >
              退役
            </el-button>
            <el-button v-else size="small" text type="success" @click="doRevive(row)">恢复</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="sm-note">
        「退役」= 这条**永久**不要了（历史读数保留）。
        「这周先不算」在「本周状态」页里勾（只影响这一期）。
        「整个阶段歇一阵」用页头的「暂停阶段」。
        「只改某一期」点右侧「按期修订」；「谁在什么时候改过」点右侧「配置变更留痕」。
        **四处作用域不同，别混。**
      </div>
    </el-card>

    <!-- 单条 KPI 改配置（改完立刻生效，且以后都用新值） -->
    <MetricConfigDialog v-model="editVisible" :metric="editing" @saved="emit('changed')" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MetricConfigDialog from './MetricConfigDialog.vue'
import { useSelfRunStore } from '../stores/selfrunStore'
import { AGG_LABEL, SOURCE_KIND_LABEL, fmt } from '../types/selfrunTypes'
import type { SelfRunMetric } from '../types/selfrunTypes'

const emit = defineEmits<{ (e: 'changed'): void }>()

const store = useSelfRunStore()
const editVisible = ref(false)
const editing = ref<SelfRunMetric | null>(null)

function openEdit(m: SelfRunMetric) {
  editing.value = m
  editVisible.value = true
}

async function doRetire(m: SelfRunMetric) {
  try {
    const r = await ElMessageBox.prompt(
      `「${m.name}」以后不再统计。历史读数会保留，往期结论不变。写一下原因（可空）。`,
      '退役这条 KPI？',
      { confirmButtonText: '退役', cancelButtonText: '算了', inputPlaceholder: '可选' },
    )
    await store.retireMetric(m.id, r.value || '')
    ElMessage.success('已退役')
    emit('changed')
  } catch (e: any) {
    if (e === 'cancel' || e?.message === 'cancel') return
    ElMessage.error(e?.response?.data?.detail ?? '操作失败')
  }
}

async function doRevive(m: SelfRunMetric) {
  try {
    await store.reviveMetric(m.id, '')
    ElMessage.success('已恢复')
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '操作失败')
  }
}
</script>

<style scoped>
.sm-wrap { display: flex; flex-direction: column; gap: 12px; }
.sm-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.sm-title { font-weight: 600; }
.sm-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }
.sm-sub { font-size: 12px; color: var(--el-text-color-secondary); }
.sm-note { margin-top: 8px; font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.8; }
</style>
