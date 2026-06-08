<template>
  <transition name="slide">
    <div v-if="store.selectedIds.size > 0" class="batch-actions">
      <div class="batch-info">已选 {{ store.selectedIds.size }} 项</div>
      <div class="batch-buttons">
        <el-button size="small" @click="handleBatch('complete')">✅ 标记完成</el-button>
        <el-button size="small" @click="handleBatch('archive')">📦 归档</el-button>
        <el-button size="small" type="primary" @click="showConvertDialog = true">🎯 转为目标</el-button>
        <el-button size="small" type="danger" @click="handleBatch('delete')">🗑️ 删除</el-button>
      </div>
    </div>
  </transition>

  <!-- 批量转为目标对话框 -->
  <el-dialog v-model="showConvertDialog" title="🎯 批量转为目标" width="480px" :close-on-click-modal="false">
    <el-form label-position="top">
      <div class="dialog-preview">
        <div class="preview-label">将以下 {{ ids.length }} 项转为里程碑：</div>
        <div v-for="(item, i) in selectedItems" :key="item.id" class="preview-item">
          <span class="preview-index">{{ i + 1 }}.</span>
          <span class="preview-text">{{ item.content }}</span>
          <el-tag v-if="item.category" size="small">{{ item.category_display || item.category }}</el-tag>
        </div>
      </div>

      <el-form-item label="目标名称" required>
        <el-input v-model="goalName" placeholder="输入目标名称，如：2025年阅读计划" maxlength="100" />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="年份">
            <el-input-number v-model="goalYear" :min="2020" :max="2030" :step="1" controls-position="right" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="里程碑奖励（可选）">
            <el-input-number v-model="rewardPerMilestone" :min="0" :step="1" controls-position="right" style="width: 100%;" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <template #footer>
      <el-button @click="showConvertDialog = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!goalName.trim()" @click="handleConvert">
        创建目标 + {{ ids.length }} 个里程碑
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useInboxStore } from '../stores/inboxStore'

const store = useInboxStore()

const ids = computed(() => Array.from(store.selectedIds))
const selectedItems = computed(() => store.items.filter(i => store.selectedIds.has(i.id)))

const showConvertDialog = ref(false)
const goalName = ref('')
const goalYear = ref(new Date().getFullYear())
const rewardPerMilestone = ref(0)
const submitting = ref(false)

function handleBatch(action: string) {
  if (ids.value.length === 0) return
  store.batchAction({ ids: ids.value, action })
}

async function handleConvert() {
  if (!goalName.value.trim() || ids.value.length === 0) return
  submitting.value = true
  try {
    const result = await store.convertToGoal(
      ids.value,
      goalName.value.trim(),
      goalYear.value,
      rewardPerMilestone.value || undefined,
    )
    ElMessage.success(`已创建目标「${result.goal_title}」，包含 ${result.milestone_count} 个里程碑`)
    showConvertDialog.value = false
    goalName.value = ''
    rewardPerMilestone.value = 0
  } catch (e) {
    ElMessage.error('转换失败，请重试')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.slide-enter-active, .slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from, .slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
.batch-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #FEF3C7;
  border: 1px solid #FCD34D;
  border-radius: 8px;
  margin-bottom: 12px;
}
.batch-info {
  font-size: 14px;
  font-weight: 600;
  color: #92400E;
}
.batch-buttons {
  display: flex;
  gap: 8px;
}
</style>
