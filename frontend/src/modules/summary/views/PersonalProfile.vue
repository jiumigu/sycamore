<template>
  <div class="personal-profile" v-loading="loading">
    <div class="page-header">
      <div class="header-left">
        <h2>🧑 个人画像</h2>
        <el-tag size="small" type="success" effect="plain">{{ currentYear }}年</el-tag>
      </div>
      <el-select v-model="currentYear" size="small" style="width:100px" @change="fetchData">
        <el-option v-for="y in [2024, 2025, 2026]" :key="y" :label="`${y}年`" :value="y" />
      </el-select>
    </div>

    <el-alert
      v-if="dataInsufficient"
      title="部分数据不足"
      :description="dataInsufficient"
      type="warning"
      show-icon
      closable
      style="margin-bottom:16px"
    />

    <el-row :gutter="16">
      <!-- 健康 -->
      <el-col :span="12">
        <el-card shadow="hover" class="profile-card">
          <template #header><span class="card-title">🩺 身体健康</span></template>
          <div class="profile-body">
            <div class="metric-row">
              <span class="metric-label">最新健康分</span>
              <span class="metric-value" :style="{ color: scoreColor(profile?.health.latest_score) }">
                {{ profile?.health.latest_score ?? '--' }}
              </span>
            </div>
            <div class="metric-row">
              <span class="metric-label">最新体重</span>
              <span class="metric-value">{{ profile?.health.latest_weight ?? '--' }} kg</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">自查次数</span>
              <span class="metric-value">{{ profile?.health.check_count ?? 0 }} 次</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 职业能量 -->
      <el-col :span="12">
        <el-card shadow="hover" class="profile-card">
          <template #header><span class="card-title">⚡ 职业能量</span></template>
          <div class="profile-body">
            <div class="metric-row">
              <span class="metric-label">总分</span>
              <span class="metric-value" :style="{ color: energyColor(profile?.energy.latest?.total_score) }">
                {{ profile?.energy.latest?.total_score ?? '--' }}
              </span>
            </div>
            <div class="metric-row">
              <span class="metric-label">工作内容 / 环境 / 成长 / 身体</span>
              <span class="metric-value" style="font-size:13px">
                {{ profile?.energy.latest ? `${profile.energy.latest.work_score}/${profile.energy.latest.env_score}/${profile.energy.latest.growth_score}/${profile.energy.latest.body_score}` : '--' }}
              </span>
            </div>
            <div class="metric-row">
              <span class="metric-label">判定</span>
              <el-tag :type="decisionTagType(profile?.energy.latest?.decision)" size="small">
                {{ profile?.energy.latest?.decision || '暂无' }}
              </el-tag>
            </div>
            <div class="metric-row">
              <span class="metric-label">审计次数</span>
              <span class="metric-value">{{ profile?.energy.audit_count ?? 0 }} 次</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 情绪 -->
      <el-col :span="12">
        <el-card shadow="hover" class="profile-card">
          <template #header><span class="card-title">😊 情绪状态</span></template>
          <div class="profile-body">
            <div class="metric-row">
              <span class="metric-label">平均幸福感</span>
              <span class="metric-value" :style="{ color: profile?.mood.avg_happiness && profile.mood.avg_happiness >= 6 ? '#52c41a' : '#faad14' }">
                {{ profile?.mood.avg_happiness ?? '--' }} / 10
              </span>
            </div>
            <div class="metric-row">
              <span class="metric-label">小确幸记录</span>
              <span class="metric-value">{{ profile?.mood.total_records ?? 0 }} 条</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">活跃天数</span>
              <span class="metric-value">{{ profile?.mood.active_days ?? 0 }} 天</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 关系 -->
      <el-col :span="12">
        <el-card shadow="hover" class="profile-card">
          <template #header><span class="card-title">👥 人际关系</span></template>
          <div class="profile-body">
            <div class="metric-row">
              <span class="metric-label">总联系人</span>
              <span class="metric-value">{{ profile?.relation.total_relations ?? 0 }}</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">年度活跃关系</span>
              <span class="metric-value">{{ profile?.relation.active_relations ?? 0 }}</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">本年互动</span>
              <span class="metric-value">{{ profile?.relation.interactions_this_year ?? 0 }} 次</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 良品率 -->
      <el-col :span="12">
        <el-card shadow="hover" class="profile-card">
          <template #header><span class="card-title">🎯 个人良品率</span></template>
          <div class="profile-body">
            <div class="metric-row">
              <span class="metric-label">总体良品率</span>
              <span class="metric-value" :style="{ color: profile?.output.good_rate && profile.output.good_rate >= 70 ? '#52c41a' : '#faad14' }">
                {{ profile?.output.good_rate ?? '--' }}%
              </span>
            </div>
            <div class="metric-row">
              <span class="metric-label">总记录</span>
              <span class="metric-value">{{ profile?.output.total_records ?? 0 }} 条</span>
            </div>
            <div v-if="profile?.output.by_category?.length" class="category-bars">
              <div v-for="c in profile.output.by_category.slice(0, 4)" :key="c.category" class="cat-bar-row">
                <span class="cat-bar-label">{{ categoryLabel(c.category) }}</span>
                <el-progress :percentage="c.rate" :stroke-width="8" size="small" />
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 收件箱 -->
      <el-col :span="12">
        <el-card shadow="hover" class="profile-card">
          <template #header><span class="card-title">📥 收件箱状态</span></template>
          <div class="profile-body">
            <div class="metric-row">
              <span class="metric-label">待处理</span>
              <span class="metric-value" :style="{ color: (profile?.inbox.pending ?? 0) > 10 ? '#f5222d' : '#52c41a' }">
                {{ profile?.inbox.pending ?? 0 }}
              </span>
            </div>
            <div class="metric-row">
              <span class="metric-label">犹豫中</span>
              <span class="metric-value" style="color:#F59E0B">{{ profile?.inbox.hesitating ?? 0 }}</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">今年已完成</span>
              <span class="metric-value">{{ profile?.inbox.done_this_year ?? 0 }}</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">总计</span>
              <span class="metric-value">{{ profile?.inbox.total ?? 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 决策 -->
      <el-col :span="12">
        <el-card shadow="hover" class="profile-card">
          <template #header><span class="card-title">📋 决策质量</span></template>
          <div class="profile-body">
            <div class="metric-row">
              <span class="metric-label">总决策数</span>
              <span class="metric-value">{{ profile?.decision.total_decisions ?? 0 }}</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">正确率</span>
              <span class="metric-value" :style="{ color: profile?.decision.right_rate && profile.decision.right_rate >= 60 ? '#52c41a' : '#faad14' }">
                {{ profile?.decision.right_rate ?? '--' }}%
              </span>
            </div>
            <div class="metric-row">
              <span class="metric-label">正确 / 错误</span>
              <span class="metric-value">{{ profile?.decision.right_count ?? 0 }} / {{ profile?.decision.wrong_count ?? 0 }}</span>
            </div>
            <div class="metric-row">
              <span class="metric-label">已回顾</span>
              <span class="metric-value">{{ profile?.decision.reviewed_count ?? 0 }}</span>
            </div>
            <div v-if="profile?.decision.top_bias" class="metric-row">
              <span class="metric-label">常见偏误</span>
              <el-tag type="warning" size="small">{{ profile.decision.top_bias }}</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getPersonalProfile, type PersonalProfile } from '../api/profileApi'

const currentYear = ref(new Date().getFullYear())
const profile = ref<PersonalProfile | null>(null)
const loading = ref(true)

const dataInsufficient = ref('')

function scoreColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return '#9CA3AF'
  if (score >= 80) return '#52c41a'
  if (score >= 50) return '#faad14'
  return '#f5222d'
}

function energyColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return '#9CA3AF'
  if (score > 0) return '#52c41a'
  if (score > -30) return '#faad14'
  return '#f5222d'
}

function decisionTagType(decision: string | null | undefined): string {
  if (!decision) return 'info'
  if (decision.includes('增值') || decision.includes('深耕')) return 'success'
  if (decision.includes('消耗') || decision.includes('离开')) return 'danger'
  if (decision.includes('维持')) return 'warning'
  return 'info'
}

function categoryLabel(cat: string): string {
  const labels: Record<string, string> = {
    work: '工作', writing: '写作', social: '社交',
    study: '学习', health: '健康', life: '生活', other: '其他',
  }
  return labels[cat] || cat
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getPersonalProfile({ year: currentYear.value })
    profile.value = res.data as PersonalProfile
    checkData()
  } catch {
    profile.value = null
  } finally {
    loading.value = false
  }
}

function checkData() {
  const p = profile.value
  if (!p) return
  const insufficient: string[] = []
  if (p.health.check_count === 0) insufficient.push('健康自查')
  if (p.energy.audit_count === 0) insufficient.push('职业能量审计')
  if (p.mood.total_records === 0) insufficient.push('情绪记录')
  if (p.output.total_records === 0) insufficient.push('良品率记录')
  if (p.decision.total_decisions === 0) insufficient.push('决策日志')

  if (insufficient.length > 0) {
    dataInsufficient.value = `以下模块数据不足：${insufficient.join('、')}。积累更多数据后将生成更完整的画像。`
  } else {
    dataInsufficient.value = ''
  }
}

onMounted(fetchData)
</script>

<style scoped>
.personal-profile {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-left h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.profile-card {
  border: none;
  border-radius: 10px;
  margin-bottom: 16px;
}
.profile-card :deep(.el-card__body) {
  padding: 12px 16px 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
}

.profile-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.metric-label {
  font-size: 13px;
  color: #6B7280;
}
.metric-value {
  font-size: 16px;
  font-weight: 700;
  color: #1F2937;
}

.category-bars {
  margin-top: 4px;
}
.cat-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.cat-bar-label {
  font-size: 12px;
  color: #6B7280;
  width: 40px;
  flex-shrink: 0;
}
</style>
