<template>
  <div class="review-toolbox">
    <div class="back-bar">
      <el-button text @click="$router.push('/toolkit')">
        <el-icon><ArrowLeft /></el-icon> 返回工具集
      </el-button>
    </div>
    <!-- 类型切换 TAB -->
    <el-tabs v-model="activeType" @tab-change="handleTypeChange">
      <el-tab-pane v-for="tab in reviewTabs" :key="tab.value" :label="tab.label" :name="tab.value" />

      <!-- 新建/编辑弹窗 -->
      <el-dialog v-model="formVisible" :title="editingId ? '编辑复盘' : `新建${currentTabLabel}`" width="700px" @closed="resetForm">
        <el-form :model="form" label-position="top" size="small">
          <el-form-item label="复盘日期" required>
            <el-date-picker v-model="form.review_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
          </el-form-item>

          <!-- ========== 每日复盘 ========== -->
          <template v-if="activeType === 'daily'">
            <el-form-item label="状态">
              <el-radio-group v-model="form.daily_status">
                <el-radio value="思考">🤔 思考</el-radio>
                <el-radio value="总结">📝 总结</el-radio>
                <el-radio value="感悟">💡 感悟</el-radio>
                <el-radio value="记录">📋 记录</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="那些人那些事">
              <el-input v-model="form.daily_people" type="textarea" :rows="3" placeholder="今天遇到了谁？发生了什么？" />
            </el-form-item>
            <el-form-item label="我缺乏的">
              <el-input v-model="form.johari_window.lack" type="textarea" :rows="2" placeholder="我知道自己缺乏的..." />
            </el-form-item>
            <el-form-item label="我掌握的">
              <el-input v-model="form.johari_window.have" type="textarea" :rows="2" placeholder="我知道自己掌握的..." />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="别人看到我的盲点">
                  <el-input v-model="form.johari_window.blind" type="textarea" :rows="2" placeholder="别人知道但自己不知道的..." />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="未知潜能">
                  <el-input v-model="form.johari_window.unknown" type="textarea" :rows="2" placeholder="别人和自己都不知道的..." />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="😊 开心的事">
                  <el-input v-model="form.emotions.happy" type="textarea" :rows="2" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="😑 无聊的事">
                  <el-input v-model="form.emotions.boring" type="textarea" :rows="2" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="😠 可憎的事">
                  <el-input v-model="form.emotions.angry" type="textarea" :rows="2" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="🥺 怀恋的事">
                  <el-input v-model="form.emotions.nostalgic" type="textarea" :rows="2" />
                </el-form-item>
              </el-col>
            </el-row>
          </template>

          <!-- ========== 周复盘 ========== -->
          <template v-if="activeType === 'weekly'">
            <el-form-item label="本周完成">
              <el-input v-model="form.completed" type="textarea" :rows="4" placeholder="完成了哪些事？" />
            </el-form-item>
            <el-form-item label="下周计划">
              <el-input v-model="form.plan_next" type="textarea" :rows="4" placeholder="下周要做什么？" />
            </el-form-item>
            <el-form-item label="反思总结">
              <el-input v-model="form.reflection" type="textarea" :rows="4" placeholder="有什么反思？学到了什么？" />
            </el-form-item>
          </template>

          <!-- ========== 月复盘 ========== -->
          <template v-if="activeType === 'monthly'">
            <el-form-item label="本月完成">
              <el-input v-model="form.completed" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="下月计划">
              <el-input v-model="form.plan_next" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="反思总结">
              <el-input v-model="form.reflection" type="textarea" :rows="3" />
            </el-form-item>
            <el-divider>GRAI 复盘</el-divider>
            <el-form-item label="目标">
              <el-input v-model="form.grai.goal" :rows="2" placeholder="原定目标是什么？" />
            </el-form-item>
            <el-form-item label="结果">
              <el-input v-model="form.grai.result" :rows="2" placeholder="实际结果如何？" />
            </el-form-item>
            <el-form-item label="原因分析">
              <el-input v-model="form.grai.reason" :rows="3" placeholder="为什么会有这样的差距？" />
            </el-form-item>
            <el-form-item label="规律总结">
              <el-input v-model="form.grai.rule" :rows="3" placeholder="学到了什么规律？下次如何应用？" />
            </el-form-item>
            <el-divider>ORID 聚焦</el-divider>
            <el-form-item label="客观事实">
              <el-input v-model="form.orid.facts" :rows="2" placeholder="发生了什么？（客观描述）" />
            </el-form-item>
            <el-form-item label="感受体验">
              <el-input v-model="form.orid.feelings" :rows="2" placeholder="我的感受是什么？" />
            </el-form-item>
            <el-form-item label="思考诠释">
              <el-input v-model="form.orid.thinking" :rows="2" placeholder="我对此的思考和理解？" />
            </el-form-item>
            <el-form-item label="行动决策">
              <el-input v-model="form.orid.decision" :rows="2" placeholder="接下来怎么做？" />
            </el-form-item>
          </template>

          <!-- ========== 季度复盘 ========== -->
          <template v-if="activeType === 'quarterly'">
            <el-form-item label="🌱 滋养的 3 件小事">
              <el-input v-model="form.nourishing" type="textarea" :rows="3" placeholder="这个季度让你感到被滋养的 3 件事" />
            </el-form-item>
            <el-form-item label="🕳️ 消耗黑洞">
              <el-input v-model="form.draining" type="textarea" :rows="3" placeholder="哪些事在持续消耗你的能量？" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="😨 害怕的事">
                  <el-input v-model="form.fears" type="textarea" :rows="3" placeholder="你在害怕什么？" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="😖 烦恼的事">
                  <el-input v-model="form.worries" type="textarea" :rows="3" placeholder="你在烦恼什么？" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="👀 羡慕的对象">
              <el-input v-model="form.envy_target" :rows="2" placeholder="你羡慕谁？羡慕 ta 什么？" />
            </el-form-item>
            <el-form-item label="👴 80 岁遗憾">
              <el-input v-model="form.regret_at_80" type="textarea" :rows="3" placeholder="如果现在不做，80 岁的你会遗憾什么？" />
            </el-form-item>
            <el-form-item label="🛤️ 5 年路径推演">
              <el-input v-model="form.life_paths" type="textarea" :rows="4" placeholder="想象 3 条不同的人生路径，每条路会通向哪里？" />
            </el-form-item>
          </template>

          <!-- ========== 人生编舟 ========== -->
          <template v-if="activeType === 'life'">
            <el-form-item label="📜 过往序章 — 生命线回顾">
              <el-input v-model="form.life_line" type="textarea" :rows="4" placeholder="回望过去，哪些时刻塑造了今天的你？" />
            </el-form-item>
            <el-form-item label="🗼 明日灯塔 — 个人目标">
              <el-input v-model="form.personal_goals" type="textarea" :rows="4" placeholder="你想要成为什么样的人？想要达成什么？" />
            </el-form-item>
            <el-form-item label="⏳ 时间之旅 — 四象限规划">
              <el-input v-model="form.time_plan" type="textarea" :rows="4" placeholder="重要紧急 / 重要不紧急 / 紧急不重要 / 不重要不紧急" />
            </el-form-item>
            <el-form-item label="🪞 自省之泉 — 深度复盘">
              <el-input v-model="form.deep_reflection" type="textarea" :rows="4" placeholder="对这段时间的深度反思..." />
            </el-form-item>
          </template>

          <el-form-item label="备注">
            <el-input v-model="form.notes" :rows="2" placeholder="选填" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button size="small" @click="formVisible = false">取消</el-button>
          <el-button size="small" type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </template>
      </el-dialog>
    </el-tabs>

    <!-- 内容区 -->
    <div v-loading="loading" class="content-area">
      <!-- 新建按钮 -->
      <div class="toolbar">
        <span class="record-count">共 {{ total }} 条记录</span>
        <el-button type="primary" size="small" @click="openCreate">+ 新建{{ currentTabLabel }}</el-button>
      </div>

      <!-- 列表 -->
      <div v-if="!records.length" class="empty-state">
        <el-empty description="暂无记录" :image-size="50" />
      </div>
      <div v-else class="record-list">
        <el-card v-for="r in records" :key="r.id" shadow="hover" class="record-card">
          <div class="record-header">
            <span class="record-date">{{ r.review_date }}</span>
            <div class="record-actions">
              <el-button size="small" text @click="openEdit(r)">✏️ 编辑</el-button>
              <el-button size="small" text type="danger" @click="handleDelete(r)">🗑️ 删除</el-button>
            </div>
          </div>

          <!-- 每日摘要 -->
          <template v-if="r.review_type === 'daily'">
            <el-tag v-if="r.daily_status" size="small" class="status-tag">{{ r.daily_status }}</el-tag>
            <p v-if="r.daily_people" class="preview-text">{{ r.daily_people }}</p>
          </template>

          <!-- 周/月摘要 -->
          <template v-if="r.review_type === 'weekly' || r.review_type === 'monthly'">
            <div v-if="r.completed" class="preview-section">
              <span class="preview-label">✓ 完成：</span>
              <span class="preview-text">{{ truncate(r.completed, 100) }}</span>
            </div>
            <div v-if="r.reflection" class="preview-section">
              <span class="preview-label">💭 反思：</span>
              <span class="preview-text">{{ truncate(r.reflection, 100) }}</span>
            </div>
          </template>

          <!-- 季度摘要 -->
          <template v-if="r.review_type === 'quarterly'">
            <div v-if="r.nourishing" class="preview-section">
              <span class="preview-label">🌱 滋养：</span>
              <span class="preview-text">{{ truncate(r.nourishing, 80) }}</span>
            </div>
            <div v-if="r.draining" class="preview-section">
              <span class="preview-label">🕳️ 消耗：</span>
              <span class="preview-text">{{ truncate(r.draining, 80) }}</span>
            </div>
          </template>

          <!-- 人生编舟摘要 -->
          <template v-if="r.review_type === 'life'">
            <div v-if="r.life_line" class="preview-section">
              <span class="preview-label">📜 生命线：</span>
              <span class="preview-text">{{ truncate(r.life_line, 100) }}</span>
            </div>
          </template>
        </el-card>
      </div>

      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        small
        style="margin-top:16px;justify-content:center"
        @current-change="fetchRecords"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getReviewRecords, createReviewRecord, updateReviewRecord, deleteReviewRecord } from '../../api/toolkitApi'

