<!--
  两秒快记 · 评价徽标（v3.60.32）

  物件资产 / 物品清单的列表行内共用这一个组件。它回答的是
  「这件东西我觉得值不值」—— 与 `status`（我还要不要它）、`condition`
  （它好不好使）是**三把正交的尺子**，界面上并列显示、互不推导。

  ## 三条交互判据（都是「用户愿意随手做」的前提）

  1. 🔴 **理由可以留空。** 要求必填理由，用户就会攒着不做；允许留空，
     他先留下标识、回头再补。留空的前提是「没填」这件事**看得见** ——
     档案馆页头有「N 条待补理由」的出口。
  2. ⚠️ **类别有预填，但不猜死。** 预填值来自后端按物件类别给的建议；
     猜不出就留空、提交时提示选一次。**绝不在前端硬编码一个默认类别。**
  3. ⚠️ **已评价时点徽标 = 打开那条档案去补理由**，不是再建一条
     （后端 1:1 唯一约束也会把第二条拦成 400，但界面不该让人走到那一步）。

  ## 为什么不放 `shared/components/`

  两个使用点都在 wealth 模块内，而它要 import treasure 模块的 api ——
  放进 `shared/` 会让 shared **反向依赖 module**，破坏既有的分层。
-->

<template>
  <span class="quick-mark" @click.stop>
    <!-- 已有评价：实色徽标，点击去那条档案补理由 -->
    <el-tag
      v-if="badge"
      class="quick-mark__badge"
      :type="badge === '歹' ? 'danger' : 'success'"
      size="small"
      effect="dark"
      @click="openRecord"
    >
      {{ badge === '歹' ? '👎 踩坑' : '👍 好物' }}
    </el-tag>

    <!-- 还没有评价：两个淡色小按钮（不抢视觉重量） -->
    <el-popover
      v-else
      v-model:visible="visible"
      trigger="click"
      placement="left"
      :width="290"
      :persistent="false"
    >
      <template #reference>
        <span class="quick-mark__buttons">
          <!-- ⚠️ `.stop` 不是装饰：popover 的 trigger="click" 绑在这个 reference 上，
               不阻止冒泡的话同一次点击会被消费两遍 —— 我们设 visible=true，
               trigger 紧接着 toggle 回 false ⇒ 用户看到的是「点了没反应」（§67）。 -->
          <el-button link size="small" class="quick-mark__btn" @click.stop="open('好')">👍</el-button>
          <el-button link size="small" class="quick-mark__btn" @click.stop="open('歹')">👎</el-button>
        </span>
      </template>

      <div class="quick-mark__panel">
        <div class="quick-mark__title">
          给「{{ name }}」记一条 {{ pendingType === '歹' ? '👎 踩坑' : '👍 好物' }}
        </div>

        <el-input
          v-model="reason"
          type="textarea"
          :rows="2"
          maxlength="500"
          placeholder="理由（可留空，以后再补）"
        />

        <div class="quick-mark__row">
          <span class="quick-mark__label">类别</span>
          <el-select
            v-model="category"
            size="small"
            placeholder="选一个"
            class="quick-mark__select"
            :teleported="false"
          >
            <el-option
              v-for="option in categories"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>

        <!-- 记录类型**建议**：物件状况坏了 ⇒ 提示一句，**绝不自动改** -->
        <div v-if="pendingType === '好' && condition === 'broken'" class="quick-mark__hint">
          这件物件的状况是「坏了」—— 要不要改记成 👎 歹物？
        </div>

        <div class="quick-mark__actions">
          <el-button size="small" @click="visible = false">取消</el-button>
          <el-button size="small" type="primary" :loading="saving" @click="submit">
            记下
          </el-button>
        </div>
      </div>
    </el-popover>
  </span>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useTreasureStore } from '@/modules/treasure/stores/treasureStore'
import * as treasureApi from '@/modules/treasure/api/treasureApi'
import { apiErrorText } from '@/shared/utils/apiError'

const props = defineProps<{
  kind: 'property' | 'survival_item'
  targetId: number
  name: string
  /** `null` = 还没评过 ⇒ 只显示两个淡色入口 */
  badge: string | null
  /** 已有评价时那条档案的 id（点徽标跳过去补理由） */
  recordId: number | null
  /** 后端按物件类别给的预填建议；猜不出是空串 */
  suggestCategory?: string
  /** 物件状况（物品清单没有这个字段，传空串） */
  condition?: string
}>()

const emit = defineEmits<{ saved: [] }>()

const router = useRouter()
const store = useTreasureStore()

const visible = ref(false)
const saving = ref(false)
const pendingType = ref<'好' | '歹'>('好')
const reason = ref('')
const category = ref('')

const categories = computed(() => store.categoriesFor(pendingType.value))

function open(type: '好' | '歹') {
  pendingType.value = type
  reason.value = ''
  // 预填建议；猜不出就留空（提交时提示选一次，不硬塞一个看着合理的值）
  category.value = props.suggestCategory || ''
  visible.value = true
}

function openRecord() {
  if (!props.recordId) return
  // 跳回档案馆并聚焦那一条 —— 「补理由」而不是「再登记一条」
  router.push({ path: '/treasure', query: { focus: String(props.recordId) } })
}

async function submit() {
  if (!category.value) {
    ElMessage.warning('选一个类别 —— 实物得有归属，方法才不用')
    return
  }
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      record_type: pendingType.value,
      subject_kind: '实物',
      name: props.name,
      category: category.value,
      [props.kind]: props.targetId,
    }
    if (pendingType.value === '好') payload.why_good = reason.value.trim()
    else payload.avoid_reason = reason.value.trim()

    await treasureApi.createThing(payload)
    ElMessage.success('已记下 —— 理由留空的话，去档案馆能一眼看到「待补」')
    visible.value = false
    emit('saved')
  } catch (err) {
    // 4xx 原样透出（「这件实物已经有一条评价了」是可行动的）
    ElMessage.error(apiErrorText(err, '记不下来'))
  } finally {
    saving.value = false
  }
}

onMounted(() => { store.fetchMeta() })
</script>

<style scoped>
.quick-mark {
  display: inline-flex;
  align-items: center;
}
.quick-mark__badge {
  cursor: pointer;
}
.quick-mark__buttons {
  display: inline-flex;
  gap: 2px;
}
.quick-mark__btn {
  /* 淡色：行内入口不抢视觉重量 */
  opacity: 0.55;
  padding: 0 2px;
}
.quick-mark__btn:hover {
  opacity: 1;
}
.quick-mark__panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.quick-mark__title {
  font-size: 13px;
  font-weight: 600;
}
.quick-mark__row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.quick-mark__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.quick-mark__select {
  width: 130px;
}
.quick-mark__hint {
  font-size: 12px;
  color: var(--el-color-warning);
  line-height: 1.5;
}
.quick-mark__actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}
</style>
