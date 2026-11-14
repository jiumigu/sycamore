<template>
  <div class="quick-bill-inline">
    <el-form label-position="top" size="small" @submit.prevent>
      <el-row :gutter="10">
        <el-col :span="14">
          <el-form-item label="金额">
            <el-input-number
              ref="amountRef"
              v-model="form.amount"
              :min="0.01"
              :precision="2"
              :controls="false"
              placeholder="0.00"
              class="quick-bill-inline__amount"
              @keyup.enter="submit"
            />
          </el-form-item>
        </el-col>
        <el-col :span="10">
          <el-form-item label="类型">
            <el-radio-group v-model="form.transaction_type">
              <el-radio-button value="支出">支出</el-radio-button>
              <el-radio-button value="收入">收入</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-col>
      </el-row>

      <!--
        🔴 分类与子分类的候选**只有一个来源**：后端 `/wealth/classify/bill-options/`
           （账本的真实层级 ∪ 口径配置里登记过的分类名）。组件里不持有任何分类常量。

        ⚠️ 两个都保留 `filterable` + `allow-create`：
           ① 口径配置里被停用过的分类名，历史账单里还在用，不能选不到；
           ② 分类体系是长出来的 —— 可以先记一笔新分类的账，回头再去口径配置补规则。
              禁止自由输入等于要求「先建规则才能记账」，顺序反了。
      -->
      <el-row :gutter="10">
        <el-col :span="12">
          <el-form-item label="分类">
            <el-select
              v-model="form.category"
              filterable
              allow-create
              clearable
              placeholder="可选"
              style="width: 100%"
            >
              <el-option
                v-for="opt in categoryOptions"
                :key="opt.value"
                :label="opt.value"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="子分类">
            <el-select
              v-model="form.subcategory"
              filterable
              allow-create
              clearable
              :placeholder="subcategoryPlaceholder"
              style="width: 100%"
            >
              <el-option
                v-for="opt in subcategoryOptions"
                :key="opt.value"
                :label="opt.value"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="日期">
        <el-date-picker
          v-model="form.date"
          type="date"
          value-format="YYYY-MM-DD"
          :clearable="false"
        />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createBill } from '../../api/wealthApi'
import { useClassifyStore } from '../../stores/classifyStore'
import {
  pickSubcategoryOptions,
  subcategoryPlaceholder as subPlaceholder,
} from '../../utils/billCategoryOptions'
import { todayLocal } from '@/shared/utils/datetime'
import type { BillCategoryOption } from '../../types/wealthTypes'

/**
 * 页头的「记一笔」—— 五个字段：金额 / 类型 / 分类 / 子分类 / 日期。
 *
 * 🔴 刻意**没有**账户、商户、项目、备注、必要程度、归属。
 *    随手记一笔只填「金额 + 分类」，每多一个显眼字段就多一次决策，
 *    记账就会拖到晚上一起补，而晚上补的账分类准确率最低。
 *    其余字段在账单页行内补（`BillListView` 已有 `period_tag` 行内下拉与批量标记）。
 *
 * ⚠️ 子分类是这条原则的**唯一例外**，理由不是「顺手」，而是它**参与口径判定**：
 *    ① `CLASSIFY_RULE` 的匹配字段是 category / subcategory / merchant，
 *       且**同优先级时更具体的字段胜**（subcategory > category）——
 *       没有子分类，「早午晚餐」这类规则就永远打不中；
 *    ② 未归类候选按 `(category, subcategory)` 聚合，分组粒度直接决定
 *       建议建在哪条规则上 —— 子分类为空就只能按大类给建议，粗一档；
 *    ③ 导入的 CSV 本来就带子分类，手记的却带不了 ⇒ 同一张表里两种数据质量，
 *       事后根本分不清「这笔真没子分类」还是「录入口没给」。
 *    所以它是「口径的一部分」，与「账户/商户」这类事后可补的描述性字段不同档。
 *
 * ⚠️ 归属（`period_tag`）留空仍然是故意的，不是漏了：它本来就是**事后批量归类**的，
 *    堵在录入口等于要求「先想清楚这笔算什么」才能记账，顺序反了。
 */
