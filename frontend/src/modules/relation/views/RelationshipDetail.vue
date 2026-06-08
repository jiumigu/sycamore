<template>
  <div class="relation-detail">
    <!-- 返回 -->
    <div class="back-bar">
      <el-button text @click="$router.push('/relation')">
        <el-icon><ArrowLeft /></el-icon> 返回列表
      </el-button>
    </div>

    <div v-loading="loading">
      <!-- 关系档案卡片 -->
      <el-card class="profile-card" v-if="relationship">
        <div class="profile-header">
          <div class="avatar" :style="{ background: qualityColor }">
            {{ relationship.name.charAt(0) }}
          </div>
          <div class="profile-info">
            <div class="profile-name">{{ maskName(relationship.name, privacyStore.privacyMode) }}</div>
            <div class="profile-alias" v-if="relationship.alias">又名 {{ maskName(relationship.alias, privacyStore.privacyMode) }}</div>
            <div class="profile-meta">
              <el-tag :type="relationTagType" effect="dark" size="small">{{ relationTypeLabel }}</el-tag>
              <el-tag :type="statusTagType" effect="plain" size="small">{{ statusLabel }}</el-tag>
            </div>
          </div>
          <div class="profile-actions">
            <el-button @click="openEdit">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button type="danger" @click="handleDelete">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </div>
        </div>

        <div class="profile-stats">
          <div class="stat-item">
            <div class="stat-num">{{ relationship.interaction_count }}</div>
            <div class="stat-lbl">互动次数</div>
          </div>
          <div class="stat-item">
            <div class="stat-num" :style="{ color: relationship.avg_energy !== null && relationship.avg_energy >= 0 ? '#10B981' : '#EF4444' }">
              {{ relationship.avg_energy !== null ? (relationship.avg_energy > 0 ? '+' : '') + relationship.avg_energy : '-' }}
            </div>
            <div class="stat-lbl">平均能量 (分/次)</div>
          </div>
          <div class="stat-item">
            <div class="stat-num">{{ relationship.last_interaction ? formatTime(relationship.last_interaction) : '-' }}</div>
            <div class="stat-lbl">最近互动</div>
          </div>
        </div>

        <el-divider />

        <!-- 相识信息 -->
        <div class="info-grid">
          <div class="info-item" v-if="relationship.met_date">
            <span class="label">📅 认识时间</span>
            <span class="value">{{ relationship.met_date }}</span>
          </div>
          <div class="info-item" v-if="relationship.met_place">
            <span class="label">📍 认识地点</span>
            <span class="value">{{ maskLocation(relationship.met_place, privacyStore.privacyMode) }}</span>
          </div>
          <div class="info-item" v-if="relationship.identity_then">
            <span class="label">🏷️ 当时身份</span>
            <span class="value">{{ maskText(relationship.identity_then, privacyStore.privacyMode) }}</span>
          </div>
        </div>

        <div class="info-section" v-if="relationship.met_scene">
          <div class="info-section-label">🌊 认识场景</div>
          <div class="info-section-content">{{ maskText(relationship.met_scene, privacyStore.privacyMode) }}</div>
        </div>

        <el-row :gutter="16" class="give-row">
          <el-col :span="12" v-if="relationship.they_give_me">
            <div class="give-card give-in">
              <div class="give-title">← 他能给我</div>
              <div class="give-content">{{ privacyStore.privacyMode ? '***' : relationship.they_give_me }}</div>
            </div>
          </el-col>
          <el-col :span="12" v-if="relationship.i_give_them">
            <div class="give-card give-out">
              <div class="give-title">→ 我能给他</div>
              <div class="give-content">{{ privacyStore.privacyMode ? '***' : relationship.i_give_them }}</div>
            </div>
          </el-col>
        </el-row>

        <div class="info-section" v-if="relationship.notes">
          <div class="info-section-label">📝 备注</div>
          <div class="info-section-content">{{ privacyStore.privacyMode ? '***' : relationship.notes }}</div>
        </div>

        <div class="info-section" v-if="relationship.tags">
          <div class="info-section-label">🏷️ 标签</div>
          <div class="tags-wrap">
            <el-tag v-for="tag in tagList" :key="tag" size="small" round>{{ privacyStore.privacyMode ? '***' : tag }}</el-tag>
          </div>
        </div>

        <el-divider />

        <!-- 付出/获得对比 -->
        <div class="give-take-comparison">
          <div class="compare-item give">
            <div class="compare-num">{{ giveTakeStats.myActionCount }}</div>
            <div class="compare-lbl">我付出的行动数</div>
          </div>
          <div class="compare-divider"></div>
          <div class="compare-item take">
            <div class="compare-num" :class="relationship.total_energy >= 0 ? 'positive' : 'negative'">
              {{ relationship.total_energy > 0 ? '+' : '' }}{{ relationship.total_energy }}
            </div>
            <div class="compare-lbl">获得的能量分</div>
          </div>
        </div>
      </el-card>

      <!-- 图表区域 -->
      <el-card class="section-card">
        <template #header><span>📈 能量趋势 & 互动频率</span></template>
        <el-row :gutter="16">
          <el-col :span="12">
            <div ref="energyChartRef" class="chart-box"></div>
          </el-col>
          <el-col :span="12">
            <div ref="frequencyChartRef" class="chart-box"></div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 互动时间线 -->
      <el-card class="section-card">
        <template #header>
          <div class="section-header">
            <span>💬 互动记录（{{ interactions.length }}）</span>
            <el-button type="primary" size="small" @click="openAddInteraction">
              <el-icon><Plus /></el-icon> 添加互动
            </el-button>
          </div>
        </template>

        <div v-if="interactions.length === 0" class="empty-timeline">
          <el-empty description="暂无互动记录" />
        </div>

        <div v-else class="timeline">
          <div v-for="item in interactions" :key="item.id" class="timeline-item">
            <div class="timeline-dot" :style="{ background: energyScoreColor(item.energy_score) }"></div>
            <div class="timeline-content">
              <div class="timeline-header">
                <span class="timeline-date">{{ formatTime(item.happened_at) }}</span>
                <el-tag size="small" effect="plain">{{ item.method_label || item.method }}</el-tag>
                <span class="timeline-energy" :style="{ color: energyScoreColor(item.energy_score) }">
                  {{ item.energy_score > 0 ? '+' : '' }}{{ item.energy_score }}
                </span>
                <span class="timeline-energy-label">{{ item.energy_label }}</span>
                <el-tag v-if="item.quality_shift_label" size="small" :type="shiftTagType(item.quality_shift)" effect="plain">
                  {{ item.quality_shift_label }}
                </el-tag>
              </div>
              <div class="timeline-summary" v-if="item.summary">{{ item.summary }}</div>
              <div class="timeline-my-action" v-if="item.my_action">
                <el-icon><Promotion /></el-icon> {{ item.my_action }}
              </div>
              <div class="timeline-actions">
                <el-button size="small" text @click="openEditInteraction(item)">编辑</el-button>
                <el-button size="small" text type="danger" @click="handleDeleteInteraction(item)">删除</el-button>
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 编辑关系弹窗 -->
    <el-dialog v-model="formVisible" :title="'编辑关系 - ' + maskName(relationship?.name || '', privacyStore.privacyMode)" width="560px" @close="resetForm">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="姓名" prop="name">
              <el-input v-model="formData.name" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="别名">
              <el-input v-model="formData.alias" maxlength="200" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="认识时间">
              <el-date-picker v-model="formData.met_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" style="width:100%" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="认识地点">
              <el-input v-model="formData.met_place" maxlength="200" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="认识场景">
          <el-input v-model="formData.met_scene" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="当时身份">
              <el-input v-model="formData.identity_then" maxlength="200" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="当前状态" prop="current_status">
              <el-select v-model="formData.current_status" style="width:100%">
                <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="他能给我">
              <el-input v-model="formData.they_give_me" type="textarea" :rows="2" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="我能给他">
              <el-input v-model="formData.i_give_them" type="textarea" :rows="2" maxlength="500" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标签">
          <el-input v-model="formData.tags" maxlength="200" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.notes" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleEditSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑互动弹窗 -->
    <el-dialog v-model="interactionFormVisible" :title="isEditInteraction ? '编辑互动' : '💬 添加互动'" width="500px" @close="resetInteractionForm">
      <el-form ref="interactionFormRef" :model="interactionForm" :rules="interactionRules" label-width="100px">
        <el-form-item label="互动时间" prop="happened_at">
          <el-date-picker v-model="interactionForm.happened_at" type="datetime" placeholder="选择时间"
            format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
        </el-form-item>

        <el-form-item label="互动方式" prop="method">
          <el-select v-model="interactionForm.method" style="width:100%">
            <el-option v-for="m in METHOD_OPTIONS" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="能量分" prop="energy_score">
          <div class="energy-slider-wrap">
            <el-slider v-model="interactionForm.energy_score" :min="-10" :max="10" :step="1" show-stops
              :marks="energyMarks" />
            <div class="energy-preview" :style="{ color: energyScoreColor(interactionForm.energy_score) }">
              {{ interactionForm.energy_score > 0 ? '+' : '' }}{{ interactionForm.energy_score }}
              · {{ energyLabel(interactionForm.energy_score) }}
            </div>
          </div>
        </el-form-item>

        <el-form-item label="质量变化" prop="quality_shift">
          <el-select v-model="interactionForm.quality_shift" style="width:100%">
            <el-option v-for="s in SHIFT_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="一句话总结">
          <el-input v-model="interactionForm.summary" maxlength="200" placeholder="这次互动感觉如何..." />
        </el-form-item>

        <el-form-item label="下次提醒">
          <el-input v-model="interactionForm.next_reminder" maxlength="200" placeholder="下次可以做什么..." />
        </el-form-item>

        <el-form-item label="我为对方做了什么">
          <el-input v-model="interactionForm.my_action" type="textarea" :rows="2"
            placeholder="我主动为对方做了什么？" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="interactionFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingInteraction" @click="handleInteractionSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Plus, Edit, Delete, Promotion } from '@element-plus/icons-vue'