const reviewTabs = [
  { value: 'daily', label: '🪞 每日复盘' },
  { value: 'weekly', label: '📅 周复盘' },
  { value: 'monthly', label: '🌙 月复盘' },
  { value: 'quarterly', label: '🧭 季度复盘' },
  { value: 'life', label: '🗺️ 人生编舟' },
]

const activeType = ref('daily')
const records = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const formVisible = ref(false)
const editingId = ref<number | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const currentTabLabel = computed(() => reviewTabs.find(t => t.value === activeType.value)?.label || '')

const form = reactive({
  review_type: 'daily',
  review_date: '',
  daily_status: '',
  daily_people: '',
  johari_window: { lack: '', have: '', blind: '', unknown: '' } as Record<string, string>,
  emotions: { happy: '', boring: '', angry: '', nostalgic: '' } as Record<string, string>,
  completed: '',
  plan_next: '',
  reflection: '',
  grai: { goal: '', result: '', reason: '', rule: '' } as Record<string, string>,
  orid: { facts: '', feelings: '', thinking: '', decision: '' } as Record<string, string>,
  nourishing: '',
  draining: '',
  fears: '',
  worries: '',
  envy_target: '',
  regret_at_80: '',
  life_paths: '',
  life_line: '',
  personal_goals: '',
  time_plan: '',
  deep_reflection: '',
  notes: '',
})

