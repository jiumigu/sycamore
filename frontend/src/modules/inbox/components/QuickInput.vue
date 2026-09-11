<template>
  <div class="quick-input">
    <div class="input-row">
      <el-input
        v-model="content"
        class="main-input"
        placeholder="💬 输入你想记住的事..."
        :disabled="store.saving"
        clearable
        @keyup.enter="handleQuickSave"
      />
      <el-button type="primary" size="large" class="save-btn" :loading="store.saving" @click="handleQuickSave">保存</el-button>
    </div>
    <div v-if="showDetail" class="detail-row">
      <el-input
        v-model="description"
        type="textarea"
        :rows="3"
        placeholder="补充详情（可选）"
      />
    </div>
    <div class="options-row">
      <el-button size="default" link @click="showDetail = !showDetail">
        📎 {{ showDetail ? '收起详情' : '添加详情' }}
      </el-button>
      <el-select v-model="category" size="default" placeholder="类别" style="width: 120px" allow-create filterable>
        <el-option
          v-for="c in CATEGORY_OPTIONS"
          :key="c.value"
          :label="`${c.icon} ${c.label}`"
          :value="c.value"
        />
      </el-select>
      <el-select v-model="priority" size="default" placeholder="优先级" style="width: 110px">
        <el-option label="🔴 高" value="high" />
        <el-option label="🟡 中" value="medium" />
        <el-option label="🟢 低" value="low" />
      </el-select>
      <el-date-picker
        v-model="dueDate"
        type="date"
        placeholder="截止日期"
        size="default"
        style="width: 150px"
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
  padding: 20px;
  margin-bottom: 16px;
}
.input-row {
  display: flex;
  gap: 10px;
}
.main-input {
  flex: 1;
}
.main-input :deep(.el-input__wrapper) {
  padding: 1px 15px;
}
.main-input :deep(.el-input__inner) {
  height: 38px;
  font-size: 15px;
}
.save-btn {
  height: 40px;
  min-width: 88px;
  font-size: 15px;
}
.detail-row {
  margin-top: 10px;
}
.options-row {
  display: flex;
  gap: 10px;
  margin-top: 10px;
  flex-wrap: wrap;
  align-items: center;
}
</style>
