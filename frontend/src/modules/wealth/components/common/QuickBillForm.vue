<template>
  <el-form :model="form" label-position="top" size="small" ref="formRef">
    <el-row :gutter="12">
      <el-col :span="12">
        <el-form-item label="交易类型" :rules="[{ required: true, message: '请选择类型' }]">
          <el-radio-group v-model="form.transaction_type">
            <el-radio value="收入">收入</el-radio>
            <el-radio value="支出">支出</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="金额" :rules="[{ required: true, message: '请输入金额' }]">
          <el-input-number
            v-model="form.amount"
            :min="0.01"
            :precision="2"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
      </el-col>
    </el-row>

    <!--
      🔴 分类与子分类的候选**只有一个来源**：后端
         `/wealth/classify/bill-options/`（账本的真实层级 ∪ 口径配置里登记过的分类名）。

         本组件里原来有一份 17 项硬编码数组（餐饮 / 交通 / 购物 / 居住…），
         与真实账本（食品酒水 / 日常生活 / 行车交通…）**完全对不上** ——
         全表 6588 行里只碰巧命中 3 行。这正是「同一事实两把尺子」的典型：
         分类体系一旦有两处定义，就永远不知道哪一处才是真的（v3.62.17 修掉）。

      ⚠️ `filterable` + `allow-create` **必须保留**，两个理由：
         ① 口径配置里被**停用**过的分类名，历史账单里还在用，编辑时不能选不到；
         ② 分类体系是长出来的 —— 可以先记一笔新分类的账，回头再去口径配置补规则。
            若在这里禁止自由输入，等于要求「先建规则才能记账」，把顺序倒过来了。
    -->
    <el-row :gutter="12">
      <el-col :span="12">
        <el-form-item label="分类">
          <el-select
            v-model="form.category"
            filterable
            allow-create
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
          <!--
            ⚠️ 子分类**跟着分类走**，但那个父子关系只存在于**账本数据**里：
               口径配置那张规则表的 `category` 与 `subcategory` 是**两个平行的匹配
               字段**，一条「匹配值 = 数码装备」的规则并不声明它属于哪个分类。
               所以联动只能由后端下发的 `subcategories`（分类 → 该分类下的子分类）驱动，
               前端不自己配对。
          -->
          <el-select
            v-model="form.subcategory"
            filterable
            allow-create
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

    <el-row :gutter="12">
      <el-col :span="8">
        <el-form-item label="账户">
          <el-input v-model="form.account" placeholder="可选" />
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item label="商家">
          <el-input v-model="form.merchant" placeholder="可选" />
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item label="项目">
          <el-input v-model="form.project" placeholder="可选" />
        </el-form-item>
      </el-col>
    </el-row>

    <el-form-item label="备注">
      <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="可选" />
    </el-form-item>

    <div class="quick-bill__actions">
      <el-button @click="$emit('cancel')">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        保存
      </el-button>
    </div>
  </el-form>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { todayLocal } from '@/shared/utils/datetime'
import { useClassifyStore } from '../../stores/classifyStore'
import {
  pickSubcategoryOptions,
  subcategoryPlaceholder as subPlaceholder,
} from '../../utils/billCategoryOptions'
import type { BillCategoryOption, BillCreateData } from '../../types/wealthTypes'

const emit = defineEmits<{
  submit: [data: BillCreateData]
  cancel: []
}>()

const props = withDefaults(defineProps<{
  defaultDate?: string | null
  submitting?: boolean
}>(), {
  submitting: false,
})

/**
 * 分类 / 子分类候选来自 `classifyStore.billOptions`。
 *
 * ⚠️ 本组件**不自己取数** —— 候选由容器（`DayDetailModal`）在**每次打开**时刷新，
 *    因为它随账本每天都在变。这里只负责读与联动，不持有任何分类常量。
 */
const classifyStore = useClassifyStore()

/** 分类候选：按账本笔数降序（常用的在最上面） */
const categoryOptions = computed<BillCategoryOption[]>(
  () => classifyStore.billOptions?.categories ?? [],
)

/**
 * 子分类候选：选了分类就只给该分类下的，没选（或该分类还没历史）就给全局。
 *
 * 🔴 联动规则本身在 `utils/billCategoryOptions.ts` —— 与页头「快速记录」的记账页签
 *    **共用同一份**。两边各写一遍的话，同一个分类在两个入口会给出不同的子分类候选，
 *    而且不报错、只有用户觉得「怎么这里选不到」。
 */
const subcategoryOptions = computed<BillCategoryOption[]>(() =>
  pickSubcategoryOptions(classifyStore.billOptions, form.category),
)

/** 未选分类时说明「这是全部子分类」，省得有人以为候选丢了 */
const subcategoryPlaceholder = computed(() => subPlaceholder(form.category))

const form = reactive<BillCreateData>({
  transaction_type: '支出',
  amount: 0,
  category: '',
  subcategory: '',
  project: '',
  account: '',
  merchant: '',
  notes: '',
  // 🔴 必须用本地日期：`new Date().toISOString().slice(0,10)` 取的是 UTC，
  //    北京时间 00:00–07:59 会得到昨天（v3.64.48 修，唯一实现在 shared/utils/datetime.ts）
  date: props.defaultDate || todayLocal(),
})

/**
 * 换分类 ⇒ 清掉子分类。
 *
 * 🔴 判据：子分类是**挂在分类下**的，换了分类之后原来那个子分类很可能不属于新分类
 *    （「食品酒水 / 早午晚餐」改成「行车交通」后，「早午晚餐」就不成立了）。
 *    留下它 = 静默存出一条自相矛盾的账目，而且事后看数据谁也说不清是谁的错。
 *    ⚠️ 只在**用户真的换了分类**（值发生变化）时清 —— 单纯点开下拉再选中同一项
 *    不该触发（`watch` 只在值变化时回调，天然满足）。
 */
watch(() => form.category, () => {
  form.subcategory = ''
})

function handleSubmit() {
  if (!form.transaction_type) return
  if (form.amount <= 0) return
  emit('submit', { ...form })
}
</script>

<style scoped lang="scss">
.quick-bill__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