function resetForm() {
  editingId.value = null
  form.review_type = activeType.value
  form.review_date = ''
  form.daily_status = ''
  form.daily_people = ''
  form.johari_window = { lack: '', have: '', blind: '', unknown: '' }
  form.emotions = { happy: '', boring: '', angry: '', nostalgic: '' }
  form.completed = ''
  form.plan_next = ''
  form.reflection = ''
  form.grai = { goal: '', result: '', reason: '', rule: '' }
  form.orid = { facts: '', feelings: '', thinking: '', decision: '' }
  form.nourishing = ''
  form.draining = ''
  form.fears = ''
  form.worries = ''
  form.envy_target = ''
  form.regret_at_80 = ''
  form.life_paths = ''
  form.life_line = ''
  form.personal_goals = ''
  form.time_plan = ''
  form.deep_reflection = ''
  form.notes = ''
}

function fillForm(r: any) {
  form.review_type = r.review_type
  form.review_date = r.review_date
  form.daily_status = r.daily_status || ''
  form.daily_people = r.daily_people || ''
  form.johari_window = { lack: '', have: '', blind: '', unknown: '', ...(r.johari_window || {}) }
  form.emotions = { happy: '', boring: '', angry: '', nostalgic: '', ...(r.emotions || {}) }
  form.completed = r.completed || ''
  form.plan_next = r.plan_next || ''
  form.reflection = r.reflection || ''
  form.grai = { goal: '', result: '', reason: '', rule: '', ...(r.grai || {}) }
  form.orid = { facts: '', feelings: '', thinking: '', decision: '', ...(r.orid || {}) }
  form.nourishing = r.nourishing || ''
  form.draining = r.draining || ''
  form.fears = r.fears || ''
  form.worries = r.worries || ''
  form.envy_target = r.envy_target || ''
  form.regret_at_80 = r.regret_at_80 || ''
  form.life_paths = r.life_paths || ''
  form.life_line = r.life_line || ''
  form.personal_goals = r.personal_goals || ''
  form.time_plan = r.time_plan || ''
  form.deep_reflection = r.deep_reflection || ''
  form.notes = r.notes || ''
}

