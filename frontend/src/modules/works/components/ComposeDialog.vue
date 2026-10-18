<script setup lang="ts">
/**
 * 收口台 —— 把「这周标记的东西」合成一件作品。
 *
 * 🔴 这是「编译」这个动作在界面上的形态：左边是散落的原材料，
 *    右边是成品的样子。**①只打勾、②才写字** —— 那个勾在各自的页面上已经打过了，
 *    这里是你**一周后回头看**时做的事。
 *
 * ⚠️ 刻意**不做**「一条都不选也能提交」：那它就从「收口」退化成
 *    「又一个新建入口」，同一件事会有两个录入口（项目铁律）。
 *    想随手记一件 ⇒ 去作品页点「新建」。
 *
 * 🔴 每一行必须**看得出是什么**：只给一个来源标签（里程碑 / 摘录 / 日记）
 *    等于只有序号 —— 用户原话是「有效信息太少」。所以每行两行：
 *    ① 标题（强）；② 当时留下的那段摘要（弱，单行，悬停看全文）。
 *    标题与摘要常常是同一段话 ⇒ 由 `captureText()` 去重，见它的文件头。
 *
 * 🔴 **样式里必须显式写 `line-height`** —— 这行是踩出来的：
 *    `el-checkbox-group` 自带 `.el-checkbox-group{font-size:0;line-height:0}`
 *    （Element 用它消掉组内空白），我的 `.cp-title` 只覆盖了 `font-size`、
 *    没覆盖 `line-height` ⇒ **继承到 0** ⇒ 盒子高度算出来是 **0px** ⇒
 *    标题被 `overflow:hidden`（为了省略号）整个裁掉、页面上一片空白。
 *    不报错、`vue-tsc` 也看不见；来源标签侥幸可见只是因为它 `overflow:visible`
 *    （字溢出了那个 2px 的盒子）。⇒ 任何放进 checkbox / radio 组里的
 *    **自定义内容**，都要自己兜住 `line-height`。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useWorkStore } from '../stores/workStore'
import type { WorkCapture } from '../types/workTypes'
import { SOURCE_SHORT } from '../types/workTypes'
import { captureText } from '../utils/captureText'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'done', workName: string): void
}>()

const store = useWorkStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const picked = ref<number[]>([])
const saving = ref(false)

const form = ref({
  name: '',
  summary: '',
  kind: 'article',
  status: 'private',
  channel: '',
  note: '',
})

/** 本期勾的（不论是否已提炼）与更早还挂着的，**分开摆** —— 免得看不出哪些是新的。 */
const thisPeriod = computed(() => store.currentCaptures.filter((c) => c.status === 'pending'))
const olderPending = computed(() => store.pendingCaptures.filter((c) => !c.in_current_period))

/** 已收进作品的（只读展示：让人看见「这些已经用掉了」）。 */
const usedThisPeriod = computed(() =>
  store.currentCaptures.filter((c) => c.status === 'used'),
)

/** 行视图模型：标题/正文在这里算一次，别在模板里对同一行算三遍。 */
interface Row { c: WorkCapture; title: string; body: string }

function toRows(list: WorkCapture[]): Row[] {
  return list.map((c) => ({ c, ...captureText(c) }))
}

const thisRows = computed<Row[]>(() => toRows(thisPeriod.value))
const olderRows = computed<Row[]>(() => toRows(olderPending.value))
const usedRows = computed<Row[]>(() => toRows(usedThisPeriod.value))

const allRows = computed<Row[]>(() => [...thisRows.value, ...olderRows.value])

watch(visible, async (open) => {
  if (!open) return
  picked.value = []
  form.value = { name: '', summary: '', kind: 'article', status: 'private', channel: '', note: '' }
  try {
    await store.loadCaptures()
  } catch {
    ElMessage.error('读取待提炼失败')
  }
})

/** 勾选变化统一走这里：把第一条的标题填进「名称」—— 省一次打字，但**允许改**。
 *
 * ⚠️ 只在名称还空着时自动填 —— 反过来（自动覆盖）会把用户刚打的字吃掉，
 *    而且**不报错**，看着像输入法吞字。
 */
function setPicked(ids: number[]) {
  picked.value = ids
  if (!form.value.name && ids.length) {
    const first = allRows.value.find((r) => r.c.id === ids[0])
    if (first?.title) form.value.name = first.title.slice(0, 40)
  }
}

function togglePick(id: number) {
  setPicked(
    picked.value.includes(id)
      ? picked.value.filter((x) => x !== id)
      : [...picked.value, id],
  )
}