import { maskName, maskLocation, maskText } from '@/shared/utils/privacy'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { QUALITY_CONFIG, STATUS_OPTIONS, METHOD_OPTIONS, SHIFT_OPTIONS, RELATION_TYPE_LABELS, RELATION_TYPE_TAG, energyLabel } from '../types/relationshipTypes'
import type { Relationship, Interaction } from '../types/relationshipTypes'
import * as api from '../api/relationshipApi'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()
const relationshipId = computed(() => Number(route.params.id))

const privacyStore = usePrivacyStore()
const relationship = ref<Relationship | null>(null)
const interactions = ref<Interaction[]>([])
const loading = ref(false)

// Computed
const qualityColor = computed(() => {
  if (!relationship.value) return '#9CA3AF'
  return QUALITY_CONFIG[relationship.value.relation_type]?.color || '#9CA3AF'
})

const statusTagType = computed(() => {
  const s = relationship.value?.current_status
  if (s === 'active') return 'success' as const
  if (s === 'distant') return 'warning' as const
  if (s === 'paused') return 'info' as const
  return 'danger' as const
})

const statusLabel = computed(() => {
  return STATUS_OPTIONS.find(s => s.value === relationship.value?.current_status)?.label || ''
})

const relationTypeLabel = computed(() => {
  return RELATION_TYPE_LABELS[relationship.value?.relation_type || ''] || ''
})