function openCreate() {
  resetForm()
  form.review_type = activeType.value
  formVisible.value = true
}

function openEdit(r: any) {
  editingId.value = r.id
  fillForm(r)
  formVisible.value = true
}

async function fetchRecords() {
  loading.value = true
  try {
    const res = await getReviewRecords({
      review_type: activeType.value,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    records.value = (res.data?.results || []) as any[]
    total.value = res.data?.count ?? 0
  } catch {
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!form.review_date) {
    ElMessage.warning('请选择复盘日期')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, user_id: 1 }
    if (editingId.value) {
      await updateReviewRecord(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await createReviewRecord(payload)
      ElMessage.success('已创建')
    }
    formVisible.value = false
    fetchRecords()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(r: any) {
  try {
    await ElMessageBox.confirm(`确定删除 ${r.review_date} 的记录？`, '确认删除', { type: 'warning' })
    await deleteReviewRecord(r.id)
    ElMessage.success('已删除')
    fetchRecords()
  } catch { /* cancelled */ }
}

function handleTypeChange() {
  currentPage.value = 1
  fetchRecords()
}

function truncate(text: string, len: number) {
  return text && text.length > len ? text.slice(0, len) + '...' : text
}

onMounted(fetchRecords)
</script>

<style scoped>
.review-toolbox { padding: 20px; background: var(--el-bg-color-page); min-height: 100vh; }
.back-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; flex-wrap: nowrap; }
.content-area { margin-top: 16px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.record-count { font-size: 13px; color: var(--el-text-color-secondary); }
.empty-state { padding: 60px 0; }
.record-list { display: flex; flex-direction: column; gap: 8px; }
.record-card { border: none; border-radius: 8px; }
.record-card :deep(.el-card__body) { padding: 14px 16px; }
.record-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.record-date { font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); }
.record-actions { display: flex; gap: 4px; }
.status-tag { margin-bottom: 6px; }
.preview-section { font-size: 13px; line-height: 1.5; margin-top: 4px; }
.preview-label { font-weight: 500; color: var(--el-text-color-secondary); }
.preview-text { color: var(--el-text-color-regular); white-space: pre-wrap; }
</style>
