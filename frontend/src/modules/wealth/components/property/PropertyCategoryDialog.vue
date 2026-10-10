<!--
  物件类别 · 新增 / 编辑弹窗（v3.60.0）

  ⚠️ `icon` 字段**刻意不在这个表单里**：种子数据给了六个图标名，
     但界面目前不依赖它。放一个自由文本的图标名输入框，写错了不会报错、
     只会静默退化成一个默认图标 —— 那正是本项目最怕的一类失败
     （「看着正常，其实没生效」）。要用图标就一次做对（带白名单与预览），
     那是二期的事，先不做，也不留一个半成品入口。

  ⚠️ 「默认使用年限」是**预填值**，不是兜底值 —— 这一点必须在界面上说出来。
     它的语义是「执行用户自己的意志」：让人少打一次字。
     如果一个物件自己没填年限，系统**不会**拿这个值顶上（净值显示「—」）。
     一旦兜底，「他自己填了 5 年」与「他没填、系统按类别猜了 5 年」
     在界面上就分不出来了 —— 那是本项目历史上最贵的一类 bug。
-->
<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑类别' : '新增类别'"
    width="460px"
    :close-on-click-modal="false"
    append-to-body
  >
    <el-form :model="form" label-width="104px" size="small">
      <el-form-item label="类别名称" required>
        <el-input
          v-model="form.name"
          placeholder="家电 / 家具 / 数码 / 交通 / 家装"
          maxlength="50"
        />
      </el-form-item>

      <el-form-item label="默认使用年限">
        <el-input-number
          v-model="defaultYears"
          :min="0.1"
          :max="100"
          :step="0.5"
          :precision="1"
          :controls="false"
          placeholder="留空 = 不预填"
          class="property-cat-dialog__years"
        />
        <span class="property-cat-dialog__suffix">年（可填小数，8.5 = 8 年 6 月）</span>
        <div class="property-cat-dialog__hint">
          只用来<b>预填</b>新增表单，可逐件改。留空表示不预填；
          <b>绝不作任何计算依据</b> —— 物件自己没填年限时净值算不出，不会拿它顶上。
        </div>
      </el-form-item>

      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" :max="999" :controls="false" />
        <span class="property-cat-dialog__suffix">数字小的排前面</span>
      </el-form-item>

      <el-form-item label="说明">
        <el-input
          v-model="form.note"
          type="textarea"
          :rows="2"
          maxlength="200"
          show-word-limit
          placeholder="这类里通常有哪些东西，如「冰箱 / 空调 / 洗衣机 / 热水器」"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button size="small" type="primary" :loading="store.saving" @click="submit">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { usePropertyStore } from '../../stores/propertyStore'
import { extractApiMessage } from '../../utils/propertyError'
import { monthsToYears, yearsToMonths } from '../../utils/propertyFormat'
import type { PropertyCategory } from '../../types/propertyTypes'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  /** 传 null = 新增；传整行 = 编辑 */
  category: PropertyCategory | null
}>()

const store = usePropertyStore()

const isEdit = computed(() => !!props.category)

const form = reactive<{
  name: string
  /** `el-input-number` 清空后会给 null —— 类型里就带上，别在提交时才想 */
  sort_order: number | null
  note: string
}>({
  name: '',
  sort_order: 0,
  note: '',
})

/**
 * 年限在界面上是「年」、在库里是「月」。
 *
 * ⚠️ 这个 ref 与 `form` 分开，是因为「留空」必须是一个**真的空**，
 *    而不是 0：`el-input-number` 清空后会给出 null，
 *    如果把它塞进 `form` 再统一 `?? 0`，就会把「不预填」变成「预填 0 年」，
 *    而后者会让折旧除零。空值语义在类型里就 `number | null`，不掉成 0。
 */
const defaultYears = ref<number | null>(null)

watch(visible, (open) => {
  if (!open) return
  form.name = props.category?.name ?? ''
  form.sort_order = props.category?.sort_order ?? 0
  form.note = props.category?.note ?? ''
  defaultYears.value = monthsToYears(props.category?.default_lifespan_months ?? null)
})

async function submit() {
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('类别名称不能为空')
    return
  }
  const payload = {
    name,
    // 清空排序框 → 归 0（而不是把 null 送过去让后端 400）
    sort_order: form.sort_order ?? 0,
    note: form.note.trim(),
    // ⚠️ 「留空」要原样送 null 过去，不能不传 ——
    //    不传等于「不动」，用户就永远撤不掉一个已有的默认年限。
    default_lifespan_months: yearsToMonths(defaultYears.value),
  }
  try {
    await store.saveCategory(payload, props.category?.id)
    ElMessage.success(isEdit.value ? '已更新类别' : `已新增类别「${name}」`)
    visible.value = false
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '保存类别失败'))
  }
}
</script>

<style scoped>
.property-cat-dialog__years {
  width: 120px;
}
.property-cat-dialog__suffix {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-cat-dialog__hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
</style>
