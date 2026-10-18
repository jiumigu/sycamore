<script setup lang="ts">
/**
 * 作品 —— 一件从经历里长出来、以后还能再用的东西。
 *
 * 🔴 这一页**只有一个列表**，不按「期」分组、不做趋势图、不做连续打卡。
 *    它要回答的问题就一个：**你留下了什么。**
 *
 * ⚠️ 「怎么长出来的」不在这里 —— 打勾（四个入口）在各自的页面里，
 *    整理（收口台）在「本周状态」页末的扁条上。这里是**结果**。
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'
import { useWorkStore } from '../stores/workStore'
import ComposeDialog from '../components/ComposeDialog.vue'
import PendingDialog from '../components/PendingDialog.vue'
import { STATUS_TAG } from '../types/workTypes'
import type { Work } from '../types/workTypes'

const store = useWorkStore()

const composeVisible = ref(false)
const pendingVisible = ref(false)
const editVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const form = ref({
  name: '', summary: '', kind: 'article', status: 'private', channel: '', note: '',
})

/** 🔴 可用性判据**不用「列表非空」** —— 一件都没有时汇总是个全 0 的对象（正确），
 *  表没建时是「根本没读上」（没就绪）。两者必须分得开。
 *
 * ⚠️ 就绪判据用 `store.ready`（= `overview` 这个**必然要碰新表**的请求成功了），
 *    **不能**用 `meta` —— 它只读常量 + `SystemPreset`，表没建也回 200。
 * ⚠️ 还得先问「到底试过没有」：首屏 `onMounted` 还没跑，天然是「没就绪」，
 *    只判就绪会让告警**先闪一下**（本地接口快，肉眼像抖了一下）。
 */
const booted = ref(false)
const notReady = computed(() => booted.value && !store.ready)

// ── 计数卡 = 入口 ──────────────────────────────────────────────
// 🔴 四个数里**只有三个是同一种东西**：累计 / 已发出去 / 准备发 都是「作品」本身
//    ⇒ 点它们 = 筛下面那张表。第四个「待提炼」量的是**捕获**（还没成形的东西），
//    它不在这张表里 ⇒ 点它打开明细浮层。
//    同一条规则套不到两类东西上，所以这里**刻意不是四个一样的按钮**。
// ⚠️ 筛选在**前端**做（`store.works` 已经是全量）—— 不再发一次请求，
//    免得「卡上是全量、表里是筛选后」两把尺子对不上。
type WorkFilter = 'all' | 'published' | 'ready'

const workFilter = ref<WorkFilter>('all')

const filteredWorks = computed(() => {
  if (workFilter.value === 'all') return store.works
  return store.works.filter((w) => w.status === workFilter.value)
})

/** 点已选中的那项 = 取消筛选（再点一次回「累计件数」）。 */
function toggleFilter(f: Exclude<WorkFilter, 'all'>) {
  workFilter.value = workFilter.value === f ? 'all' : f
}

/** 🔴 空态文案**按顺序问三句话**：没取到 → 筛选后没有 → 真的还没有。
 *  顺序写反，库读不到时会显示「还没有作品」——
 *  那是用一句看着合理的话把故障盖过去（本项目最怕的那种失败）。 */
const listEmptyText = computed(() => {
  if (notReady.value) return '列表没取到 —— 先看上面那条黄字'
  if (workFilter.value !== 'all') return '这个筛选下没有 —— 点「累计件数」看全部'
  return '还没有作品 —— 从上面「整理这周的标记」开始'
})

/** 状态名取**后端下发的枚举**（`meta.statuses`）。
 *
 *  🔴 卡上与筛选标签必须**同一个词** —— 后端那份是「已发」，
 *     卡上原本手写成「已发出去」，于是同一个筛选在一页上有了两种说法。
 *     不会报错、也不影响功能，只是每次都要在脑子里对一次（这类不一致最难被发现）。
 *  ⚠️ 找不到就退回 key，**不是空串** —— 空串会让标签变成「只看「」」。
 */
function statusLabel(v: Exclude<WorkFilter, 'all'>): string {
  return store.statusOptions.find((o) => o.value === v)?.label ?? v
}

const filterLabel = computed(() =>
  workFilter.value === 'all' ? '' : statusLabel(workFilter.value),
)

