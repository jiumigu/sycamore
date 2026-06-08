<template>
  <div class="inbox-page">
    <div class="page-header">
      <div class="header-left">
        <h2>📥 收件箱</h2>
        <el-tag size="small" type="info" effect="plain">大脑的缓冲区，先存后理</el-tag>
      </div>
    </div>

    <QuickInput />
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" :class="{ active: store.filterStatus === 'pending' }" shadow="hover" @click="filterByStatus('pending')">
          <div class="stat-label">📋 待处理</div>
          <div class="stat-value pending">{{ stats.pending }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" :class="{ active: store.filterStatus === 'done' }" shadow="hover" @click="filterByStatus('done')">
          <div class="stat-label">✅ 已完成</div>
          <div class="stat-value completed">{{ stats.completed }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" :class="{ active: store.filterStatus === 'processed' }" shadow="hover" @click="filterByStatus('processed')">
          <div class="stat-label">🔄 已处理</div>
          <div class="stat-value processed">{{ stats.processed }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" :class="{ active: !store.filterStatus || store.filterStatus === 'all' }" shadow="hover" @click="filterByStatus('all')">
          <div class="stat-label">📊 总条数</div>
          <div class="stat-value total">{{ stats.total }}</div>
        </el-card>
      </el-col>
    </el-row>
    <InboxFilter v-model:batch-mode="batchMode" />
    <BatchActions />

    <section class="section">
      <InboxList :batch-mode="batchMode" @edit="handleEdit" @convert="handleConvert" @complete="handleComplete" />
    </section>

    <el-pagination
      v-if="store.total > 0"
      v-model:current-page="store.currentPage"
      :page-size="store.pageSize"
      :total="store.total"
      layout="prev, pager, next"
      @current-change="store.handlePageChange"
      style="margin-top: 16px; justify-content: center"
    />

    <InboxForm v-model:visible="formVisible" :item="editItem" />
    <ConvertModal v-model:visible="convertVisible" :item="convertItem" />

    <!-- 完成备注弹窗 -->
    <el-dialog v-model="completionDialogVisible" title="标记完成" width="480px" :close-on-click-modal="false">
      <el-form :model="completeForm">
        <p class="complete-item-title">确认完成：<strong>{{ completingItem?.content }}</strong></p>

        <el-form-item label="完成备注">
          <el-input
            v-model="completeForm.note"
            type="textarea"
            :rows="3"
            placeholder="记录完成情况、关键结论或后续行动（选填）"
          />
        </el-form-item>

        <el-divider />

        <div class="extra-options">
          <!-- 工作类别：关联良品率 -->
          <template v-if="completingItem?.category === 'work'">
            <el-checkbox v-model="completeForm.recordOutput" class="output-check">
              📊 同时登记到个人良品率
            </el-checkbox>
            <template v-if="completeForm.recordOutput">
              <el-form-item label="质量判定" class="sub-option">
                <el-radio-group v-model="completeForm.quality">
                  <el-radio value="good">✅ 良品（达到预期）</el-radio>
                  <el-radio value="defective">⚠️ 不良品（未达预期）</el-radio>
                  <el-radio value="waste">❌ 废品（彻底搞砸）</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="难度" class="sub-option">
                <el-radio-group v-model="completeForm.difficulty">
                  <el-radio :value="1">1 轻车熟路</el-radio>
                  <el-radio :value="2">2 稍需思考</el-radio>
                  <el-radio :value="3">3 需要努力</el-radio>
                  <el-radio :value="4">4 挑战较大</el-radio>
                  <el-radio :value="5">5 完全未知</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-if="completeForm.quality !== 'good'" label="失败原因" class="sub-option">
                <el-select v-model="completeForm.failType" placeholder="选择失败类型" style="width:100%">
                  <el-option label="认知盲区（没想到）" value="认知盲区" />
                  <el-option label="能力不足（想到了做不到）" value="能力不足" />
                  <el-option label="外部因素（不可控）" value="外部因素" />
                  <el-option label="运气（随机事件）" value="运气" />
                  <el-option label="粗心（本可以避免）" value="粗心" />
                </el-select>
              </el-form-item>
              <el-form-item label="经验教训" class="sub-option">
                <el-input v-model="completeForm.lesson" type="textarea" :rows="2" />
              </el-form-item>
            </template>
          </template>

          <el-checkbox v-model="completeForm.addSugar" class="sugar-check">
            🍰 同时新增一条小确幸记录
          </el-checkbox>
          <template v-if="completeForm.addSugar">
            <el-form-item label="开心指数" class="sub-option">
              <el-rate v-model="completeForm.sugarRating" :max="5" />
            </el-form-item>
          </template>

          <el-checkbox v-model="completeForm.addReward" class="reward-check">
            🏦 同时新增奖励到快乐银行
          </el-checkbox>
          <template v-if="completeForm.addReward">
            <el-form-item label="奖励金额" class="sub-option">
              <el-input-number v-model="completeForm.rewardAmount" :min="1" :max="100" :precision="2" />
              <span class="suffix">元</span>
            </el-form-item>
            <el-form-item label="奖励理由" class="sub-option">
              <el-input v-model="completeForm.rewardReason" placeholder="如：完成了一件拖延很久的事" />
            </el-form-item>
          </template>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="completionDialogVisible = false">取消</el-button>
        <el-button type="success" :loading="processing" @click="confirmComplete">确认完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useInboxStore } from '../stores/inboxStore'
import type { InboxItem } from '../types/inboxTypes'
import * as sugarApi from '@/modules/sugar/api/sugarApi'
import * as rewardApi from '@/modules/reward/api/rewardApi'
import * as goalsApi from '@/modules/goals/api/goalApi'
import QuickInput from '../components/QuickInput.vue'
import InboxFilter from '../components/InboxFilter.vue'
import InboxList from '../components/InboxList.vue'
import BatchActions from '../components/BatchActions.vue'
import InboxForm from '../components/InboxForm.vue'
import ConvertModal from '../components/ConvertModal.vue'

const store = useInboxStore()

const stats = computed(() => store.stats ?? { pending: 0, completed: 0, processed: 0, total: 0 })

function filterByStatus(status: string) {
  if (store.filterStatus === status || (status === 'all' && (!store.filterStatus || store.filterStatus === 'all'))) {
    store.filterStatus = 'all'
  } else {
    store.filterStatus = status
  }
  store.search()
}

const batchMode = ref(false)
const formVisible = ref(false)
const editItem = ref<InboxItem | null>(null)
const convertVisible = ref(false)
const convertItem = ref<InboxItem | null>(null)
const completionDialogVisible = ref(false)
const completingItem = ref<InboxItem | null>(null)
const processing = ref(false)

const completeForm = reactive({
  note: '',
  addSugar: false,
  sugarRating: 3,
  addReward: false,
  rewardAmount: 5,
  rewardReason: '',
  // 良品率关联
  recordOutput: false,
  quality: 'good',
  difficulty: 3,
  failType: '',
  lesson: '',
})

// 失败类型：前端显示 → 后端存储值映射
const failTypeMap: Record<string, string> = {
  '认知盲区': 'cognitive',
  '能力不足': 'ability',
  '外部因素': 'external',
  '运气': 'luck',
  '粗心': 'careless',
  '其他': 'other',
}

function resetCompleteForm() {
  completeForm.note = ''
  completeForm.addSugar = false
  completeForm.sugarRating = 3
  completeForm.addReward = false
  completeForm.rewardAmount = 5
  completeForm.rewardReason = ''
  completeForm.recordOutput = false
  completeForm.quality = 'good'
  completeForm.difficulty = 3
  completeForm.failType = ''
  completeForm.lesson = ''
}

onMounted(() => {
  store.fetchAll()
})

function handleEdit(item: InboxItem) {
  editItem.value = item
  formVisible.value = true
}

function handleConvert(item: InboxItem) {
  convertItem.value = item
  convertVisible.value = true
}

function handleComplete(item: InboxItem) {
  completingItem.value = item
  resetCompleteForm()
  completeForm.note = item.completion_note || ''
  completionDialogVisible.value = true
}

async function confirmComplete() {
  if (!completingItem.value) return
  processing.value = true
  try {
    const item = completingItem.value

    // 1. 标记完成
    await store.completeItem(item.id, completeForm.note || undefined)

    // 2. 登记良品率（仅工作类别）
    if (completeForm.recordOutput) {
      const mappedFailType = failTypeMap[completeForm.failType] || ''
      await goalsApi.createOutputRecord({
        title: item.content,
        category: 'work',
        quality: completeForm.quality,
        difficulty: completeForm.difficulty,
        fail_type: mappedFailType,
        fail_reason: completeForm.quality !== 'good' ? (completeForm.failType || '') : '',
        lesson_learned: completeForm.lesson || '',
        occurred_at: new Date().toISOString().slice(0, 10),
        expected_result: '',
        actual_result: completeForm.note || '',
      })
    }

    // 3. 新增小确幸
    if (completeForm.addSugar) {
      await sugarApi.createSugar({
        content: `完成：${item.content}`,
        level_of_happiness: completeForm.sugarRating || 3,
        reward_amount: 0,
        record_type: 'moment',
      })
    }

    // 3. 新增奖励
    if (completeForm.addReward) {
      await rewardApi.addRewardTransaction({
        amount: completeForm.rewardAmount,
        source_type: 'inbox_complete',
        transaction_type: 'manual_add',
        description: completeForm.rewardReason || `完成：${item.content}`,
      })
    }

    ElMessage.success('已完成')
    completionDialogVisible.value = false
    completingItem.value = null
    resetCompleteForm()
  } catch (e: any) {
    console.error('操作失败:', e)
    console.error('响应数据:', e.response?.data)
    console.error('响应状态:', e.response?.status)
    ElMessage.error('操作失败')
  } finally {
    processing.value = false
  }
}
</script>

<style scoped>
.inbox-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1F2937;
}
.stats-row {
  margin-bottom: 16px;
}
.stat-card {
  cursor: pointer;
  border-radius: 10px;
  transition: all 0.2s;
  border: 2px solid transparent;
  &.active {
    border-color: #409EFF;
    background: #ECF5FF;
  }
  :deep(.el-card__body) {
    padding: 16px;
    text-align: center;
  }
}
.stat-label {
  font-size: 12px;
  color: #6B7280;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  &.pending { color: #3B82F6; }
  &.completed { color: #10B981; }
  &.processed { color: #8B5CF6; }
  &.total { color: #6B7280; }
}
.section {
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  padding: 16px;
}

.complete-item-title {
  margin: 0 0 12px;
  font-size: 14px;
  color: #374151;
}

.extra-options {
  .sub-option {
    margin-left: 24px;
    margin-top: 8px;
  }
  .output-check {
    margin-bottom: 8px;
  }
  .sugar-check {
    margin-top: 12px;
  }
  .reward-check {
    margin-top: 12px;
  }
}

.suffix {
  margin-left: 8px;
  font-size: 13px;
  color: #6B7280;
}
</style>