const relationTagType = computed(() => {
  return RELATION_TYPE_TAG[relationship.value?.relation_type || ''] || 'info'
})

const tagList = computed(() => {
  if (!relationship.value?.tags) return []
  return relationship.value.tags.split(/[,，、]/).filter(Boolean).map(t => t.trim())
})

const giveTakeStats = computed(() => {
  const myActionCount = interactions.value.filter(i => i.my_action).length
  return { myActionCount }
})

// Charts
const energyChartRef = ref<HTMLElement>()
const frequencyChartRef = ref<HTMLElement>()
let energyChart: echarts.ECharts | null = null
let frequencyChart: echarts.ECharts | null = null

// Relationship form
const formVisible = ref(false)
const submitting = ref(false)
const formRef = ref()
const formData = ref({
  name: '', alias: '', met_date: null as string | null, met_place: '',
  met_scene: '', identity_then: '', they_give_me: '', i_give_them: '',
  current_status: 'active', notes: '', tags: '',
})
const formRules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  current_status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

// Interaction form
const interactionFormVisible = ref(false)
const isEditInteraction = ref(false)
const editingInteractionId = ref<number | null>(null)
const submittingInteraction = ref(false)
const interactionFormRef = ref()
const interactionForm = ref({
  relationship: 0,
  happened_at: '',
  method: 'meet',
  energy_score: 5,
  quality_shift: 'same',
  summary: '',
  next_reminder: '',
  my_action: '',
})
const interactionRules = {
  happened_at: [{ required: true, message: '请选择时间', trigger: 'change' }],
  method: [{ required: true, message: '请选择方式', trigger: 'change' }],
  energy_score: [{ required: true, message: '请评分', trigger: 'blur' }],
}

