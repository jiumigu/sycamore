<!--
  用掉 / 入库 · 极简浮层（v3.60.18 · P0）

  为什么是浮层、不是「消耗登记页」：用户想「我吃了一罐」时，眼睛盯的是**那件物品**。
  另建一个页面 = 逼他记住第二个入口，进去还要重新找一次物品 —— 那才是真正的重复填写。

  🔴 **这个浮层只有一格需要打字。** 其余全部预填、只读或自动：

    物品名 / 单位   从物品带出，只读        —— 用户已经从那件物品点进来了，再问一遍才是重复
    当前数量        只读                    —— 改的是「变化量」，不是「绝对值」
    数量            默认 1、自动聚焦全选     —— 「1 件 / 1 份」是绝大多数情况
    原因            留空即可，后端按类别自动 —— 只有异常（坏了 / 过期 / 丢弃 / 送人）才要动手
    时间            默认「刚刚」             —— 补记才点开 ✎
    渠道            系统填 `manual`          —— 用户不需要知道这个词

  🔴 **「用掉几件」和「还剩几件」永远不并列。** 这里只问前者；
     后者由 `当前 − 用掉` **算出来**摆在旁边当预览（防错，不是第二个输入框）。
     并列问两个的后果不是多填一格，是**静默错账**：两个都填了，系统只能听一个。

  ⚠️ 预览里的减法是**纯展示**：真正的判定（不能为负、不能为 0）在后端，
     前端只是把「会变成负数」提前说一声。
-->
<template>
  <el-dialog
    v-model="visible"
    :title="`${isUse ? '用掉' : '入库'} · ${name || '—'}`"
    width="420px"
    :close-on-click-modal="false"
    append-to-body
    @opened="onOpen"
  >
    <div class="flow-dialog__book">
      <span class="flow-dialog__book-label">当前</span>
      <b>{{ formatQuantity(bookQuantity, unitName) }}</b>
    </div>

    <div class="flow-dialog__input-row">
      <!-- 唯一需要打字的格子：自动聚焦 + 内容全选，回车即提交 -->
      <el-input
        ref="amountRef"
        v-model="amount"
        size="large"
        inputmode="decimal"
        class="flow-dialog__input"
        @keyup.enter="submit"
      />
      <span class="flow-dialog__unit">{{ unitName }}</span>
    </div>

    <!-- 实时预览：把「这笔记下去会变成多少」摆出来（防错，不是重复输入） -->
    <div class="flow-dialog__preview" :class="{ 'is-bad': !previewOk }">
      {{ previewText }}
    </div>

    <!-- 原因：胶囊按钮。留空也可提交 —— 后端按类别的消耗模式自动记 -->
    <div class="flow-dialog__reasons">
      <span class="flow-dialog__label">原因</span>
      <el-radio-group v-model="reason" size="small">
        <el-radio-button
          v-for="opt in reasonOptions"
          :key="opt.value"
          :value="opt.value"
        >{{ opt.label }}</el-radio-button>
      </el-radio-group>
    </div>
    <div class="flow-dialog__hint">
      不选也行 —— 系统会按这类物品的消耗模式自动记成「{{ isUse ? '吃掉 / 用掉' : '入库' }}」
    </div>

    <!-- 时间：默认「刚刚」；补记才点开 ✎ -->
    <div class="flow-dialog__time">
      <span class="flow-dialog__label">时间</span>
      <span class="flow-dialog__time-text">{{ occurredAt ? occurredAt : '刚刚' }}</span>
      <el-button link size="small" @click="showTime = !showTime">
        {{ showTime ? '收起' : '✎ 补记' }}
      </el-button>
      <el-date-picker
        v-if="showTime"
        v-model="occurredAt"
        type="datetime"
        size="small"
        value-format="YYYY-MM-DD HH:mm:ss"
        placeholder="选择发生时间（不能是未来）"
        class="flow-dialog__time-picker"
      />
    </div>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button
        size="small"
        type="primary"
        :loading="flowStore.saving"
        :disabled="!previewOk"
        @click="submit"
      >
        确认
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import type { InputInstance } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useSurvivalFlowStore } from '../../stores/survivalFlowStore'
import { formatQuantity } from '../../utils/survivalFormat'
import { apiErrorText } from '@/shared/utils/apiError'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  /** 要记哪一件；null = 没打开 */
  itemId: number | null
  /** 用掉（消耗）还是入库 */
  mode: 'use' | 'restock'
  /** 父级已经知道的名称 / 当前数量 / 单位 —— 先渲染，不等接口 */
  fallbackName: string
  fallbackQuantity: number | null
  fallbackUnitName: string
}>()

const emit = defineEmits<{
  /** 记成功了 —— 由父级去刷新物品数量与工作表（本组件不管别的 store） */
  saved: []
}>()

const flowStore = useSurvivalFlowStore()

const amountRef = ref<InputInstance | null>(null)
const amount = ref('1')
const reason = ref('')
const occurredAt = ref('')
const showTime = ref(false)

const isUse = computed(() => props.mode === 'use')
const name = computed(() => props.fallbackName)
const unitName = computed(() => props.fallbackUnitName)
const bookQuantity = computed(() => props.fallbackQuantity)

