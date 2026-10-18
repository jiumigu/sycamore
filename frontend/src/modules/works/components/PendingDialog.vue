<script setup lang="ts">
/**
 * 待提炼明细 —— 作品页计数卡上「待提炼」那个数点开的样子。
 *
 * 🔴 它回答的问题只有一个：**那几条到底是什么。**
 *    在这之前那个数是个死数字 —— 知道有 8 条，但看不见是哪 8 条，
 *    于是「8」既没法核对、也没法处理（用户原话：「点开可以看到对应明细」）。
 *
 * ⚠️ 这个浮层是**只读**的，并且刻意如此：合成只有收口台一条路
 *    （同一件事不许两个录入口）。它给两个出口，都不是「在这里写一件」：
 *      · 不收了  ⇒ 撤销那条标记（它是个标记，不是流水，可以真删）；
 *      · 去整理  ⇒ 关掉自己、打开收口台（把「看」交回给「做」）。
 *    所以这不是收口台的第二份实现：那边是「把散的东西收成一件」（写），
 *    这边是「我到底勾了些什么」（读）。
 *
 * ⚠️ 分组口径与收口台**同一把尺子** —— `in_current_period` 由后端判并下发，
 *    这里**不**自己比 `period_key` 字符串（自己算跨年会静默差一周）。
 *
 * ⚠️ 计数卡上的数来自 `overview.pending_captures`(后端 COUNT)，
 *    这里的行来自 `captures` 列表 —— 两条路必须是同一把尺子。
 *    已核对：`GET /works/captures/` **不带期筛选**（`period_type` 只用来算
 *    `in_current_period`），所以列表就是全量 ⇒ 数 = 行数。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { useWorkStore } from '../stores/workStore'
import { SOURCE_SHORT } from '../types/workTypes'
import type { WorkCapture } from '../types/workTypes'
// 「标题 / 摘要」怎么摆，与收口台**共用一份** ——
// 各写一份的话，同一件事在两个地方会长得不一样，而且不报错。
import { captureText } from '../utils/captureText'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'compose'): void
}>()

const store = useWorkStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const loading = ref(false)
const dropping = ref<number | null>(null)

/** 这周勾的 / 更早还挂着的 —— 与收口台同款分法（不然「哪些是新的」看不出来）。 */
const thisPeriod = computed(() => store.pendingCaptures.filter((c) => c.in_current_period))
const older = computed(() => store.pendingCaptures.filter((c) => !c.in_current_period))

type GroupTag = 'primary' | 'info'

/** 行视图模型：标题 / 正文在这里算一次（`captureText` 会把与标题重复的摘要去掉）。 */
interface PdRow { c: WorkCapture; title: string; body: string }

function toRows(list: WorkCapture[]): PdRow[] {
  return list.map((c) => ({ c, ...captureText(c) }))
}

/** 摊成组再渲染：**同一份行模板只写一次** ——
 *  写两遍的话，以后改一处忘另一处，两段会长得不一样（而且不报错）。 */
const groups = computed<{ key: string; label: string; tag: GroupTag; rows: PdRow[] }[]>(
  () => {
    const out: { key: string; label: string; tag: GroupTag; rows: PdRow[] }[] = []
    if (thisPeriod.value.length) {
      out.push({ key: 'now', label: '这周标记的', tag: 'primary', rows: toRows(thisPeriod.value) })
    }
    if (older.value.length) {
      out.push({ key: 'old', label: '更早还挂着的', tag: 'info', rows: toRows(older.value) })
    }
    return out
  },
)

watch(visible, async (open) => {
  if (!open) return
  loading.value = true
  try {
    // 每次打开都重拉 —— 数字是别处的动作改的（七个入口打勾、删作品退回），
    // 缓存下来的列表会与卡上的数对不上，而那种「对不上」不报错。
    await store.loadCaptures()
  } catch {
    ElMessage.error('读取待提炼失败')
  } finally {
    loading.value = false
  }
})

/** `2026-10-14T16:30:00+08:00` → `10-14 16:30`。
 *  ⚠️ 只用于本浮层：这里「几点了」比「哪一天」有用（今天勾的都在当天）。
 *    日期展示项目里各页自带一份，**不在这里再造一个通用件**。 */
function when(iso: string | null): string {
  return (iso ?? '').slice(5, 16).replace('T', ' ')
}

/** 标签优先用短名（与收口台一致）；后端多出一个来源时**退回后端名**，
 *  而不是渲染成空白 —— 键名对不上是静默失败的高发区。 */
function sourceLabel(c: WorkCapture): string {
  return SOURCE_SHORT[c.source_type] ?? c.source_type_display
}

async function drop(c: WorkCapture) {
  dropping.value = c.id
  try {
    await store.undoCapture(c.id)
    ElMessage.success('已取消标记')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '取消失败')
  } finally {
    dropping.value = null
  }
}