const classifyStore = useClassifyStore()
const amountRef = ref<{ focus?: () => void } | null>(null)
const saving = ref(false)

/** 分类候选**只认**后端 `classify/bill-options/`，组件内不持有任何分类常量 */
const categoryOptions = computed<BillCategoryOption[]>(
  () => classifyStore.billOptions?.categories ?? [],
)

const form = reactive({
  amount: null as number | null,
  category: '',
  subcategory: '',
  transaction_type: '支出' as '支出' | '收入',
  // 🔴 本地日期，不是 `toISOString()`（那是 UTC，早上 8 点前会记到昨天）
  date: todayLocal(),
})

/**
 * 子分类候选：选了分类就只给该分类下的，没选（或该分类还没历史）就给全局。
 *
 * 🔴 联动规则本身在 `utils/billCategoryOptions.ts` —— 与月度页的「记一笔」弹窗
 *    （`QuickBillForm`）**共用同一份**。两边各写一遍的话，同一个分类在两个入口
 *    会给出不同的子分类候选，而且不报错，只有用户觉得「怎么这里选不到」。
 */
const subcategoryOptions = computed<BillCategoryOption[]>(() =>
  pickSubcategoryOptions(classifyStore.billOptions, form.category),
)

/** 半宽约 190px，长文案会被省略号吃掉，所以用 `narrow = true` */
const subcategoryPlaceholder = computed(() => subPlaceholder(form.category, true))

/**
 * 换分类 ⇒ 清掉子分类。
 *
 * 🔴 子分类是**挂在分类下**的：把「食品酒水 / 早午晚餐」的分类改成「行车交通」后，
 *    「早午晚餐」就不成立了。留着它 = 静默存出一条自相矛盾的账目，
 *    事后看数据没人说得清是谁的错。只在**值真的变了**时清（`watch` 天然满足）。
 */
watch(() => form.category, () => {
  form.subcategory = ''
})

onMounted(() => {
  // 每次打开都拉：候选是账本的派生结果，今天自由输入的新分类明天就该出现在列表里
  classifyStore.fetchBillOptions()
  amountRef.value?.focus?.()
})

/** 保存一笔。成功后**不关面板**、只清金额与分类，保留日期与类型（记账是成串发生的） */
async function submit() {
  if (saving.value) return
  const amount = Number(form.amount)
  if (!form.amount || !Number.isFinite(amount) || amount <= 0) {
    ElMessage.warning('请先填金额')
    amountRef.value?.focus?.()
    return
  }

  saving.value = true
  try {
    await createBill({
      transaction_type: form.transaction_type,
      amount,
      category: form.category || '',
      subcategory: form.subcategory || '',
      project: '',
      account: '',
      merchant: '',
      notes: '',
      date: form.date,
    })
    ElMessage.success(`已记一笔 ¥${amount.toFixed(2)}`)
    form.amount = null
    // 分类与子分类一起清（子分类跟着分类走，单独留着没有意义）
    form.category = ''
    form.subcategory = ''
    // 记完一笔重新拉候选：新输入的分类可能刚进账本
    classifyStore.fetchBillOptions()
    amountRef.value?.focus?.()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '记账失败')
  } finally {
    saving.value = false
  }
}

/** 父组件（`QuickRecordPanel` 的页脚按钮）调这里 */
defineExpose({ submit, saving })
</script>

<style scoped lang="scss">
.quick-bill-inline {
  :deep(.el-form-item) {
    margin-bottom: 12px;
  }

  :deep(.el-form-item__label) {
    padding-bottom: 2px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__amount {
    width: 100%;

    :deep(.el-input__inner) {
      font-size: 16px;
      font-variant-numeric: tabular-nums;
    }
  }

  // 🔴 el-date-picker 的根**没有 data-v 作用域属性**（class 只透传到 `.el-date-editor`），
  //    所以 `&__xxx { width:100% }` 这类 scoped 选择器匹配不到 —— 实测仍是默认 220px。
  //    必须走 `:deep()` 从本组件根节点往下选。
  :deep(.el-date-editor) {
    width: 100%;
  }
}
</style>
