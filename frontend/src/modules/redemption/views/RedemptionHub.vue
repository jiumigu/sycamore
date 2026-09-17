<template>
  <div class="redemption-hub">
    <el-tabs v-model="activeTab" class="rt-tabs">
      <el-tab-pane label="仪表盘" name="dashboard">
        <RedemptionDashboard />
      </el-tab-pane>
      <el-tab-pane label="归因规则" name="rules">
        <AttrRuleEditor />
      </el-tab-pane>
      <el-tab-pane label="配置" name="config">
        <el-card shadow="never" class="cfg-card">
          <template #header><span class="card-title">赎回期配置</span></template>
          <el-form label-width="110px" style="max-width: 480px">
            <el-form-item label="开始日期">
              <el-date-picker v-model="cfg.start_date" type="date" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="结束日期">
              <el-date-picker v-model="cfg.end_date" type="date" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="启动现金池">
              <el-input-number v-model="cfg.pool_principal" :min="0" :step="1000" style="width: 200px" />
              <span class="hint">（B2 口径：可中途注入）</span>
            </el-form-item>
            <el-form-item label="追踪状态">
              <el-tag :type="cfg.tracking_status === 'active' ? 'success' : 'info'">
                {{ cfg.tracking_status === 'active' ? '追踪中' : '已暂停' }}
              </el-tag>
              <span v-if="cfg.paused_since" class="hint">暂停于 {{ cfg.paused_since }}，计划恢复 {{ cfg.resume_at }}</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
              <el-button v-if="cfg.tracking_status === 'active'" @click="doPause">暂停追踪</el-button>
              <el-button v-else type="success" @click="doResume">恢复追踪</el-button>
            </el-form-item>
          </el-form>
          <el-alert
            type="warning" :closable="false" show-icon
            title="暂停≠放弃"
            description="暂停只隐藏评价与告警、保留记录能力，不影响已记录数据。低谷期用它，是活过 1096 天的必要条件。"
          />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import RedemptionDashboard from './RedemptionDashboard.vue'
import AttrRuleEditor from './AttrRuleEditor.vue'
import * as rapi from '../api/redemptionApi'
import type { RedemptionConfig } from '../types/redemptionTypes'

const activeTab = ref('dashboard')
const saving = ref(false)
const cfg = reactive({
  start_date: '',
  end_date: '',
  pool_principal: 100000,
  tracking_status: 'active' as 'active' | 'paused',
  paused_since: null as string | null,
  resume_at: null as string | null,
})

async function load() {
  try {
    const res = await rapi.getRedemption()
    Object.assign(cfg, res.data)
  } catch {
    ElMessage.error('加载配置失败')
  }
}

async function saveConfig() {
  saving.value = true
  try {
    await rapi.updateRedemption({
      start_date: cfg.start_date,
      end_date: cfg.end_date,
      pool_principal: cfg.pool_principal,
    })
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function doPause() {
  try {
    await rapi.pauseTracking()
    cfg.tracking_status = 'paused'
    await load()
    ElMessage.success('已暂停追踪')
  } catch {
    ElMessage.error('操作失败')
  }
}

async function doResume() {
  try {
    await rapi.resumeTracking()
    cfg.tracking_status = 'active'
    cfg.paused_since = null
    cfg.resume_at = null
    ElMessage.success('已恢复追踪')
  } catch {
    ElMessage.error('操作失败')
  }
}

onMounted(load)
</script>

<style scoped>
.redemption-hub { padding: 4px; }
.cfg-card { border-radius: 10px; max-width: 640px; }
.card-title { font-weight: 600; }
.hint { font-size: 12px; color: var(--el-text-color-secondary); margin-left: 8px; }
</style>