/** 点行的空白处也能勾 —— 只让「勾选框」可点，一行里就会出现一片死区。
 *
 * 🔴 但**必须把勾选框和按钮自己排除掉**：它们的点击会冒泡到这一层，
 *    不排除就变成「点一下勾 = 勾上又被撤掉」，看着像控件坏了。
 *    判据看**事件源**（`closest`），不赌 Element 把 `@click.stop` 绑在哪一层 ——
 *    `el-button` 声明了 `click` 事件、`el-checkbox` 没声明，两者的修饰符行为不同，
 *    这种事不该靠记忆。
 *
 * ⚠️ 也不把行做成 `<label>`：Element 的 `el-checkbox` 根元素**本身就是 `<label>`**，
 *    再套一层是嵌套 label（无效 HTML），点里面的按钮会连带改勾选。
 */
function onRowClick(e: MouseEvent, id: number) {
  const t = e.target as HTMLElement | null
  if (t?.closest('.el-checkbox') || t?.closest('button')) return
  togglePick(id)
}

async function removeCapture(id: number) {
  try {
    await store.undoCapture(id)
    picked.value = picked.value.filter((x) => x !== id)
    ElMessage.success('已取消标记')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '取消失败')
  }
}

async function submit() {
  if (!picked.value.length) return
  saving.value = true
  try {
    const work = await store.composeWork({
      capture_ids: picked.value,
      ...form.value,
    })
    ElMessage.success(`已合成「${work.name}」`)
    emit('done', work.name)
    visible.value = false
  } catch (e: any) {
    const d = e?.response?.data
    ElMessage.error(d?.capture_ids?.[0] ?? d?.name?.[0] ?? '合成失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="这周留下的东西 —— 整理成一件"
    width="820px"
    top="6vh"
  >
    <div class="cp-body">
      <!-- 左：原材料 -->
      <div class="cp-left">
        <div class="cp-sec">
          <div class="cp-sec-head">
            <span>这周标记的</span>
            <el-tag v-if="thisRows.length" size="small" type="primary" effect="plain">
              {{ thisRows.length }} 条
            </el-tag>
          </div>
          <div v-if="!thisRows.length" class="cp-empty">
            这周还没打勾。完成里程碑 / 收件箱条目、读完一本书、给日记打上「值得留」标签、
            或把摘录 / AI 问答标为「值得留」，它们会出现在这里。
          </div>
          <el-checkbox-group
            v-else
            :model-value="picked"
            class="cp-list"
            @update:model-value="setPicked($event as number[])"
          >
            <div
              v-for="r in thisRows"
              :key="r.c.id"
              class="cp-row"
              @click="onRowClick($event, r.c.id)"
            >
              <el-checkbox :value="r.c.id" class="cp-check" />
              <span class="cp-tag">{{ SOURCE_SHORT[r.c.source_type] ?? r.c.source_type_display }}</span>
              <div class="cp-main">
                <div class="cp-line">
                  <span class="cp-title" :title="r.c.title">{{ r.title }}</span>
                </div>
                <div v-if="r.body" class="cp-sub" :title="r.c.excerpt">{{ r.body }}</div>
              </div>
              <el-button link size="small" class="cp-act" @click="removeCapture(r.c.id)">
                取消标记
              </el-button>
            </div>
          </el-checkbox-group>
        </div>

        <div v-if="olderRows.length" class="cp-sec">
          <div class="cp-sec-head">
            <span>更早还挂着的</span>
            <el-tag size="small" type="info" effect="plain">{{ olderRows.length }} 条</el-tag>
          </div>
          <el-checkbox-group
            :model-value="picked"
            class="cp-list"
            @update:model-value="setPicked($event as number[])"
          >
            <!-- ⚠️ 这一段**也要有「不收了」的出口** ——
                 不然上周没提炼的会一直挂在这儿，只能攒着，
                 而「攒着」看起来像 bug（「这些我早不想要了，怎么删不掉」）。 -->
            <div
              v-for="r in olderRows"
              :key="r.c.id"
              class="cp-row"
              @click="onRowClick($event, r.c.id)"
            >
              <el-checkbox :value="r.c.id" class="cp-check" />
              <span class="cp-tag">{{ SOURCE_SHORT[r.c.source_type] ?? r.c.source_type_display }}</span>
              <div class="cp-main">
                <div class="cp-line">
                  <span class="cp-title" :title="r.c.title">{{ r.title }}</span>
                  <span class="cp-when">{{ (r.c.captured_at ?? '').slice(0, 10) }}</span>
                </div>
                <div v-if="r.body" class="cp-sub" :title="r.c.excerpt">{{ r.body }}</div>
              </div>
              <el-button link size="small" class="cp-act" @click="removeCapture(r.c.id)">
                不收了
              </el-button>
            </div>
          </el-checkbox-group>
        </div>

        <div v-if="usedRows.length" class="cp-sec">
          <div class="cp-sec-head">
            <span>这周已经用掉的</span>
            <el-tag size="small" type="success" effect="plain">{{ usedRows.length }} 条</el-tag>
          </div>
          <div class="cp-list">
            <div v-for="r in usedRows" :key="r.c.id" class="cp-row cp-row-done">
              <span class="cp-tag">{{ SOURCE_SHORT[r.c.source_type] ?? r.c.source_type_display }}</span>
              <div class="cp-main">
                <div class="cp-line">
                  <span class="cp-title">{{ r.title }}</span>
                </div>
                <div v-if="r.body" class="cp-sub">{{ r.body }}</div>
              </div>
              <span class="cp-when">→ {{ r.c.work_name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右：成品 -->
      <div class="cp-right">
        <el-form label-position="top" size="default">
          <el-form-item label="它叫什么" required>
            <el-input v-model="form.name" maxlength="120" placeholder="例如：《装修避坑清单》" />
          </el-form-item>
          <el-form-item label="一句话是什么">
            <el-input
              v-model="form.summary"
              type="textarea"
              :rows="2"
              maxlength="200"
              show-word-limit
              placeholder="给三个月后的自己看的一句话"
            />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="form.kind" style="width: 100%">
              <el-option
                v-for="o in store.kindOptions"
                :key="o.value"
                :label="o.label"
                :value="o.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="出口">
            <div class="cp-out">
              <el-select v-model="form.status" style="width: 130px">
                <el-option
                  v-for="o in store.statusOptions"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
              <el-select
                v-model="form.channel"
                clearable
                placeholder="发到哪（可留空）"
                style="flex: 1"
              >
                <el-option v-for="ch in store.channelOptions" :key="ch" :label="ch" :value="ch" />
              </el-select>
            </div>
          </el-form-item>
        </el-form>
        <div class="cp-hint">
          「只给自己」也是一种出口 —— 一份《避坑清单》本来就不必发出去。
        </div>
      </div>
    </div>

    <template #footer>
      <div class="cp-foot">
        <span class="cp-foot-hint">
          <template v-if="picked.length">选了 {{ picked.length }} 条</template>
          <template v-else>至少选一条 —— 想随手记一件，去作品页点「新建」</template>
        </span>
        <span>
          <el-button @click="visible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="saving"
            :disabled="!picked.length || !form.name.trim()"
            @click="submit"
          >
            合成一件
          </el-button>
        </span>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.cp-body { display: flex; gap: 16px; align-items: flex-start; }
.cp-left { flex: 1; min-width: 0; max-height: 56vh; overflow-y: auto; padding-right: 4px; }
.cp-right { width: 300px; flex-shrink: 0; }

.cp-sec + .cp-sec { margin-top: 14px; }
.cp-sec-head {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 600; color: var(--el-text-color-regular);
  margin-bottom: 6px;
}
.cp-empty {
  font-size: 12px; line-height: 1.8; color: var(--el-text-color-secondary);
  padding: 10px 12px; border-radius: 6px;
  background: var(--el-fill-color-light);
}
.cp-list { display: flex; flex-direction: column; }

/* 🔴 `line-height` 是**必须**的，不是随手加的：
   上面那层 `el-checkbox-group` 带着 `line-height: 0`（Element 用它消组内空白），
   不在这里兜住 ⇒ 标题盒子算出来是 0px，再被下面的 `overflow: hidden` 裁掉。
   见文件头。 */
.cp-list {
  display: flex; flex-direction: column;
  /* 同一件事在**源头**再兜一次：这个元素就是 `el-checkbox-group` 的根，
     `font-size: 0` / `line-height: 0` 是它带下来的 —— 从这里顶掉，
     以后往行里加任何自定义内容都不必再各自记着写 line-height。 */
  font-size: 14px; line-height: 1.5;
}
.cp-row {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 6px; border-radius: 5px; margin: 0;
  cursor: pointer;
  line-height: 1.5;
}
.cp-row:hover { background: var(--el-fill-color-light); }
.cp-row-done { cursor: default; opacity: 0.75; }
.cp-row-done:hover { background: transparent; }

/* 勾选框高度压到一行文字那么高 —— 默认 32px 会把两行的行高撑起来；
   顺带把默认的 `margin-right: 30px` 归零（间距统一交给容器的 gap）。 */
.cp-check {
  flex-shrink: 0; height: 20px; margin-right: 0; margin-top: 1px;
}

.cp-tag {
  flex-shrink: 0; margin-top: 1px;
  font-size: 11px; line-height: 1.6; padding: 0 6px; border-radius: 4px;
  background: var(--el-fill-color); color: var(--el-text-color-secondary);
}

.cp-main { flex: 1; min-width: 0; }
.cp-line { display: flex; align-items: baseline; gap: 8px; }
.cp-title {
  flex: 1; min-width: 0; font-size: 13px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cp-sub {
  margin-top: 1px; font-size: 12px; color: var(--el-text-color-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cp-when {
  flex-shrink: 0; font-size: 12px; color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}
.cp-act { flex-shrink: 0; }

.cp-out { display: flex; gap: 8px; width: 100%; }
.cp-hint {
  font-size: 12px; line-height: 1.7; color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.cp-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.cp-foot-hint { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