function goCompose() {
  visible.value = false
  emit('compose')
}
</script>

<template>
  <el-dialog v-model="visible" width="680px" top="7vh">
    <template #header>
      <div class="pd-head">
        <span class="pd-head-title">待提炼</span>
        <span class="pd-head-sub">
          打了勾、还没收成一件的 —— 一共 {{ store.pendingCaptures.length }} 条
        </span>
      </div>
    </template>

    <div v-loading="loading" class="pd-body">
      <div v-if="!store.pendingCaptures.length" class="pd-empty">
        <p class="pd-empty-lead">没有待提炼的东西。</p>
        <p>
          勾过的都已经收进作品里了。<br />
          想再攒：在里程碑 / 收件箱 / 读书 / 日记 / 摘录 / AI 问答这些页面上，
          点一下「值得留」就行 —— <b>不用现在写任何字</b>。
        </p>
      </div>

      <div v-for="g in groups" v-else :key="g.key" class="pd-sec">
        <div class="pd-sec-head">
          <span>{{ g.label }}</span>
          <el-tag size="small" :type="g.tag" effect="plain">{{ g.rows.length }} 条</el-tag>
        </div>
        <div v-for="r in g.rows" :key="r.c.id" class="pd-row">
          <span class="pd-tag">{{ sourceLabel(r.c) }}</span>
          <div class="pd-main">
            <div class="pd-title">{{ r.title }}</div>
            <!-- ⚠️ 「摘要为空」有两种意思，别混成一种：
                 ① 当时真没带摘要  ⇒ 说一句「只记了标题」；
                 ② 摘要就是标题的加长版（摘录 / AI 问答那两类）⇒ 去重后本来就该是空的，
                    那是**正常**，不该说「没带摘要」。见 `captureText`。 -->
            <div v-if="r.body" class="pd-excerpt" :title="r.c.excerpt">{{ r.body }}</div>
            <div v-else-if="!r.c.excerpt" class="pd-bare">当时只记了标题，没带摘要</div>
          </div>
          <span class="pd-when">{{ when(r.c.captured_at) }}</span>
          <el-button
            link
            size="small"
            type="danger"
            :loading="dropping === r.c.id"
            @click="drop(r.c)"
          >
            不收了
          </el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="pd-foot">
        <span class="pd-foot-hint">这里只是看 —— 要把它们收成一件，去收口台。</span>
        <span>
          <el-button @click="visible = false">知道了</el-button>
          <el-button type="primary" @click="goCompose">去整理成一件 →</el-button>
        </span>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.pd-head { display: flex; align-items: baseline; gap: 10px; }
.pd-head-title { font-size: 16px; font-weight: 600; }
.pd-head-sub { font-size: 12px; color: var(--el-text-color-secondary); }

/* ⚠️ 60vh 时 8 条刚好差一点点装不下 —— 最后一行被切在滚动边界上，
   看着像「内容被截断了」（而不是「可以滚」）。66vh 让常见条数整屏装完。 */
.pd-body { max-height: 66vh; overflow-y: auto; padding-right: 4px; }

.pd-empty { font-size: 13px; line-height: 1.9; color: var(--el-text-color-secondary); }
.pd-empty-lead { color: var(--el-text-color-regular); font-weight: 500; }
.pd-empty p { margin: 0 0 6px; }

.pd-sec + .pd-sec { margin-top: 16px; }
.pd-sec-head {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 600; color: var(--el-text-color-regular);
  margin-bottom: 6px;
}
.pd-row {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 7px 6px; border-radius: 5px;
}
.pd-row:hover { background: var(--el-fill-color-light); }
.pd-row + .pd-row { border-top: 1px solid var(--el-border-color-lighter); }

.pd-tag {
  flex-shrink: 0; margin-top: 1px;
  font-size: 11px; padding: 1px 6px; border-radius: 4px;
  background: var(--el-fill-color); color: var(--el-text-color-secondary);
}
.pd-main { flex: 1; min-width: 0; }
.pd-title { font-size: 13px; line-height: 1.5; word-break: break-word; }
.pd-excerpt {
  margin-top: 2px; font-size: 12px; line-height: 1.6;
  color: var(--el-text-color-secondary);
  word-break: break-word;
  /* 🔴 摘要最长 300 字（后端截的）⇒ 不封顶时一条能占 8 行，
         这个列表就**扫不动**了 —— 而「看出是哪几条」正是它存在的理由。
         封 3 行，全文挂 `title`（悬停可见）；要读整条请回它自己的页面。 */
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}
.pd-bare { margin-top: 2px; font-size: 12px; font-style: italic; color: var(--el-text-color-placeholder); }
.pd-when {
  flex-shrink: 0; margin-top: 1px;
  font-size: 12px; color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.pd-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.pd-foot-hint { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
