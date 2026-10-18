<!--
  身上之物 · 新增 / 编辑一个位（v3.62.4）

  一个「位」= 某个部位需要的一样东西。表单只问四件事：
  它要什么、办到哪一步了、现在顶着的这件称不称心、我想找什么样的。

  🔴 三条不能做错的：

     ① **满意可以留空，而且按钮要能把空填回去**。留空不是「凑合」——
        它是「还没有东西在用」或「有东西在用但还没评过」，两者由后端区分。
        表单不做任何「既然填了进度就顺手评个满意」的联动。

     ② **两个关联源只送一个，另一个显式送 `null`**。
        后端把「这次送的」与「原来就有的」合并起来判互斥 ——
        只送新的那一个，会让老的那个还挂着 ⇒ **400**（这正是设计要的：
        宁可拦下来，也不要一行同时挂两件、界面只显示一件）。
        所以这里每次都把两个字段一起送出去。

     ③ **「已找到」之后「想找什么样的」不清空、也不改写** ——
        它是你**当时的标准**，是个快照；标签改成「当初想找什么样的」，
        只是把这件事说出来，不动数据。

  ⚠️ 弹窗里的 `el-select` 一律 `:teleported="false"`：否则浮层挂到 body 上，
     弹窗一滚动它就与输入框分家（项目硬坑）。
-->

<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑这一位' : '新增一位'"
    width="520px"
    :close-on-click-modal="false"
  >
    <el-form :model="form" label-width="104px" label-position="right">
      <el-form-item label="部位" required>
        <el-select
          v-model="form.part_id"
          placeholder="选一个部位"
          class="body-form__wide"
          :teleported="false"
        >
          <el-option
            v-for="option in store.parts"
            :key="option.id"
            :label="option.name"
            :value="option.id"
          />
        </el-select>
        <!-- ⚠️ 部位是主数据、可自己加 —— 缺一个就在这里说清去哪加，
             而不是让用户对着一个选不出东西的下拉框发呆 -->
        <div class="body-form__hint">
          没有你要的部位？到上面的「部位维护」里加一个 —— 它就是张可以随时改的表
        </div>
      </el-form-item>

      <el-form-item label="要什么" required>
        <el-input
          v-model="form.name"
          maxlength="60"
          placeholder="眼镜 / 护手霜 / 指甲剪"
          class="body-form__wide"
        />
      </el-form-item>

      <el-form-item label="进度">
        <el-select
          v-model="form.find_status"
          class="body-form__wide"
          :teleported="false"
        >
          <el-option
            v-for="option in store.findStatusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="满意">
        <el-select
          v-model="form.satisfaction"
          clearable
          class="body-form__wide"
          placeholder="留空 = 还没东西在用，或还没评过"
          :teleported="false"
        >
          <el-option
            v-for="option in store.satisfactionOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <div class="body-form__hint">
          {{ store.meta?.satisfaction_note }}
        </div>
      </el-form-item>

      <el-form-item label="用的是哪一件">
        <el-select
          v-model="linkValue"
          filterable
          clearable
          class="body-form__wide"
          placeholder="从物件资产或物品清单里挑一件；也可以先不挂"
          :teleported="false"
        >
          <el-option
            v-for="option in linkOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <div class="body-form__hint">
          最多挂一件。这里只存「用的是这件」这层关系，不显示它的价格、天数或净值
          —— 那些数只在它自己的页面上有一份
        </div>
      </el-form-item>

      <el-form-item :label="wishLabel">
        <el-input
          v-model="form.wish"
          type="textarea"
          :rows="2"
          maxlength="500"
          placeholder="把「不满意」写具体一点：轻一点、鼻托不压、38 码不挤脚"
          class="body-form__wide"
        />
      </el-form-item>

      <el-form-item label="备注">
        <el-input
          v-model="form.note"
          type="textarea"
          :rows="2"
          maxlength="500"
          class="body-form__wide"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="store.saving" @click="submit">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useBodyStore } from '../../stores/bodyStore'
import { usePropertyStore } from '../../stores/propertyStore'
import { useSurvivalStore } from '../../stores/survivalStore'
import { extractApiMessage } from '../../utils/propertyError'
import type { BodyNeedFormData } from '../../types/bodyTypes'
import type { BodyFindStatus, BodySatisfaction, BodyLinkedKind } from '../../types/bodyTypes'

const props = defineProps<{
  /** 编辑哪一条；null = 新增 */
  needId: number | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  saved: []
}>()

const store = useBodyStore()
const propertyStore = usePropertyStore()
const survivalStore = useSurvivalStore()

