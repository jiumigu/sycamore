<template>
  <div class="attr-rule-editor">
    <el-alert
      type="info" :closable="false" show-icon
      title="外挂归因规则"
      description="把 ATracker 任务映射到五类归因：任务名称 / 任务类型按名字精确匹配，活动类型(L2) 按 task_name 反查任务台账取得；重叠时取高优先级。规则不写进 ATracker 表，只存在于赎回模块。⚠️ 这里是规则的唯一管理口：时间统计台账里按任务名改归因写入的规则也会出现在下方列表；按 L2 活动类型 / 任务类型的规则会同时覆盖多个任务名，只能在停用或删除。优先级 0–99（台账按任务名写入的规则固定 100，高于此处手工规则）。"
    />

    <!-- 新增规则 -->
    <el-card class="block" shadow="never">
      <template #header><span class="card-title">新增规则</span></template>
      <el-form :inline="true" :model="form" class="rule-form">
        <el-form-item label="匹配字段">
          <el-select v-model="form.match_field" style="width: 190px">
            <el-option label="任务名称" value="task_name" />
            <el-option label="活动类型(L2)" value="activity_type" />
            <el-option label="任务类型(等同任务名)" value="task_type" />
          </el-select>
        </el-form-item>
        <el-form-item label="匹配值">
          <el-input v-model="form.match_value" placeholder="匹配值，需与所选维度完全相等，如：牛马工作 / 深度工作" style="width: 260px" />
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

const ATTRIBUTIONS: Attribution[] = ['成长', '关系', '维持', '谋生', '流失']
const rules = ref<AttrRule[]>([])
const saving = ref(false)

const form = reactive({
  match_field: 'task_name' as AttrField,
  match_value: '',
  attribution: '成长' as Attribution,
  priority: 0,
})

function fieldLabel(f: string) {
  return { task_name: '任务名称', activity_type: '活动类型(L2)', task_type: '任务类型(等同任务名)' }[f] || f
}
function attrStyle(a: string) {
  const m = ATTRIBUTION_META[a] || { color: '#888', bg: '#eee' }
  return { color: m.color, borderColor: m.color, backgroundColor: m.bg }
}

async function load() {
  try {
    const res = await rapi.listAttrRules()
    // ⚠️ 防御性解构：后端曾受全局分页影响，把裸数组包成 {count, results}，而这里直接当数组用
    // → `length` 得到 undefined，页面显示成「现有规则 ()」+ 空表格，**规则明明存在却看不见**
    // （2026-09-18 发现：库里 3 条真实规则被显示为 0 条）。后端已关掉该接口分页，
    // 此处仍同时兼容两种形状，避免分页配置回退时重现假 0。
    const d = res.data as unknown
    rules.value = Array.isArray(d) ? (d as AttrRule[]) : ((d as { results?: AttrRule[] })?.results || [])
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