const energyMarks = computed(() => {
  const m: Record<number, string> = {}
  for (let i = -10; i <= 10; i += 5) {
    m[i] = i > 0 ? `+${i}` : `${i}`
  }
  return m
})

// Helpers
function formatTime(t: string | undefined | null): string {
  if (!t) return '-'
  return t.slice(0, 16).replace('T', ' ')
}

function energyScoreColor(score: number): string {
  if (score > 0) return '#10B981'
  if (score === 0) return '#9CA3AF'
  return '#EF4444'
}

function shiftTagType(shift: string): 'success' | 'danger' | 'info' {
  if (shift === 'improved') return 'success'
  if (shift === 'declined') return 'danger'
  return 'info'
}

// Data fetching
async function fetchDetail() {
  loading.value = true
  try {
    const [relRes, intRes] = await Promise.all([
      api.getRelationshipDetail(relationshipId.value),
      api.getInteractionList({ relationship: relationshipId.value }),
    ])
    relationship.value = relRes.data
    interactions.value = Array.isArray(intRes.data) ? intRes.data : (intRes.data.results || [])
    return true
  } catch (e: any) {
    ElMessage.error('加载失败')
    router.push('/relation')
    return false
  } finally {
    loading.value = false
  }
}

// Relationship CRUD
function openEdit() {
  if (!relationship.value) return
  const r = relationship.value
  formData.value = {
    name: r.name, alias: r.alias || '', met_date: r.met_date || null,
    met_place: r.met_place || '', met_scene: r.met_scene || '',
    identity_then: r.identity_then || '', they_give_me: r.they_give_me || '',
    i_give_them: r.i_give_them || '', current_status: r.current_status || 'active',
    notes: r.notes || '', tags: r.tags || '',
  }
  formVisible.value = true
}

async function handleEditSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await api.updateRelationship(relationshipId.value, formData.value)
    ElMessage.success('已更新')
    formVisible.value = false
    await fetchDetail()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(`确定删除「${maskName(relationship.value?.name || '', privacyStore.privacyMode)}」及其所有互动记录？`, '提示', { type: 'warning' })
    await api.deleteRelationship(relationshipId.value)
    ElMessage.success('已删除')
    router.push('/relation')
  } catch { /* cancelled */ }
}

function resetForm() {
  formRef.value?.resetFields()
}

// Interaction CRUD
function openAddInteraction() {
  isEditInteraction.value = false
  editingInteractionId.value = null
  interactionForm.value = {
    relationship: relationshipId.value,
    happened_at: '',
    method: 'meet',
    energy_score: 5,
    quality_shift: 'same',
    summary: '',
    next_reminder: '',
    my_action: '',
  }
  interactionFormVisible.value = true
}