/**
 * 数量输入。
 *
 * ⚠️ 刻意用 `el-input` 而不是 `el-input-number`：后者带加减按钮，
 *    而这里的加减按钮会让人以为「点几下就能记几笔」——
 *    真正要提交的只有一次。空串按 0 处理（预览会立刻报「必须是正数」）。
 */
const amountNum = computed(() => {
  const n = Number(amount.value)
  return Number.isFinite(n) ? n : NaN
})

const after = computed(() => {
  const base = bookQuantity.value
  if (base === null || !Number.isFinite(amountNum.value)) return null
  return isUse.value ? base - amountNum.value : base + amountNum.value
})

/**
 * 能不能提交。
 *
 * 判据与后端一致（正数、改完不为负），但这里**只做预告不做兜底** ——
 * 真正的拒绝在服务层，前端禁用按钮只是省一次往返，
 * 绝不把它当成「前端校验过了后端就不用查」。
 */
const previewOk = computed(
  () => Number.isFinite(amountNum.value) && amountNum.value > 0
    && after.value !== null && after.value >= 0,
)

const previewText = computed(() => {
  if (bookQuantity.value === null) return '取不到当前库存，请刷新后重试'
  if (!Number.isFinite(amountNum.value)) return '请填一个数字'
  if (amountNum.value <= 0) return '数量要大于 0'
  if (after.value !== null && after.value < 0) {
    return `现在只有 ${formatQuantity(bookQuantity.value, unitName.value)}，`
      + `这一笔要减 ${formatQuantity(amountNum.value, '')}，会变成负数 —— `
      + '请核对数量，或改用「盘一下」直接改成实际值'
  }
  const afterText = formatQuantity(after.value, unitName.value)
  return isUse.value ? `用掉后剩 ${afterText}` : `入库后为 ${afterText}`
})

/**
 * 原因胶囊。
 *
 * ⚠️ 两套选项与后端 `SURVIVAL_FLOW_REASONS` 同值；**留空一律可以提交**，
 *    后端按类别自动记 —— 所以这里不预选任何一项，避免「看起来必须选」。
 */
const reasonOptions = computed(() => (isUse.value
  ? [
    { value: 'eat', label: '吃掉' },
    { value: 'use', label: '用掉' },
    { value: 'broken', label: '坏了' },
    { value: 'expired', label: '过期' },
    { value: 'discard', label: '丢弃' },
    { value: 'gift', label: '送人' },
  ]
  : [
    { value: 'buy', label: '买入' },
    { value: 'receive', label: '受赠' },
    { value: 'other', label: '其他' },
  ]))

/**
 * 每次打开都回到「刚刚 + 默认 1」，并把光标放进那一格。
 *
 * ⚠️ 挂在 `@opened`（动画结束）而不是 `@open`：el-dialog 自带 focus-trap，
 *    它在「打开」那一刻把焦点收进容器 —— 若我们在 `@open` 里抢焦点，
 *    会被随后的 trap 覆盖掉，表现就是**看着有焦点、其实没有**（实测复现过）。
 */
async function onOpen() {
  amount.value = '1'
  reason.value = ''
  occurredAt.value = ''
  showTime.value = false
  await nextTick()
  focusAmount()
  // 兜一层：transition 结束与本帧之间仍可能插进一次 trap 的焦点重置
  window.setTimeout(focusAmount, 30)
}

function focusAmount() {
  amountRef.value?.focus()
  amountRef.value?.select()
}

async function submit() {
  if (!previewOk.value || props.itemId === null) return
  const delta = isUse.value ? -Math.abs(amountNum.value) : Math.abs(amountNum.value)
  try {
    await flowStore.record({
      item_id: props.itemId,
      delta,
      channel: 'manual',
      reason: reason.value || undefined,
      occurred_at: occurredAt.value || undefined,
    })
  } catch (err: unknown) {
    // 把后端的具体原因说出来（「会变成负数」这类）——
    // 只会回一句「保存失败」的话，用户只能瞎猜自己哪里填错了
    ElMessage.error(apiErrorText(err, '保存失败'))
    return
  }
  ElMessage.success(isUse.value ? '已记一笔用掉' : '已记一笔入库')
  emit('saved')
  visible.value = false
}
// ⚠️ 失败原因 → 人话的实现**只在** `@/shared/utils/apiError`（唯一实现）。
//    不在这里再写一份：「5xx 该不该把 Django 调试页读给用户看」这种判断
//    一旦分叉，没人知道哪份是对的。
</script>

<style scoped>
.flow-dialog__book {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.flow-dialog__book-label {
  color: var(--el-text-color-secondary);
}
.flow-dialog__input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 0 6px;
}
.flow-dialog__input {
  width: 140px;
}
.flow-dialog__unit {
  font-size: 14px;
  color: var(--el-text-color-regular);
}
/* 预览行：常态是提示（次要色），会变负数时才转成警示色 ——
   「防错」与「报错」必须是两种长相，否则用户会以为填错了 */
.flow-dialog__preview {
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.flow-dialog__preview.is-bad {
  color: var(--el-color-danger);
}
.flow-dialog__reasons {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}
.flow-dialog__label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.flow-dialog__hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.flow-dialog__time {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.flow-dialog__time-text {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.flow-dialog__time-picker {
  width: 200px;
}
</style>