/** 从明细浮层去收口台：先关自己再开下一个（同 tick 换浮层会抢滚动锁）。 */
function openComposeFromPending() {
  pendingVisible.value = false
  nextTick(() => {
    composeVisible.value = true
  })
}

onMounted(async () => {
  try {
    await store.loadAll()
  } catch {
    ElMessage.error('读取作品失败')
  } finally {
    booted.value = true
  }
})

function openCreate() {
  editingId.value = null
  form.value = { name: '', summary: '', kind: 'article', status: 'private', channel: '', note: '' }
  editVisible.value = true
}

function openEdit(w: Work) {
  editingId.value = w.id
  form.value = {
    name: w.name, summary: w.summary, kind: w.kind,
    status: w.status, channel: w.channel, note: w.note,
  }
  editVisible.value = true
}

async function submitEdit() {
  if (!form.value.name.trim()) {
    ElMessage.warning('给它起个名字')
    return
  }
  saving.value = true
  try {
    if (editingId.value === null) {
      await store.createWork({ ...form.value })
      ElMessage.success('记下了')
    } else {
      await store.updateWork(editingId.value, { ...form.value })
      ElMessage.success('已更新')
    }
    editVisible.value = false
  } catch (e: any) {
    const d = e?.response?.data
    ElMessage.error(d?.name?.[0] ?? d?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(w: Work) {
  try {
    await ElMessageBox.confirm(
      `删掉「${w.name}」？它的来源会回到待提炼，不会丢。`,
      '删掉这一件',
      { type: 'warning', confirmButtonText: '删掉', cancelButtonText: '再想想' },
    )
  } catch {
    return
  }
  try {
    const res = await store.removeWork(w.id)
    ElMessage.success(res.detail)
  } catch {
    ElMessage.error('删除失败')
  }
}

// ── 导出 ──────────────────────────────────────────────────────
// ⚠️ 在**前端**拼文本，不落库、不走接口 —— 它是「取出去看看」，
//    不是系统里的第二份数据。
function exportText(w: Work): string {
  const lines = [`## ${w.name}`]
  if (w.summary) lines.push('', w.summary)
  lines.push('')
  lines.push(`- 类型：${w.kind_display}`)
  lines.push(`- 出口：${w.status_display}${w.channel ? ` · ${w.channel}` : ''}`)
  if (w.origin.length) {
    lines.push(`- 来自：${w.origin.map((o) => `${o.source_type_display}「${o.title}」`).join('、')}`)
  }
  if (w.note) lines.push(`- 备注：${w.note}`)
  return lines.join('\n')
}

async function copyOne(w: Work) {
  try {
    await navigator.clipboard.writeText(exportText(w))
    ElMessage.success('已复制这一段')
  } catch {
    ElMessage.error('复制失败（浏览器没给剪贴板权限）')
  }
}

function downloadAll() {
  if (!store.works.length) {
    ElMessage.warning('还没有作品')
    return
  }
  const text = store.works.map(exportText).join('\n\n---\n\n')
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `作品-${new Date().toISOString().slice(0, 10)}.md`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="wv">
    <div class="wv-head">
      <div>
        <h2 class="wv-title">作品</h2>
        <p class="wv-sub">
          一件<b>从经历里长出来、以后还能再用</b>的东西 —— 可以只有自己看。
        </p>
      </div>
      <div class="wv-actions">
        <el-button @click="composeVisible = true">整理这周的标记</el-button>
        <el-button @click="downloadAll">导出全部</el-button>
        <el-button type="primary" @click="openCreate">新建一件</el-button>
      </div>
    </div>

    <el-alert
      v-if="notReady"
      type="warning" :closable="false" show-icon
      title="读不到作品数据"
      description="如果刚刚升级，请先执行迁移（selfrun / works / core 三个 app）。"
    />

    <el-card v-else shadow="never" class="wv-counts">
      <div class="wv-counts-row">
        <!-- 「累计件数」= 复位（它不是筛选，所以**没有选中态** ——
             一个常年亮着的大号彩色数字比「少一个高亮」更吵）。 -->
        <button type="button" class="wv-count" @click="workFilter = 'all'">
          <span class="wv-count-num">{{ store.overview?.total ?? 0 }}</span>
          <span class="wv-count-label">累计件数</span>
        </button>
        <button
          type="button"
          class="wv-count"
          :class="{ 'is-active': workFilter === 'published' }"
          @click="toggleFilter('published')"
        >
          <span class="wv-count-num">{{ store.overview?.published ?? 0 }}</span>
          <span class="wv-count-label">{{ statusLabel('published') }}</span>
        </button>
        <button
          type="button"
          class="wv-count"
          :class="{ 'is-active': workFilter === 'ready' }"
          @click="toggleFilter('ready')"
        >
          <span class="wv-count-num">{{ store.overview?.ready ?? 0 }}</span>
          <span class="wv-count-label">{{ statusLabel('ready') }}</span>
        </button>
        <!-- ⚠️「待提炼」数的是**另一类东西**（捕获，还没成形的），它不在这张表里
             ⇒ 点它开明细浮层，**不筛表**。四个一样的按钮在这里是错的。
             ⚠️ 0 条时也**不关掉它** —— 「我到底勾了些什么」正是这时候最想问的。 -->
        <button type="button" class="wv-count is-entry" @click="pendingVisible = true">
          <span class="wv-count-num">{{ store.overview?.pending_captures ?? 0 }}</span>
          <span class="wv-count-label">
            待提炼
            <el-icon class="wv-count-arrow"><ArrowRight /></el-icon>
          </span>
        </button>
      </div>
      <span class="wv-counts-hint">点数字：前三项筛下面的清单 ·「待提炼」看是哪几条</span>
    </el-card>

    <el-card shadow="never" class="wv-list">
      <template #header>
        <div class="wv-list-head">
          <span class="wv-list-title">留下的一件件</span>
          <!-- 筛选是**当下状态**，留在页上（说明才进气泡/提示行）——
               不然「怎么只剩 1 件了」会变成一个要自己猜的谜。 -->
          <el-tag
            v-if="workFilter !== 'all'"
            size="small"
            closable
            @close="workFilter = 'all'"
          >
            只看「{{ filterLabel }}」
          </el-tag>
        </div>
      </template>
      <!-- ⚠️ 空态文案的**顺序有意义**：先问「是不是没取到」，再问「是不是筛掉了」，
           最后才问「是不是真的没有」（见 `listEmptyText`）。
           顺序写反，库读不到时会显示「还没有作品」——
           那是在用一句看着合理的话把故障盖过去。 -->
      <el-table :data="filteredWorks" size="small" :empty-text="listEmptyText">
        <el-table-column prop="name" label="它叫什么" min-width="180">
          <template #default="{ row }">
            <div class="wv-name">{{ row.name }}</div>
            <div v-if="row.summary" class="wv-summary">{{ row.summary }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="kind_display" label="类型" width="82" />
        <el-table-column label="出口" width="130">
          <template #default="{ row }">
            <el-tag :type="STATUS_TAG[row.status as 'private' | 'ready' | 'published']" size="small">
              {{ row.status_display }}
            </el-tag>
            <span v-if="row.channel" class="wv-channel">{{ row.channel }}</span>
          </template>
        </el-table-column>
        <el-table-column label="从哪来" min-width="180">
          <template #default="{ row }">
            <span v-if="!row.origin.length" class="wv-muted">自己记的</span>
            <span v-else class="wv-origin">
              <el-tooltip
                v-for="o in row.origin"
                :key="o.id"
                placement="top"
                :content="`${o.source_type_display} · ${o.title}`"
                :show-after="200"
              >
                <el-tag
                  size="small"
                  effect="plain"
                  class="wv-origin-tag"
                >
                  {{ o.source_type_display }} · {{ o.title }}
                </el-tag>
              </el-tooltip>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="成形于" width="100">
          <template #default="{ row }">{{ (row.created_at ?? '').slice(0, 10) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link size="small" @click="openEdit(row)">改</el-button>
            <el-button link size="small" @click="copyOne(row)">复制</el-button>
            <el-button link size="small" type="danger" @click="remove(row)">删</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建 / 编辑 -->
    <el-dialog
      v-model="editVisible"
      :title="editingId === null ? '新建一件' : '改这一件'"
      width="480px"
    >
      <el-form label-position="top">
        <el-form-item label="它叫什么" required>
          <el-input v-model="form.name" maxlength="120" placeholder="例如：《离职准备 SOP》" />
        </el-form-item>
        <el-form-item label="一句话是什么">
          <el-input
            v-model="form.summary" type="textarea" :rows="2"
            maxlength="200" show-word-limit
          />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.kind" style="width: 100%">
            <el-option v-for="o in store.kindOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="出口">
          <div class="wv-out">
            <el-select v-model="form.status" style="width: 130px">
              <el-option v-for="o in store.statusOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-select v-model="form.channel" clearable placeholder="发到哪（可留空）" style="flex: 1">
              <el-option v-for="ch in store.channelOptions" :key="ch" :label="ch" :value="ch" />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" maxlength="200" show-word-limit placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <ComposeDialog v-model="composeVisible" @done="() => {}" />

    <!-- 待提炼明细 —— 计数卡上那个数点开的样子：只读 + 两个出口
         （不收了 / 去收口台）。在这里**没有**「写一件」的入口。 -->
    <PendingDialog v-model="pendingVisible" @compose="openComposeFromPending" />
  </div>
</template>

<style scoped>
.wv-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; flex-wrap: wrap; margin-bottom: 14px;
}
.wv-title { margin: 0; font-size: 20px; }
.wv-sub { margin: 6px 0 0; font-size: 13px; color: var(--el-text-color-secondary); }
.wv-actions { display: flex; gap: 8px; flex-shrink: 0; }

.wv-counts { margin-bottom: 14px; }
.wv-counts :deep(.el-card__body) {
  display: flex; align-items: center; gap: 20px; padding: 12px 20px;
}
.wv-counts-row { display: flex; gap: 40px; }

/* 🔴 四个数都是**原生 `<button>`**，不是 `el-button`：
   `el-button` 会给相邻按钮塞 `margin-left`、还要覆盖它一堆自带样式；
   更要紧的是它的 `click` 是**自定义事件**，在「透传到根元素」那条路径上
   可能触发两次 —— 这里的表现会是「点一次筛了又取消」（像没反应），
   而且不报错。原生元素只有一条路径。 */
.wv-count {
  display: flex; flex-direction: column; gap: 2px; align-items: flex-start;
  padding: 4px 8px; margin: -4px -8px;
  border: none; border-radius: 6px; background: transparent;
  font: inherit; color: inherit; text-align: left; cursor: pointer;
}
.wv-count:hover { background: var(--el-fill-color-light); }
.wv-count:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 1px; }
.wv-count-num {
  font-size: 22px; font-weight: 600; line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.wv-count-label {
  display: inline-flex; align-items: center; gap: 2px;
  font-size: 12px; color: var(--el-text-color-secondary);
}
/* 选中的筛选项（只有「已发出去 / 准备发」会亮）*/
.wv-count.is-active { background: var(--el-color-primary-light-9); }
.wv-count.is-active .wv-count-num { color: var(--el-color-primary); }
.wv-count.is-active .wv-count-label { color: var(--el-color-primary); }

/* 「待提炼」量的是**另一类东西**（点它开明细，不筛表）⇒
   让它一眼看出「这个和旁边三个不一样」。 */
.wv-count.is-entry .wv-count-label { color: var(--el-color-primary); }
.wv-count.is-entry:hover { background: var(--el-color-primary-light-9); }
.wv-count-arrow { font-size: 12px; }

.wv-counts-hint {
  margin-left: auto;
  font-size: 12px; color: var(--el-text-color-placeholder);
}

.wv-list-head { display: flex; align-items: center; gap: 10px; }
.wv-list-title { font-weight: 600; }
.wv-name { font-weight: 500; }
.wv-summary { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.wv-channel { font-size: 12px; color: var(--el-text-color-secondary); margin-left: 6px; }
.wv-muted { color: var(--el-text-color-secondary); font-size: 12px; }
.wv-origin { display: flex; flex-wrap: wrap; gap: 4px; }
.wv-origin-tag { max-width: 100%; }
/* 🔴 el-tag **内层**文字默认是 `overflow:visible` + `text-overflow:clip` + `min-width:auto`
   （实测计算样式）⇒ 光给外层 `max-width:100%` 只能把**盒子**限住，
   字照旧从盒子里溢出去、并盖到右邻的「成形于」列上 —— 这正是截图里的「硬切」。
   给内层补省略号三件套，`min-width:0` 是让这个 flex 子项能收缩到内容宽度以下。 */
.wv-origin-tag :deep(.el-tag__content) {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wv-out { display: flex; gap: 8px; width: 100%; }
</style>
