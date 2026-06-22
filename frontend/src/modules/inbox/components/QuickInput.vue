<template>
  <div class="quick-input">
    <div class="input-row">
      <el-input
        v-model="content"
        placeholder="💬 输入你想记住的事..."
        :disabled="store.saving"
        clearable
        @keyup.enter="handleQuickSave"
      />
      <el-button type="primary" :loading="store.saving" @click="handleQuickSave">保存</el-button>
    </div>
    <div v-if="showDetail" class="detail-row">
      <el-input
        v-model="description"
        type="textarea"
        :rows="2"
        placeholder="补充详情（可选）"
      />
    </div>
    <div class="options-row">
      <el-button size="small" link @click="showDetail = !showDetail">
        📎 {{ showDetail ? '收起详情' : '添加详情' }}
      </el-button>
      <el-select v-model="category" size="small" placeholder="类别" style="width: 100px" allow-create filterable>
        <el-option
          v-for="c in CATEGORY_OPTIONS"
          :key="c.value"
          :label="`${c.icon} ${c.label}`"
          :value="c.value"
        />
      </el-select>
      <el-select v-model="priority" size="small" placeholder="优先级" style="width: 90px">
        <el-option label="🔴 高" value="high" />
        <el-option label="🟡 中" value="medium" />
        <el-option label="🟢 低" value="low" />
      </el-select>
      <el-date-picker
        v-model="dueDate"
        type="date"
        placeholder="截止日期"
        size="small"
        style="width: 130px"
        value-format="YYYY-MM-DD"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { CATEGORY_OPTIONS } from '../types/inboxTypes'
import { useInboxStore } from '../stores/inboxStore'

const store = useInboxStore()

const content = ref('')
const description = ref('')
const category = ref('other')
const priority = ref('medium')
const dueDate = ref('')
const showDetail = ref(false)

async function handleQuickSave() {
  if (!content.value.trim()) return
  const data: Record<string, unknown> = {
    content: content.value.trim(),
    category: category.value,
    priority: priority.value,
  }
  if (description.value) data.description = description.value
  if (dueDate.value) data.due_date = dueDate.value

  await store.createItem(data)
  content.value = ''
  description.value = ''
  dueDate.value = ''
  showDetail.value = false
}
</script>

<style scoped>
.quick-input {
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}
.input-row {
  display: flex;
  gap: 8px;
}
.detail-row {
  margin-top: 8px;
}
.options-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
  align-items: center;
}
</style>