const isEdit = computed(() => props.needId !== null)

/** 「已找到」之后，这一格的语义从「我想找什么样的」变成「当初想找什么样的」 */
const editingNeed = computed(
  () => store.needs.find((n) => n.id === props.needId) ?? null,
)
const wishLabel = computed(
  () => (editingNeed.value?.find_status === 'settled' ? '当初想找的' : '想找什么样的'),
)

// ─── 表单 ───
//
// ⚠️ 表单模型与入参**刻意分开**：`part_id` 在表单里可以为空（还没选），
//    而入参必须是数字（送 null 会被后端 400 拦下 —— 那是对的，别去放宽它）。
//    用 `undefined as unknown as number` 之类的强转把两者塞成一个类型，
//    换来的是「提交时忘了校验」这类静默错误。
interface BodyFormModel {
  part_id: number | null
  name: string
  find_status: BodyFindStatus
  satisfaction: BodySatisfaction | null
  wish: string
  note: string
}

function emptyForm(): BodyFormModel {
  return {
    part_id: null,
    name: '',
    find_status: 'todo',
    satisfaction: null,
    wish: '',
    note: '',
  }
}

const form = ref<BodyFormModel>(emptyForm())

/**
 * 「用的是哪一件」在界面里是一个下拉，跨**两张表** ⇒
 * 用一个带前缀的字符串值（`property-12` / `item-34`）承载，提交时再拆回两个 id。
 */
const linkValue = ref<string | null>(null)

function kindPrefix(kind: BodyLinkedKind): string {
  return kind === 'property' ? 'property' : 'item'
}

const linkOptions = computed(() => {
  const out: { value: string; label: string }[] = []
  for (const item of propertyStore.items) {
    out.push({ value: `property-${item.id}`, label: `物件资产 · ${item.name}` })
  }
  for (const item of survivalStore.items) {
    out.push({ value: `item-${item.id}`, label: `物品清单 · ${item.name}` })
  }
  return out
})

// ─── 打开时装载 ───
watch(visible, async (open) => {
  if (!open) return
  // 候选来自两个已有 store —— 只做「输入即搜 + 显式点选」，
  // **不做名称模糊匹配后自动写入**（那是静默错值的经典来源）。
  if (!propertyStore.items.length) await propertyStore.fetchItems()
  if (!survivalStore.items.length) await survivalStore.fetchItems()

  const need = editingNeed.value
  if (need) {
    form.value = {
      part_id: need.part_id,
      name: need.name,
      find_status: need.find_status,
      satisfaction: need.satisfaction,
      wish: need.wish,
      note: need.note,
    }
    linkValue.value = need.linked_kind
      ? `${kindPrefix(need.linked_kind)}-${need.linked_kind === 'property' ? need.property_id : need.survival_item_id}`
      : null
  } else {
    form.value = emptyForm()
    linkValue.value = null
  }
})

function resolveLink(value: string | null): {
  property_id: number | null
  survival_item_id: number | null
} {
  if (!value) return { property_id: null, survival_item_id: null }
  const [prefix, raw] = value.split('-')
  const id = Number(raw)
  if (!id) return { property_id: null, survival_item_id: null }
  return prefix === 'property'
    ? { property_id: id, survival_item_id: null }
    : { property_id: null, survival_item_id: id }
}

async function submit() {
  if (!form.value.part_id) {
    ElMessage.warning('选一个部位')
    return
  }
  if (!form.value.name.trim()) {
    ElMessage.warning('写一下这个部位要什么')
    return
  }
  // 🔴 两个关联字段**一起送**：只送一个的话，后端会把老的那个也算进来判互斥 ⇒ 400
  const payload: BodyNeedFormData = {
    part_id: form.value.part_id,
    name: form.value.name.trim(),
    find_status: form.value.find_status,
    // 空串 / null 一律归成 null —— 「没评过」只许有一种送法
    satisfaction: form.value.satisfaction || null,
    wish: form.value.wish,
    note: form.value.note,
    ...resolveLink(linkValue.value),
  }
  try {
    await store.saveNeed(payload, props.needId ?? undefined)
    ElMessage.success(isEdit.value ? '已更新' : '已加一位')
    visible.value = false
    emit('saved')
  } catch (e: unknown) {
    // 🔴 400 里那句「一个位最多只能挂一件东西…」是可照做的提示，原样弹出来
    ElMessage.error(extractApiMessage(e, '保存失败'))
  }
}
</script>

<style scoped>
.body-form__wide {
  width: 100%;
}
.body-form__hint {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
</style>
