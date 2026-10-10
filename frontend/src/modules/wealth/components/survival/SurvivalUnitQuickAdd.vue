<!--
  就地新增消耗单位（P3-A 二期）

  为什么要有这个小弹窗：单位维护弹窗原本只挂在页面顶部，而真正的痛点是
  **在填物品/配方时才发现少一个单位**（「鸡蛋」按「个」记，可种子单位里只有克/千克/罐/袋/顿）。
  那时候跳出当前弹窗去维护，回来还得重填一遍。

  所以这里只问三个字段（名称 / 基准单位 / 换算率），建完**自动选中**，
  编辑器一个字段都不用重填。

  ⚠️ 刻意不做成「下拉里的行内表单」：下拉一点外部就收起，
  在收起过程中提交会把「点了一下」变成「填了一半就没了」。
  带浮层的小弹窗虽然多一次点击，但不会丢输入。

  换算率不是可选项：跨单位求和的前提是折到同一基准，
  「20 罐 + 3000 克」在数学上无意义，而错误结果是**静默**的 ——
  它会给出一个看着完全合理的生存天数，没人会去查。
-->
<template>
  <el-dialog
    v-model="visible"
    title="新增消耗单位"
    width="440px"
    :close-on-click-modal="false"
    append-to-body
  >
    <div class="survival-quick-unit__hint">
      建完会<b>自动选中</b>，当前正在编辑的物品/配方不用重填。<br />
      基准单位留空 = 这个单位自成一系（不与同类别其它单位换算）。
    </div>

    <el-form :model="form" label-width="88px" size="small">
      <el-form-item label="单位名称">
        <el-input
          v-model="form.name"
          placeholder="个 / 盒 / 瓶 / 斤 / 张"
          maxlength="20"
          @keyup.enter="submit"
        />
      </el-form-item>
      <el-form-item label="基准单位">
        <el-input v-model="form.base_unit" placeholder="留空 = 自成一系；如 克 / 件" maxlength="20" />
      </el-form-item>
      <el-form-item label="换算率">
        <el-input-number v-model="form.to_base_rate" :min="0.0001" :step="1" :precision="4" />
        <span class="survival-quick-unit__suffix">
          1 {{ form.name || '本单位' }} = {{ form.to_base_rate }} {{ form.base_unit || form.name || '基准' }}
        </span>
      </el-form-item>
      <el-form-item label="可作一餐">
        <el-switch v-model="form.is_serving_unit" />
        <span class="survival-quick-unit__suffix">如「顿」—— 可直接当作一餐的计数单位</span>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button size="small" type="primary" :loading="store.saving" @click="submit">
        建好并使用
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useSurvivalStore } from '../../stores/survivalStore'
import type { SurvivalUnit } from '../../types/survivalTypes'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  categoryId: number | null
  categoryName: string
}>()

/** 建好之后把新单位交回调用方，由它写进表单并选中 */
const emit = defineEmits<{ created: [unit: SurvivalUnit] }>()

const store = useSurvivalStore()

const form = reactive({
  name: '',
  base_unit: '',
  to_base_rate: 1,
  is_serving_unit: false,
})

function resetForm() {
  form.name = ''
  form.base_unit = ''
  form.to_base_rate = 1
  form.is_serving_unit = false
}

watch(visible, (open) => {
  if (open) resetForm()
})

async function submit() {
  if (!props.categoryId) {
    ElMessage.warning('先选一个类别')
    return
  }
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('单位名称不能为空')
    return
  }
  // 同名单位在同一个类别下是重复的 —— 提前拦下，并告诉用户「已经有一个了，直接用」
  const duplicate = store.units.find(
    (u) => u.category_id === props.categoryId && u.name === name,
  )
  if (duplicate) {
    ElMessage.warning(`「${name}」已经存在，直接选它就行`)
    return
  }
  try {
    const created = await store.saveUnit({
      category_id: props.categoryId,
      name,
      base_unit: form.base_unit.trim(),
      to_base_rate: form.to_base_rate,
      is_serving_unit: form.is_serving_unit,
    })
    const unit = (created as SurvivalUnit | undefined)
      // `saveUnit` 不返回行时从刚刷新过的清单里找回来，避免「建好了却没选中」
      ?? store.units.find((u) => u.category_id === props.categoryId && u.name === name)
    if (unit) emit('created', unit)
    ElMessage.success(`已新增单位「${name}」`)
    visible.value = false
  } catch (e: unknown) {
    ElMessage.error(extractMessage(e, '新增失败'))
  }
}

function extractMessage(e: unknown, fallback: string): string {
  const data = (e as { response?: { data?: Record<string, unknown> } })?.response?.data
  if (data && typeof data.detail === 'string') return data.detail
  if (data) {
    const first = Object.values(data)[0]
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string') return first
  }
  return fallback
}
</script>

<style scoped>
.survival-quick-unit__hint {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}
.survival-quick-unit__suffix {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