function openEditInteraction(item: Interaction) {
  isEditInteraction.value = true
  editingInteractionId.value = item.id
  interactionForm.value = {
    relationship: relationshipId.value,
    happened_at: item.happened_at || '',
    method: item.method || 'meet',
    energy_score: item.energy_score ?? 0,
    quality_shift: item.quality_shift || 'same',
    summary: item.summary || '',
    next_reminder: item.next_reminder || '',
    my_action: item.my_action || '',
  }
  interactionFormVisible.value = true
}

async function handleInteractionSubmit() {
  const valid = await interactionFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submittingInteraction.value = true
  try {
    const payload = { ...interactionForm.value }
    if (isEditInteraction.value && editingInteractionId.value) {
      await api.updateInteraction(editingInteractionId.value, payload)
    } else {
      await api.createInteraction(payload)
    }
    ElMessage.success(isEditInteraction.value ? '已更新' : '已添加')
    interactionFormVisible.value = false
    await fetchDetail()
    initCharts()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  } finally {
    submittingInteraction.value = false
  }
}

async function handleDeleteInteraction(item: Interaction) {
  try {
    await ElMessageBox.confirm('确定删除此互动记录？', '提示', { type: 'warning' })
    await api.deleteInteraction(item.id)
    ElMessage.success('已删除')
    await fetchDetail()
    initCharts()
  } catch { /* cancelled */ }
}

function resetInteractionForm() {
  interactionFormRef.value?.resetFields()
}

// Charts
function initCharts() {
  nextTick(() => {
    const sorted = [...interactions.value].sort((a, b) => a.happened_at.localeCompare(b.happened_at))
    initEnergyChartForRelation(sorted)
    initFreqChartForRelation(sorted)
  })
}

function initEnergyChartForRelation(data: Interaction[]) {
  if (!energyChartRef.value) return
  if (!energyChart) energyChart = echarts.init(energyChartRef.value)
  energyChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '8%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: data.map(d => d.happened_at.slice(0, 10)), axisLabel: { fontSize: 10, interval: Math.max(1, Math.floor(data.length / 8)) } },
    yAxis: { type: 'value', min: -11, max: 11, splitLine: { lineStyle: { type: 'dashed' } } },
    series: [{
      type: 'line', data: data.map(d => d.energy_score), smooth: true,
      symbol: 'circle', symbolSize: 6,
      areaStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(139,92,246,0.3)' }, { offset: 1, color: 'rgba(139,92,246,0.02)' }] },
      },
      lineStyle: { color: '#8B5CF6', width: 2 },
      itemStyle: function (p: any) {
        const v = data[p.dataIndex]?.energy_score ?? 0
        return { color: v > 0 ? '#10B981' : v === 0 ? '#9CA3AF' : '#EF4444' }
      } as any,
    }],
  })
  energyChart.resize()
}

function initFreqChartForRelation(data: Interaction[]) {
  if (!frequencyChartRef.value) return
  if (!frequencyChart) frequencyChart = echarts.init(frequencyChartRef.value)
  // Group by month
  const monthMap = new Map<string, number>()
  data.forEach(d => {
    const m = d.happened_at.slice(0, 7)
    monthMap.set(m, (monthMap.get(m) || 0) + 1)
  })
  const months = Array.from(monthMap.entries()).sort(([a], [b]) => a.localeCompare(b))
  frequencyChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '8%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: months.map(([m]) => m), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'bar', data: months.map(([, c]) => c), barWidth: '40%',
      itemStyle: { color: '#A78BFA', borderRadius: [4, 4, 0, 0] },
    }],
  })
  frequencyChart.resize()
}

watch(interactions, initCharts, { deep: true })
window.addEventListener('resize', () => {
  energyChart?.resize()
  frequencyChart?.resize()
})

