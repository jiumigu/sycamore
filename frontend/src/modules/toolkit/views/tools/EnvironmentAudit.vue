<template>
  <div class="env-audit">
    <el-card class="audit-form" style="max-width: 100%">
      <template #header><span>🧭 环境校准</span></template>
      <p class="subtitle">六条特征，1-5分。身体不骗人，低于18分就是消耗。</p>

      <el-form :model="form">
        <el-form-item label="环境名称">
          <el-input v-model="form.environment_name" placeholder="如：公司、社群、家庭" />
        </el-form-item>

        <el-divider />

        <el-form-item label="允许说不知道">
          <el-rate v-model="form.allow_learning" :max="5" show-text
            :texts="['完全不允许','不太允许','一般','比较允许','非常允许']" />
          <span class="hint">问"这个怎么做"不会被反问"这你都不会？"</span>
        </el-form-item>

        <el-form-item label="系统能力被当资产">
          <el-rate v-model="form.system_valued" :max="5" show-text
            :texts="['被说想太多','不被理解','一般','被认可','被需要']" />
          <span class="hint">你的记录/复盘习惯被当作优点还是怪癖？</span>
        </el-form-item>

        <el-form-item label="噪音小于信号">
          <el-rate v-model="form.signal_over_noise" :max="5" show-text
            :texts="['全是噪音','噪音居多','一半一半','信号居多','全是信号']" />
          <span class="hint">沟通里有"啧""唉""你是不是不懂"吗？</span>
        </el-form-item>

        <el-form-item label="身体报警能被听见">
          <el-rate v-model="form.body_heard" :max="5" show-text
            :texts="['完全忽视','很少回应','偶尔回应','经常回应','完全尊重']" />
          <span class="hint">不舒服时能被允许休息吗？</span>
        </el-form-item>

        <el-form-item label="高手愿意分享">
          <el-rate v-model="form.people_share" :max="5" show-text
            :texts="['完全封闭','偶尔透露','一般','愿意分享','倾囊相授']" />
          <span class="hint">比你厉害的人愿意教你吗？</span>
        </el-form-item>

        <el-form-item label="输出有回路">
          <el-rate v-model="form.output_echoes" :max="5" show-text
            :texts="['石沉大海','偶尔回应','有时回应','经常回应','每次都回应']" />
          <span class="hint">你写的东西有人看、有人回应吗？</span>
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="补充感受" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleAudit">
            {{ saving ? '保存中...' : '校准' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 判定结果 -->
    <el-card v-if="result" class="audit-result" :class="resultClass">
      <div class="result-score">{{ result.total_score }} / 30</div>
      <div class="result-verdict">{{ result.verdict }}</div>
      <div class="result-advice">{{ result.advice }}</div>
    </el-card>

    <!-- 历史记录 -->
    <el-card class="section-card audit-history">
      <template #header>
        <div class="history-header">
          <span>📋 校准历史</span>
          <el-button v-if="history.length > 0" text type="danger" size="small" @click="clearAll">清空</el-button>
        </div>
      </template>
      <el-table v-if="history.length > 0" :data="history" style="width: 100%">
        <el-table-column prop="audit_date" label="日期" width="100" />
        <el-table-column prop="environment_name" label="环境" width="120" />
        <el-table-column prop="total_score" label="总分" width="70" />
        <el-table-column prop="verdict" label="判定" width="100">
          <template #default="{ row }">
            <el-tag :type="getVerdictType(row.verdict)" size="small">{{ row.verdict }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="60" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="deleteRecord(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无校准记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as toolkitApi from '../../api/toolkitApi'

interface AuditForm {
  environment_name: string
  allow_learning: number
  system_valued: number
  signal_over_noise: number
  body_heard: number
  people_share: number
  output_echoes: number
  notes: string
}

interface AuditResult {
  total_score: number
  verdict: string
  advice: string
}

interface AuditRecord {
  id: number
  environment_name: string
  audit_date: string
  total_score: number
  verdict: string
  notes: string
}

const form = reactive<AuditForm>({
  environment_name: '',
  allow_learning: 0,
  system_valued: 0,
  signal_over_noise: 0,
  body_heard: 0,
  people_share: 0,
  output_echoes: 0,
  notes: '',
})

const saving = ref(false)
const result = ref<AuditResult | null>(null)
const history = ref<AuditRecord[]>([])

function resetForm() {
  form.environment_name = ''
  form.allow_learning = 0
  form.system_valued = 0
  form.signal_over_noise = 0
  form.body_heard = 0
  form.people_share = 0
  form.output_echoes = 0
  form.notes = ''
}

function calculateVerdict(total: number): { verdict: string; advice: string; cssClass: string } {
  if (total >= 24) {
    return { verdict: '🟢 增值环境', advice: '这里让你变得更好，值得深耕。', cssClass: 'verdict-good' }
  } else if (total >= 18) {
    return { verdict: '🟡 可维持', advice: '不差，但也别待太久。找找哪些特征拖后腿。', cssClass: 'verdict-ok' }
  } else if (total >= 12) {
    return { verdict: '🟠 消耗环境', advice: '待一天就少一天能量。开始准备离开。', cssClass: 'verdict-warn' }
  }
  return { verdict: '🔴 立即离开', advice: '这里在透支你。身体已经告诉你了。', cssClass: 'verdict-danger' }
}

const resultClass = computed(() => result.value ? calculateVerdict(result.value.total_score).cssClass : '')

async function handleAudit() {
  if (!form.environment_name.trim()) {
    ElMessage.warning('请填写环境名称')
    return
  }

  // 检查六项是否都已评分（每项 > 0）
  const scores = [form.allow_learning, form.system_valued, form.signal_over_noise,
    form.body_heard, form.people_share, form.output_echoes]
  if (scores.some(s => s === 0)) {
    ElMessage.warning('请完成所有六项评分')
    return
  }

  saving.value = true
  try {
    const total = scores.reduce((a, b) => a + b, 0)
    const v = calculateVerdict(total)
    result.value = { total_score: total, ...v }

    await toolkitApi.createEnvironmentAudit({
      environment_name: form.environment_name,
      audit_date: new Date().toISOString().slice(0, 10),
      allow_learning: form.allow_learning,
      system_valued: form.system_valued,
      signal_over_noise: form.signal_over_noise,
      body_heard: form.body_heard,
      people_share: form.people_share,
      output_echoes: form.output_echoes,
      notes: form.notes,
      total_score: total,
      verdict: v.verdict,
    })

    ElMessage.success('校准完成')
    await fetchHistory()
    resetForm()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function fetchHistory() {
  try {
    const res = await toolkitApi.getEnvironmentAudits({ page_size: 100 })
    history.value = (res.data?.results ?? res.data ?? []) as AuditRecord[]
  } catch {
    history.value = []
  }
}

async function deleteRecord(id: number) {
  try {
    await toolkitApi.deleteEnvironmentAudit(id)
    ElMessage.success('已删除')
    await fetchHistory()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('确定清空所有校准历史？', '确认', { confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning' })
    for (const r of history.value) {
      await toolkitApi.deleteEnvironmentAudit(r.id)
    }
    history.value = []
    ElMessage.success('已清空')
  } catch { /* cancelled */ }
}

function getVerdictType(verdict: string): string {
  if (verdict.includes('增值')) return 'success'
  if (verdict.includes('可维持')) return 'warning'
  if (verdict.includes('消耗')) return 'warning'
  return 'danger'
}

onMounted(fetchHistory)
</script>

<style scoped>
.env-audit {
  margin: 0 auto;
  padding: 20px;
}
.subtitle {
  font-size: 13px;
  color: #9CA3AF;
  margin: 0 0 16px;
}
.hint {
  display: block;
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.audit-form {
  :deep(.el-form-item__label) {
    width: 160px;
  }
  :deep(.el-rate) {
    margin-top: 4px;
  }
}
.audit-result {
  margin-bottom: 18px;
  text-align: center;
  padding: 24px;
  border-radius: 10px;
  border: none;
}
.audit-result .result-score {
  font-size: 48px;
  font-weight: 700;
  margin-bottom: 8px;
}
.audit-result .result-verdict {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}
.audit-result .result-advice {
  font-size: 14px;
  color: #6B7280;
}
.verdict-good { background: #ecfdf5; }
.verdict-ok { background: #fffbeb; }
.verdict-warn { background: #fff7ed; }
.verdict-danger { background: #fef2f2; }
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.audit-history {
  :deep(.el-card__body) {
    padding: 16px;
  }
  :deep(.el-table) {
    width: 100%;
  }
}
</style>
