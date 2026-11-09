<template>
  <div class="inbox-page">
    <div class="page-header">
      <div class="header-left">
        <h2>📥 收件箱</h2>
        <el-tag size="small" type="info" effect="plain">大脑的缓冲区，先存后理</el-tag>
      </div>
      <div class="header-right">
        <el-button @click="showImportDialog = true">
          <el-icon><Upload /></el-icon> 导入
        </el-button>
      </div>
    </div>

    <QuickInput />
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4">
        <el-card class="stat-card" :class="{ active: store.filterStatus === 'pending' }" shadow="hover" @click="filterByStatus('pending')">
          <div class="stat-label">📋 待处理</div>
          <div class="stat-value pending">{{ stats.pending }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card" :class="{ active: store.filterStatus === 'hesitating' }" shadow="hover" @click="filterByStatus('hesitating')">
          <div class="stat-label">🤔 犹豫中</div>
          <div class="stat-value hesitating">{{ stats.hesitating }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card" :class="{ active: store.filterStatus === 'done' }" shadow="hover" @click="filterByStatus('done')">
          <div class="stat-label">✅ 已完成</div>
          <div class="stat-value completed">{{ stats.completed }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card" :class="{ active: store.filterStatus === 'processed' }" shadow="hover" @click="filterByStatus('processed')">
          <div class="stat-label">🔄 已处理</div>
          <div class="stat-value processed">{{ stats.processed }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card" :class="{ active: store.filterStatus === 'abandoned' }" shadow="hover" @click="filterByStatus('abandoned')">
          <div class="stat-label">🗑️ 已废弃</div>
          <div class="stat-value abandoned">{{ stats.abandoned }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
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
    <ImportDialog v-model="showImportDialog" @success="handleImportSuccess" />

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
            <el-form-item label="开心程度" class="sub-option">
              <HappinessScale v-model="completeForm.happiness" />
            </el-form-item>
            <el-form-item label="奖励" class="sub-option">
              <span class="reward-preview">💰 ¥{{ completeForm.happiness }}</span>
              <span class="reward-hint">金额 = 开心程度（由小确幸自动记一笔）</span>
            </el-form-item>
          </template>

          <!-- 🔴 勾了小确幸就禁掉这个：小确幸创建时**后端已经记过一笔**奖励，
               再勾一次等于同一件事记两笔（余额会翻倍，而且流水上看不出原因）。 -->
          <el-checkbox
            v-model="completeForm.addReward"
            :disabled="completeForm.addSugar"
            class="reward-check"
          >
            🏦 同时新增奖励到快乐银行
            <span v-if="completeForm.addSugar" class="reward-hint">（小确幸已自动记过，无需再加）</span>
          </el-checkbox>
          <template v-if="completeForm.addReward && !completeForm.addSugar">
            <el-form-item label="奖励金额" class="sub-option">
              <el-input-number v-model="completeForm.rewardAmount" :min="1" :max="100" :precision="2" />
              <span class="suffix">元</span>
            </el-form-item>
            <el-form-item label="奖励理由" class="sub-option">
              <el-input v-model="completeForm.rewardReason" placeholder="如：完成了一件拖延很久的事" />
            </el-form-item>
          </template>

          <!-- 作品（v3.62.0）：与上面三个勾**并排、同长相** ——
               它是同一件事的下一个入口，不是第二次设计。 -->
          <div class="keep-row">
            <el-checkbox v-model="completeForm.keepIt">📦 这条值得留下（收进「待提炼」）</el-checkbox>
            <!-- ⚠️ `el-popover` 而不是 `el-tooltip`（两者插槽语义是反的）：
                 tooltip 的默认插槽是「触发元素」、正文要走 `#content`；
                 popover 才是「`#reference` 触发 + 默认插槽正文」。
                 写错不报错，只是正文被当成触发内容**内联渲染、常驻可见**。 -->
            <el-popover placement="top" :width="340" trigger="hover" :show-after="120">
              <template #reference>
                <el-icon class="keep-icon"><QuestionFilled /></el-icon>
              </template>
              <div class="keep-tip">
                <p>勾了<b>不用现在写</b>什么 —— 它只把这条放进「待提炼」。</p>
                <p>
                  在<b>「本周状态」页末</b>把它收成一件东西
                  （一份清单、一个方法、一段记录都算）。
                </p>
              </div>
            </el-popover>
          </div>
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
import { Upload, QuestionFilled } from '@element-plus/icons-vue'
import { useInboxStore } from '../stores/inboxStore'
import type { InboxItem } from '../types/inboxTypes'
import * as sugarApi from '@/modules/sugar/api/sugarApi'
// 快乐程度输入与小确幸页共用同一个组件 —— 避免这里再出现一套「星→分」的换算
import HappinessScale from '@/modules/sugar/components/HappinessScale.vue'
// 「值得留下」→ 作品库的「待提炼」。与上面三个「同时登记到…」同源：**前端串联**。
import { capture as captureWork } from '@/modules/works/api/workApi'
import * as rewardApi from '@/modules/reward/api/rewardApi'
import * as goalsApi from '@/modules/goals/api/goalApi'
import QuickInput from '../components/QuickInput.vue'
import InboxFilter from '../components/InboxFilter.vue'
import InboxList from '../components/InboxList.vue'
import BatchActions from '../components/BatchActions.vue'
import InboxForm from '../components/InboxForm.vue'
import ConvertModal from '../components/ConvertModal.vue'
import ImportDialog from '../components/ImportDialog.vue'

const store = useInboxStore()

const stats = computed(() => store.stats ?? { pending: 0, hesitating: 0, completed: 0, processed: 0, abandoned: 0, total: 0 })

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
const showImportDialog = ref(false)

function handleImportSuccess() {
  store.fetchAll()
}

const completeForm = reactive({
  note: '',
  addSugar: false,
  /**
   * 快乐程度（5–20 分，区间由后端 `happiness_bands` 下发）。
   *
   * 🔴 这里曾经是 `sugarRating: 1–5 颗星`，提交时 `星 × 4` 折成 5–20 分。
   *    折出来的 12 分被后端写进了流水文案（「获得 12 元奖励」），
   *    而实际入账的是另一个字段 `rewardAmount: 5` ⇒ 同一条记录两个数、还都显示出来。
   *    现在只有这一套刻度，且**金额 = 分数**，不再有第二次换算。
   */
  happiness: 10,
  addReward: false,
  /** 仅「不记小确幸、只记奖励」时用：那种场景没有程度可派生，只能自己填金额 */
  rewardAmount: 5,
  rewardReason: '',
  // 良品率关联
  recordOutput: false,
  quality: 'good',
  difficulty: 3,
  failType: '',
  lesson: '',
  // 作品（v3.62.0）：跟上面三个「同时登记到…」**同一个模式** ——
  // 勾只是把这条放进「待提炼」，**不需要现在写任何东西**。
  keepIt: false,
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
  completeForm.happiness = 10
  completeForm.addReward = false
  completeForm.rewardAmount = 5
  completeForm.rewardReason = ''
  completeForm.recordOutput = false
  completeForm.quality = 'good'
  completeForm.difficulty = 3
  completeForm.failType = ''
  completeForm.lesson = ''
  completeForm.keepIt = false
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

function localToday(): string {
  // 🔴 用本地日期，不用 `toISOString().slice(0,10)`：那是 UTC，东八区早上 8 点前
  //    会记成前一天（小确幸日期、良品率日期都会错一天）。
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** 从后端错误体里取一句人话；取不到就返回空串 —— 宁可少说，不编原因。 */
function apiErrorSuffix(e: any): string {
  const d = e?.response?.data
  if (!d) return ''
  if (typeof d === 'string') return `：${d.slice(0, 80)}`
  const first = Object.values(d as Record<string, unknown>)[0]
  const text = Array.isArray(first) ? String(first[0] ?? '') : String(first ?? '')
  return text ? `：${text.slice(0, 80)}` : ''
}

async function confirmComplete() {
  if (!completingItem.value) return
  processing.value = true
  const item = completingItem.value
  const failed: string[] = []

  try {
    // ── 1. 标记完成：只有这一步失败才是真的失败 ──
    try {
      await store.completeItem(item.id, completeForm.note || undefined)
    } catch (e: any) {
      console.error('标记完成失败:', e, e.response?.data)
      ElMessage.error(`标记完成失败${apiErrorSuffix(e)}`)
      return
    }

    // ── 2~5. 附加联动：各自独立 try ──
    //   🔴 2026-10-23 实案：原来 1~4 步共用一个 try，小确幸创建报 500 时整条链路
    //   显示「操作失败」，而收件箱其实**已经完成**。用户以为没成、又点一次
    //   ⇒ 多出一条重复小确幸（s_id 77/78）。附加项失败必须说成
    //   「已完成；X 没记上」，绝不能让用户以为要重做。
    if (completeForm.recordOutput) {
      const mappedFailType = failTypeMap[completeForm.failType] || ''
      try {
        await goalsApi.createOutputRecord({
          title: item.content,
          category: 'work',
          quality: completeForm.quality,
          difficulty: completeForm.difficulty,
          fail_type: mappedFailType,
          fail_reason: completeForm.quality !== 'good' ? (completeForm.failType || '') : '',
          lesson_learned: completeForm.lesson || '',
          occurred_at: localToday(),
          expected_result: '',
          actual_result: completeForm.note || '',
        })
      } catch (e: any) {
        console.error('良品率登记失败:', e, e.response?.data)
        failed.push('良品率')
      }
    }

    if (completeForm.addSugar) {
      try {
        // 金额 = 开心程度（同一套刻度，1 分 = 1 元）—— 全模块唯一口径。
        // 🔴 原来这里传 `星 × 4` 给程度、又传另一个 `rewardAmount=5` 当金额，
        //    后端把程度写进了流水文案 ⇒ 「获得 12 元奖励」但实际 +¥5.00。
        await sugarApi.createSugar({
          title: `完成：${item.content}`,
          level_of_happiness: completeForm.happiness,
          reward_amount: completeForm.happiness,
          time: localToday(),
        })
      } catch (e: any) {
        console.error('小确幸创建失败:', e, e.response?.data)
        failed.push('小确幸')
      }
    }

    // 🔴 互斥：小确幸创建时后端已记过一笔奖励，这里再记就是同一件事两笔
    if (completeForm.addReward && !completeForm.addSugar) {
      try {
        await rewardApi.addRewardTransaction({
          amount: completeForm.rewardAmount || 5,
          source_type: 'inbox_complete',
          transaction_type: 'inbox_complete',
          description: `收件箱完成小奖励：${item.content}`,
        })
      } catch (e: any) {
        console.error('奖励登记失败:', e, e.response?.data)
        failed.push('快乐银行奖励')
      }
    }

    // 标记「值得留下」（作品库）—— 勾的意思只是「这条以后可能长成一件东西」，
    // 此刻不用写任何字；失败同样只提示、不推翻「已完成」。
    if (completeForm.keepIt) {
      try {
        await captureWork({
          source_type: 'inbox',
          source_id: item.id,
          title: item.content,
          excerpt: (completeForm.note || '').slice(0, 300),
        })
      } catch {
        failed.push('「值得留下」')
      }
    }

    if (failed.length) {
      ElMessage.warning(`已完成；${failed.join('、')}没记上`)
    } else {
      ElMessage.success('已完成')
    }
    completionDialogVisible.value = false
    completingItem.value = null
    resetCompleteForm()
  } finally {
    processing.value = false
  }
}
</script>

<style scoped>
.inbox-page {
  max-width: 1200px;
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
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
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
  &.hesitating { color: #F59E0B; }
  &.completed { color: #10B981; }
  &.processed { color: #8B5CF6; }
  &.abandoned { color: #9CA3AF; }
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

/* 奖励预览：金额由开心程度直接派生，不让它变成一个可填的输入框 ——
   一旦能改，就又会和「开心程度」变成两个数、两处口径。 */
.reward-preview {
  font-size: 16px;
  font-weight: 700;
  color: #e6a23c;
}

.reward-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #9CA3AF;
}

/* 「值得留下」那一行：与上面三个勾同长相，但**多一个去处说明** ——
   「收进待提炼」如果不摆在眼前，勾的意思是「我又要走一遍流程吗」。 */
.keep-row {
  display: flex; align-items: center; gap: 6px;
  margin-top: 12px; padding-top: 10px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.keep-icon {
  color: var(--el-text-color-secondary); cursor: help;
  border-bottom: 1px dashed var(--el-border-color);
}
.keep-icon:hover { color: var(--el-color-primary); }
.keep-tip { max-width: 330px; font-size: 12px; line-height: 1.8; }
.keep-tip p { margin: 0 0 6px; }
.keep-tip p:last-child { margin-bottom: 0; }
</style>
