<template>
  <div class="attr-rule-editor">
    <el-alert
      type="info" :closable="false" show-icon
      title="外挂归因规则"
      description="把 ATracker 任务（按 任务类型 / 任务名称 / 二级分类）映射到四类归因。重叠时取高优先级。ATracker 表不在此加列，规则只存在于赎回模块。"
    />

    <!-- 新增规则 -->
    <el-card class="block" shadow="never">
      <template #header><span class="card-title">新增规则</span></template>
      <el-form :inline="true" :model="form" class="rule-form">
        <el-form-item label="匹配字段">
          <el-select v-model="form.match_field" style="width: 130px">
            <el-option label="任务类型" value="task_type" />
            <el-option label="任务名称" value="task_name" />
            <el-option label="二级分类" value="category_level2" />
          </el-select>
        </el-form-item>
        <el-form-item label="匹配值">
          <el-input v-model="form.match_value" placeholder="如：阅读思考 / 牛马工作 / 刷手机空转" style="width: 200px" />
        </el-form-item>
        <el-form-item label="归因">
          <el-select v-model="form.attribution" style="width: 130px">
            <el-option v-for="a in ATTRIBUTIONS" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="0" :max="99" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="addRule">添加</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 规则列表 -->
    <el-card class="block" shadow="never">
      <template #header><span class="card-title">现有规则（{{ rules.length }}）</span></template>
      <el-table :data="rules" size="small" stripe>
        <el-table-column label="匹配字段" width="110">
          <template #default="{ row }">{{ fieldLabel(row.match_field) }}</template>
        </el-table-column>
        <el-table-column prop="match_value" label="匹配值" min-width="140" />
        <el-table-column label="归因" width="100">
          <template #default="{ row }">
            <el-tag :style="attrStyle(row.attribution)" size="small" effect="plain">{{ row.attribution }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="(v: boolean) => toggleActive(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="danger" @click="removeRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as rapi from '../api/redemptionApi'
import type { AttrRule, AttrField, Attribution } from '../types/redemptionTypes'
import { ATTRIBUTION_META } from '../types/redemptionTypes'

const ATTRIBUTIONS: Attribution[] = ['投向', '维持', '外部', '流失']
const rules = ref<AttrRule[]>([])
const saving = ref(false)

const form = reactive({
  match_field: 'task_type' as AttrField,
  match_value: '',
  attribution: '投向' as Attribution,
  priority: 0,
})

function fieldLabel(f: string) {
  return { task_type: '任务类型', task_name: '任务名称', category_level2: '二级分类' }[f] || f
}
function attrStyle(a: string) {
  const m = ATTRIBUTION_META[a] || { color: '#888', bg: '#eee' }
  return { color: m.color, borderColor: m.color, backgroundColor: m.bg }
}

async function load() {
  try {
    const res = await rapi.listAttrRules()
    rules.value = (res.data as AttrRule[]) || []
  } catch {
    ElMessage.error('加载规则失败')
  }
}

async function addRule() {
  if (!form.match_value.trim()) {
    ElMessage.warning('请填写匹配值')
    return
  }
  saving.value = true
  try {
    await rapi.createAttrRule({ ...form, match_value: form.match_value.trim() })
    ElMessage.success('已添加')
    form.match_value = ''
    await load()
  } catch {
    ElMessage.error('添加失败')
  } finally {
    saving.value = false
  }
}

async function toggleActive(row: AttrRule, v: boolean) {
  try {
    await rapi.updateAttrRule(row.id, { is_active: v })
  } catch {
    row.is_active = !v
    ElMessage.error('更新失败')
  }
}

async function removeRule(row: AttrRule) {
  try {
    await ElMessageBox.confirm(`删除规则：${fieldLabel(row.match_field)} = ${row.match_value}？`, '确认', { type: 'warning' })
    await rapi.deleteAttrRule(row.id)
    ElMessage.success('已删除')
    await load()
  } catch { /* 取消 */ }
}

onMounted(load)
</script>

<style scoped>
.attr-rule-editor { display: flex; flex-direction: column; gap: 14px; }
.block { border-radius: 10px; }
.card-title { font-weight: 600; }
.rule-form { display: flex; flex-wrap: wrap; gap: 4px; }
</style>