onMounted(async () => {
  const ok = await fetchDetail()
  if (ok) initCharts()
})
</script>

<style scoped lang="scss">
.relation-detail {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;

  .back-bar { margin-bottom: 16px; }

  .profile-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px;
    .profile-header { display: flex; align-items: center; gap: 16px;
      .avatar { width: 56px; height: 56px; border-radius: 14px; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 700; font-size: 22px; flex-shrink: 0; }
      .profile-info { flex: 1;
        .profile-name { font-size: 20px; font-weight: 700; color: #1F2937; }
        .profile-alias { font-size: 13px; color: #9CA3AF; margin-top: 2px; }
        .profile-meta { display: flex; gap: 8px; margin-top: 6px; }
      }
      .profile-actions { display: flex; gap: 8px; flex-shrink: 0; }
    }

    .profile-stats { display: flex; gap: 40px; margin-top: 20px;
      .stat-item { text-align: center;
        .stat-num { font-size: 22px; font-weight: 700; color: #1F2937; }
        .stat-lbl { font-size: 12px; color: #9CA3AF; margin-top: 2px; }
      }
    }
  }

  .info-grid { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px;
    .info-item { display: flex; flex-direction: column; gap: 2px;
      .label { font-size: 12px; color: #9CA3AF; }
      .value { font-size: 14px; color: #374151; }
    }
  }

  .info-section { margin-bottom: 16px;
    .info-section-label { font-size: 12px; color: #9CA3AF; margin-bottom: 4px; }
    .info-section-content { font-size: 14px; color: #374151; line-height: 1.6; }
    .tags-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
  }

  .give-row { margin-bottom: 16px;
    .give-card { padding: 14px; border-radius: 8px; min-height: 60px;
      &.give-in { background: #f0fdf4; }
      &.give-out { background: #faf5ff; }
      .give-title { font-size: 12px; font-weight: 600; margin-bottom: 4px; color: #374151; }
      .give-content { font-size: 13px; color: #6B7280; line-height: 1.5; }
    }
  }

  .give-take-comparison { display: flex; align-items: center; justify-content: center; gap: 24px; padding: 8px 0;
    .compare-item { text-align: center;
      .compare-num { font-size: 26px; font-weight: 700; color: #8B5CF6;
        &.positive { color: #10B981; }
        &.negative { color: #EF4444; }
      }
      .compare-lbl { font-size: 12px; color: #9CA3AF; margin-top: 2px; }
    }
    .compare-divider { width: 1px; height: 40px; background: #e5e7eb; }
  }

  .section-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px;
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
    .section-header { display: flex; justify-content: space-between; align-items: center; }
  }

  .chart-box { height: 260px; width: 100%; }

  .timeline { padding: 8px 0;
    .timeline-item { display: flex; gap: 14px; padding: 12px 0; position: relative; border-bottom: 1px solid #f5f5f5;
      &:last-child { border-bottom: none; }
      .timeline-dot { width: 12px; height: 12px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; }
      .timeline-content { flex: 1;
        .timeline-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px;
          .timeline-date { font-size: 13px; color: #6B7280; }
          .timeline-energy { font-size: 14px; font-weight: 700; }
          .timeline-energy-label { font-size: 12px; color: #9CA3AF; }
        }
        .timeline-summary { font-size: 14px; color: #374151; margin-bottom: 6px; }
        .timeline-my-action { font-size: 13px; color: #8B5CF6; margin-bottom: 6px; display: flex; align-items: center; gap: 4px;
          .el-icon { font-size: 14px; }
        }
        .timeline-actions { display: flex; gap: 4px; }
      }
    }
  }

  .empty-timeline { padding: 40px 0; }

  .energy-slider-wrap {
    padding: 8px 12px 0;

    .energy-preview {
      text-align: center; margin-top: 8px; font-size: 15px; font-weight: 600;
    }

    :deep(.el-slider__marks-text) { font-size: 10px; color: #9CA3AF; }
  }
}
</style>
