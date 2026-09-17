<template>
  <div class="mapping-editor">
    <div class="page-header">
      <h2>🧩 分类映射编辑器</h2>
      <el-tag type="info" size="small">L1 归因 / L2 类型 / L3 task_name</el-tag>
    </div>

    <el-alert type="warning" :closable="false" show-icon class="hint-alert">
      <template #title>未归类任务不参与记录完整度计算</template>
      左侧「未归类池」中的 task_name 未命中系统预设，请为其指定 <b>L2 活动类型</b>；若带价值归因，可一并指定 <b>L1 归因</b>（会自动写入赎回期归因规则）。
    </el-alert>

    <el-row :gutter="16" class="editor-row">
      <!-- 左：未归类任务池 -->
      <el-col :span="14">
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>📥 未归类任务池（{{ unclassified.items.length }}）</span>
              <el-button size="small" text type="primary" @click="loadPool">刷新</el-button>
            </div>
          </template>
          <div class="pool-list">
            <div
              v-for="item in unclassified.items"
              :key="item.task_name"
              class="pool-item"
              :class="{ selected: selected.has(item.task_name) }"
              @click="toggleSelect(item.task_name)"
            >
              <el-checkbox :model-value="selected.has(item.task_name)" @click.stop @change="toggleSelect(item.task_name)" />
              <span class="pool-name">{{ item.task_name }}</span>
              <span class="pool-meta">{{ item.total_hours.toFixed(1) }}h · {{ item.record_count }}次</span>
            </div>
            <el-empty v-if="!unclassified.items.length" description="全部已归类 🎉" :image-size="60" />
          </div>
        </el-card>
      </el-col>

      <!-- 右：批量设 L2 类型 + L1 归因 -->
      <el-col :span="10">
        <el-card class="panel-card" shadow="never">
          <template #header><span>⚙️ 批量设置（已选 {{ selected.size }}）</span></template>
          <el-form label-width="96px" size="small">
            <el-form-item label="L2 活动类型" required>
              <el-select v-model="form.activity_type" placeholder="选择活动类型" style="width:100%">
                <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
              </el-select>
            </el-form-item>
            <el-form-item label="L1 价值归因">
              <el-select v-model="form.attribution" placeholder="不选=按类型默认" clearable style="width:100%">
                <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="a" :value="a" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :disabled="!selected.size || !form.activity_type" :loading="saving" @click="applyBatch">
                应用到已选任务
              </el-button>
              <el-button @click="selected.clear()">清空选择</el-button>
            </el-form-item>
          </el-form>
          <el-divider />
          <div class="selected-tags">
            <el-tag v-for="n in Array.from(selected)" :key="n" size="small" closable @close="toggleSelect(n)" style="margin:2px">
              {{ n }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useTemporalStore } from '../stores/temporalStore'
import { ACTIVITY_TYPE_OPTIONS, ATTRIBUTION_OPTIONS } from '../types/temporalTypes'

const store = useTemporalStore()
const { unclassified } = storeToRefs(store)

const selected = reactive(new Set<string>())
const form = reactive<{ activity_type: string; attribution: string | null }>({
  activity_type: '', attribution: null,
})
const saving = ref(false)

async function loadPool() {
  await store.loadUnclassified()
}

function toggleSelect(name: string) {
  if (selected.has(name)) selected.delete(name)
  else selected.add(name)
}

async function applyBatch() {
  if (!selected.size || !form.activity_type) return
  saving.value = true
  try {
    const res = await store.batchSetMeta({
      task_names: Array.from(selected),
      activity_type: form.activity_type,
      attribution: form.attribution || null,
    })
    ElMessage.success(`已更新 ${res.updated} 个任务${form.attribution ? '（含归因规则）' : ''}`)
    selected.clear()
    await loadPool()
  } catch { ElMessage.error('应用失败') } finally { saving.value = false }
}

onMounted(async () => {
  await loadPool()
})
</script>

<style scoped lang="scss">
.mapping-editor { padding: 20px; background: #F5F7FA; min-height: 100vh;
  .page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px;
    h2 { margin: 0; font-size: 20px; } }
  .hint-alert { margin-bottom: 14px; }
  .editor-row { align-items: stretch; }
  .panel-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); height: 100%;
    :deep(.el-card__header) { padding: 12px 16px; font-size: 14px; font-weight: 500; } }
  .panel-header { display: flex; justify-content: space-between; align-items: center; }
  .pool-list { max-height: 60vh; overflow: auto;
    .pool-item { display: flex; align-items: center; gap: 8px; padding: 7px 6px; border-radius: 6px; cursor: pointer;
      &:hover { background: #f3f4f6; }
      &.selected { background: #eef2ff; }
      .pool-name { flex: 1; font-size: 13px; }
      .pool-meta { font-size: 11px; color: #9ca3af; } } }
  .selected-tags { max-height: 200px; overflow: auto; }
}
</style>
