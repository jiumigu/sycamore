<template>
  <div class="career-audit">
    <h2 class="page-title">⚡ 职业能量审计</h2>
    <p class="subtitle">不是"该不该走"，是"现在走到哪了"。</p>

    <el-card class="audit-form" style="max-width: 100%">
      <el-form :model="form" label-position="left" label-width="120px">
        <el-collapse v-model="activePanels">
          <!-- 工作内容本身 -->
          <el-collapse-item title="💼 工作内容本身" name="work">
            <template v-for="item in workItems" :key="item.field">
              <div class="slider-group">
                <div class="slider-label">{{ item.label }}</div>
                <div class="slider-row">
                  <span class="slider-left">{{ item.left }}</span>
                  <el-slider v-model="form[item.field]" :min="-5" :max="5" :step="1" show-stops :marks="{0:'0'}" size="small" />
                  <span class="slider-right">{{ item.right }}</span>
                </div>
              </div>
            </template>
          </el-collapse-item>

          <!-- 环境与人 -->
          <el-collapse-item title="🏢 环境与人" name="environment">
            <template v-for="item in envItems" :key="item.field">
              <div class="slider-group">
                <div class="slider-label">{{ item.label }}</div>
                <div class="slider-row">
                  <span class="slider-left">{{ item.left }}</span>
                  <el-slider v-model="form[item.field]" :min="-5" :max="5" :step="1" show-stops :marks="{0:'0'}" size="small" />
                  <span class="slider-right">{{ item.right }}</span>
                </div>
              </div>
            </template>
          </el-collapse-item>

          <!-- 成长与未来 -->
          <el-collapse-item title="📈 成长与未来" name="growth">
            <template v-for="item in growthItems" :key="item.field">
              <div class="slider-group">
                <div class="slider-label">{{ item.label }}</div>
                <div class="slider-row">
                  <span class="slider-left">{{ item.left }}</span>
                  <el-slider v-model="form[item.field]" :min="-5" :max="5" :step="1" show-stops :marks="{0:'0'}" size="small" />
                  <span class="slider-right">{{ item.right }}</span>
                </div>
              </div>
            </template>
          </el-collapse-item>

          <!-- 身体与情绪 -->
          <el-collapse-item title="🫀 身体与情绪" name="body">
            <el-form-item label="早起感受">
              <el-radio-group v-model="form.morning_feeling">
                <el-radio :value="1">期待</el-radio>
                <el-radio :value="2">平静</el-radio>
                <el-radio :value="3">无所谓</el-radio>
                <el-radio :value="4">抵触</el-radio>
                <el-radio :value="5">恐惧</el-radio>
              </el-radio-group>
            </el-form-item>
            <div v-for="item in bodySliderItems" :key="item.field" class="slider-group">
              <div class="slider-label">{{ item.label }}</div>
              <div class="slider-row">
                <span class="slider-left">{{ item.left }}</span>
                <el-slider v-model="form[item.field]" :min="1" :max="5" :step="1" size="small" />
                <span class="slider-right">{{ item.right }}</span>
              </div>
            </div>
            <el-form-item label="身体信号（多选）">
              <el-checkbox-group v-model="bodySignals">
                <el-checkbox label="失眠或早醒" />
                <el-checkbox label="胃痛/消化问题" />
                <el-checkbox label="肩颈僵硬" />
                <el-checkbox label="无故流泪" />
                <el-checkbox label="频繁生病" />
                <el-checkbox label="月牙变化" />
                <el-checkbox label="经期紊乱" />
                <el-checkbox label="不想说话" />
                <el-checkbox label="忘记照顾宠物" />
              </el-checkbox-group>
            </el-form-item>
          </el-collapse-item>
        </el-collapse>

        <el-divider />
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="补充感受或记录" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="审计日期">
              <el-date-picker v-model="form.audit_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="下次审计日期（可选）">
              <el-date-picker v-model="form.next_review_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" size="large" :loading="saving" @click="handleAudit">
            {{ saving ? '提交中...' : '提交审计' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 审计结果 -->
    <el-card v-if="result" class="audit-result" :class="resultClass">
      <div class="result-score">{{ result.total_score }} 分</div>
      <div class="result-detail">
        <span>工作 {{ result.work_score }}</span>
        <span>环境 {{ result.env_score }}</span>
        <span>成长 {{ result.growth_score }}</span>
        <span>身体 {{ result.body_score }}</span>
      </div>
      <div class="result-decision">{{ result.decision }}</div>
      <div class="result-advice">{{ result.advice }}</div>

      <!-- 环境分值连续低迷时提示环境校准 -->
      <el-alert v-if="showEnvCalibrationHint" type="warning" :closable="false" style="margin-top:12px">
        <template #title>
          ⚠️ 环境分值已连续 {{ consecutiveLowEnvMonths }} 个月拖后腿。
          要不要<a @click="goToEnvAudit" style="cursor:pointer;color:#409eff;text-decoration:underline">对当前环境做一次校准</a>？
        </template>
      </el-alert>
    </el-card>

    <!-- 历史记录 -->
    <el-card class="audit-history">
      <template #header>
        <div class="history-header">
          <span>📋 审计历史</span>
          <el-button v-if="history.length > 0" text type="danger" size="small" @click="clearAll">清空</el-button>
        </div>
      </template>
      <el-table v-if="history.length > 0" :data="history" style="width:100%">
        <el-table-column prop="audit_date" label="日期" width="110">
          <template #default="{ row }">
            <span style="white-space: nowrap">{{ row.audit_date }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="总分" width="70" />
        <el-table-column prop="decision" label="判定" width="110">
          <template #default="{ row }">
            <el-tag :type="tagType(row.total_score)" size="small">{{ row.decision }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="维度" width="180">
          <template #default="{ row }">
            工作{{ row.work_score }} 环境{{ row.env_score }} 成长{{ row.growth_score }} 身体{{ row.body_score }}
          </template>
        </el-table-column>
        <el-table-column prop="body_signals" label="身体信号" min-width="120" show-overflow-tooltip />
        <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="60" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无审计记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as toolkitApi from '../../api/toolkitApi'

// ── 定义分类项目 ──

interface AuditSliderItem {
  field: string
  label: string
  left: string
  right: string
}

const workItems: AuditSliderItem[] = [
  { field: 'task_clarity', label: '任务清晰度', left: '每天等人给活', right: '知道自己要做什么' },
  { field: 'skill_match', label: '技能匹配度', left: '总被说半吊子', right: '在能力范围内' },
  { field: 'autonomy', label: '自主决策权', left: '每个细节要请示', right: '能自己决定' },
  { field: 'achievement', label: '成就感', left: '做完也没感觉', right: '完成一件事的感觉' },
  { field: 'learning', label: '学习机会', left: '重复劳动', right: '能学到新东西' },
  { field: 'workload', label: '工作量合理性', left: '天天加班', right: '工作时间内完成' },
  { field: 'visibility', label: '结果可见性', left: '不知道有什么用', right: '能看到产出' },
]

const envItems: AuditSliderItem[] = [
  { field: 'communication', label: '沟通效率', left: '反复解释被误解', right: '一句话说清楚' },
  { field: 'transparency', label: '信息透明度', left: '突然被告知', right: '变更有通知' },
  { field: 'respect', label: '被尊重程度', left: '被敷衍啧唉', right: '意见被认真对待' },
  { field: 'feedback_quality', label: '反馈质量', left: '你是不是不懂', right: '指向具体问题' },
  { field: 'process_smooth', label: '流程顺畅度', left: '处处受阻', right: '需求不被卡' },
  { field: 'commute', label: '通勤体验', left: '消耗巨大', right: '轻松到达' },
  { field: 'physical_env', label: '物理环境', left: '不舒适', right: '舒适' },
  { field: 'colleague_relation', label: '同事关系', left: '需要防备', right: '相处融洽' },
]

const growthItems: AuditSliderItem[] = [
  { field: 'skill_growth', label: '技能成长', left: '原地踏步', right: '在提升' },
  { field: 'vision_expand', label: '视野拓展', left: '信息茧房', right: '接触新思维' },
  { field: 'resume_value', label: '履历增值', left: '纯粹耗时间', right: '对未来有帮助' },
  { field: 'income_satisfy', label: '收入满意度', left: '觉得不值', right: '匹配付出' },
  { field: 'direction', label: '方向感', left: '迷茫', right: '知道往哪走' },
]

const bodySliderItems: AuditSliderItem[] = [
  { field: 'sunday_anxiety', label: '周日焦虑', left: '完全放松', right: '极度焦虑' },
  { field: 'after_work_state', label: '下班后状态', left: '还有精力', right: '瘫倒不想动' },
  { field: 'sleep_quality', label: '睡眠质量', left: '倒头就睡', right: '失眠早醒' },
  { field: 'emotion_stability', label: '情绪波动', left: '情绪稳定', right: '经常失控' },
]

// ── 页面状态 ──

const activePanels = ref(['work', 'environment', 'growth', 'body'])
const saving = ref(false)
const result = ref<{
  total_score: number
  decision: string
  advice: string
  work_score: number
  env_score: number
  growth_score: number
  body_score: number
} | null>(null)

interface AuditRecord {
  id: number
  audit_date: string
  total_score: number
  decision: string
  notes: string
  body_signals: string
  work_score: number
  env_score: number
  growth_score: number
  body_score: number
}

const history = ref<AuditRecord[]>([])
const bodySignals = ref<string[]>([])

function defaultForm() {
  return {
    audit_date: new Date().toISOString().slice(0, 10),
    next_review_date: '',
    notes: '',
    // 工作内容
    task_clarity: 0, skill_match: 0, autonomy: 0, achievement: 0,
    learning: 0, workload: 0, visibility: 0,
    // 环境与人
    communication: 0, transparency: 0, respect: 0, feedback_quality: 0,
    process_smooth: 0, commute: 0, physical_env: 0, colleague_relation: 0,
    // 成长与未来
    skill_growth: 0, vision_expand: 0, resume_value: 0,
    income_satisfy: 0, direction: 0,
    // 身体与情绪
    morning_feeling: 3, sunday_anxiety: 3, after_work_state: 3,
    sleep_quality: 3, emotion_stability: 3,
  }
}

const form = reactive<Record<string, any>>(defaultForm())

const consecutiveLowEnvMonths = ref(0)
const router = useRouter()

const showEnvCalibrationHint = computed(() => consecutiveLowEnvMonths.value >= 3)

async function handleAudit() {
  if (!form.audit_date) {
    ElMessage.warning('请选择审计日期')
    return
  }

  saving.value = true
  try {
    const data = { ...form, body_signals: bodySignals.value.join(',') }
    // 将空字符串日期转为 null，避免 DRF 校验失败
    if (!data.next_review_date) data.next_review_date = null
    const resp = await toolkitApi.createCareerEnergyAudit(data as unknown as Record<string, unknown>)
    const d = resp.data as AuditRecord
    result.value = {
      total_score: d.total_score,
      decision: d.decision,
      advice: d.advice || '',
      work_score: d.work_score,
      env_score: d.env_score,
      growth_score: d.growth_score,
      body_score: d.body_score,
    }
    ElMessage.success('审计完成')
    await fetchHistory()
    Object.assign(form, defaultForm())
    bodySignals.value = []
  } catch {
    ElMessage.error('提交失败')
  } finally {
    saving.value = false
  }
}

async function fetchHistory() {
  try {
    const resp = await toolkitApi.getCareerEnergyAudits({ page_size: 100 })
    history.value = (resp.data?.results ?? resp.data ?? []) as AuditRecord[]

    // 计算连续环境低分月数
    let count = 0
    for (const record of history.value) {
      if (record.env_score < 0) {
        count++
      } else {
        break
      }
    }
    consecutiveLowEnvMonths.value = count
  } catch {
    history.value = []
  }
}

function goToEnvAudit() {
  router.push('/toolkit/environment-audit')
}

async function handleDelete(id: number) {
  try {
    await toolkitApi.deleteCareerEnergyAudit(id)
    ElMessage.success('已删除')
    await fetchHistory()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('确定清空所有审计记录？', '确认', {
      confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning',
    })
    for (const r of history.value) {
      await toolkitApi.deleteCareerEnergyAudit(r.id)
    }
    history.value = []
    ElMessage.success('已清空')
  } catch { /* cancelled */ }
}

function tagType(score: number): string {
  if (score >= 40) return 'success'
  if (score >= 10) return 'warning'
  return 'danger'
}

const resultClass = computed(() => {
  if (!result.value) return ''
  if (result.value.total_score >= 40) return 'verdict-good'
  if (result.value.total_score >= 10) return 'verdict-ok'
  if (result.value.total_score >= -20) return 'verdict-warn'
  return 'verdict-danger'
})

onMounted(fetchHistory)
</script>

<style scoped>
.career-audit {
  width: 100%;
  padding: 20px;
}
.page-title {
  font-size: 22px; font-weight: 700; margin: 0 0 4px;
}
.subtitle {
  font-size: 13px; color: #9CA3AF; margin: 0 0 20px;
}
.audit-form {
  margin-bottom: 18px;
}
.audit-form :deep(.el-form-item__label) {
  width: 120px;
}
.audit-form :deep(.el-slider) {
  width: 100%;
}
:deep(.el-table__cell) {
  white-space: nowrap;
}
.audit-form :deep(.el-collapse-item__header) {
  font-weight: 600;
  font-size: 15px;
}
.slider-group {
  margin-bottom: 18px;
}
.slider-label {
  font-size: 14px; font-weight: 500; color: #374151; margin-bottom: 6px;
}
.slider-row {
  display: flex; align-items: center; gap: 12px;
}
.slider-left, .slider-right {
  font-size: 11px; color: #9CA3AF; white-space: nowrap; min-width: 80px;
  flex-shrink: 0;
}
.slider-right {
  text-align: right;
}
.slider-row :deep(.el-slider) {
  flex: 1;
}
:deep(.el-checkbox-group) {
  display: flex; flex-wrap: wrap; gap: 8px;
}
:deep(.el-checkbox) {
  margin-right: 0; min-width: 130px;
}

/* 结果卡片 */
.audit-result {
  margin-bottom: 18px; text-align: center; padding: 24px 20px;
  border-radius: 10px; border: none;
}
.result-score {
  font-size: 48px; font-weight: 700; line-height: 1;
}
.result-detail {
  display: flex; justify-content: center; gap: 24px; margin: 16px 0;
  font-size: 16px; font-weight: 500;
  color: #6B7280;
}
.result-detail span:nth-child(1) { color: #3B82F6; }
.result-detail span:nth-child(2) { color: #10B981; }
.result-detail span:nth-child(3) { color: #8B5CF6; }
.result-detail span:nth-child(4) { color: #F59E0B; }
.result-decision {
  font-size: 24px; font-weight: 600; margin: 8px 0;
}
.result-advice {
  font-size: 14px; color: #6B7280; line-height: 1.6;
  white-space: pre-wrap;
}
.verdict-good { background: #ecfdf5; }
.verdict-ok { background: #fffbeb; }
.verdict-warn { background: #fff7ed; }
.verdict-danger { background: #fef2f2; }

/* 历史记录 */
.audit-history {
  :deep(.el-card__body) { padding: 16px; }
}
.history-header {
  display: flex; justify-content: space-between; align-items: center;
}
</style>
