<!-- 自我运转 · 人生阶段时间轴（「制定配置」的页内子页面，v3.64.56）
     ────────────────────────────────────────────────────────────
     回答的问题是「我这辈子到现在走过哪几段、接下来还空着哪儿」，
     而不是「这个阶段现在跑得怎么样」—— 后者是页头那两把尺子与本周/月状态。

     🔴 为什么要有这一页：这个模块原来只有「增一个新阶段」和「当前阶段复盘」，
        阶段作为一类对象**没有任何清单** —— 已收尾的那张表 `filter(status='closed')`，
        进行中/暂停的、以及只记一笔的人生阶段，全都没有落点。
        于是「谋生期前 6 年、现在的赎回期、以后的自我价值实现期」在系统里连不起来。

     🔴 两类阶段在同一张时间轴上，但**不能混成一个概念**：
        · 运转型（`run`）= 配 KPI、按周月归档、有判定；
        · 记录型（`record`）= 只记一笔（小学期 / 中学期 / 大学期 …），零 KPI。
        所以记录型标「记录型」并可改可删（它没有周期会被牵连），
        运转型只在别的页管理（改 KPI、收尾归账）——这里**不给**它删除按钮。

     🔴 空档是这一页的重点，不是装饰：两段之间没配阶段的日子要**显式写出来**，
        否则「2029 之后还没想好」这条信息在列表里根本看不见。
        位置与天数全部由后端给（`gap_before` / `tail_gap` / `days`），前端零计算。
-->
<template>
  <el-card shadow="never" class="tl-card">
    <template #header>
      <div class="tl-head">
        <span class="tl-title">人生阶段</span>
        <span class="tl-hint">
          按起点从早到晚。运转型配 KPI、按周月归档；记录型只记一笔，不考核。
        </span>
        <span class="tl-spacer" />
        <span v-if="loaded" class="tl-count">
          {{ t.all }} 段 · 运转型 {{ t.run }} · 记录型 {{ t.record }}
        </span>
        <el-button size="small" type="primary" @click="openCreate">补录一段</el-button>
      </div>
    </template>

    <div v-loading="loading">
      <!-- ① 空态：**说清这一页要等什么**，并给出唯一该做的事 -->
      <el-empty
        v-if="loaded && !view.roots.length"
        :image-size="72"
        description="还没有任何阶段 —— 补录一段已经走过的，或去主视图开一个要跑 KPI 的阶段"
      >
        <el-button size="small" @click="openCreate">补录一段人生阶段</el-button>
      </el-empty>

      <div v-else class="tl-list">
        <template v-for="node in view.roots" :key="node.stage.id">
          <!-- 空档：两段之间没有阶段的日子 -->
          <div v-if="node.gap_before" class="tl-gap">
            <span class="tl-gap-line" />
            <span class="tl-gap-text">{{ node.gap_before.label }}</span>
            <span class="tl-gap-line" />
          </div>

          <div class="tl-row">
            <!-- 左：区间与天数（两处都直接印后端的词，前端不自己拼日期） -->
            <div class="tl-when">
              <div class="tl-range">{{ node.stage.range_label }}</div>
              <div class="tl-days">{{ node.stage.days_label }}</div>
            </div>

            <!-- 中：轴上的一点 -->
            <div class="tl-axis">
              <span class="tl-dot" :class="dotClass(node.stage)" />
            </div>

            <!-- 右：这一段是什么 -->
            <div class="tl-body">
              <div class="tl-title-row">
                <span class="tl-name">{{ node.stage.name }}</span>
                <el-tag size="small" effect="plain" :type="kindTagType(node.stage)">
                  {{ node.stage.stage_kind_display }}
                </el-tag>
                <!-- 记录型的状态词由后端分流成「已记录 / 持续中」，
                     运转型仍是「进行中 / 已收尾」，前端不再判断 -->
                <span class="tl-status" :class="statusClass(node.stage)">
                  {{ node.stage.status_display }}
                </span>
                <span v-if="node.stage.stage_kind === 'run'" class="tl-meta">
                  {{ node.stage.metric_count }} 条 KPI
                </span>
                <span class="tl-spacer" />
                <!-- 🔴 只有记录型给改/删：运转型删了就带走 KPI 与已归档周期 -->
                <template v-if="node.stage.stage_kind === 'record'">
                  <el-button size="small" text type="primary" @click="openEdit(node.stage)">改</el-button>
                  <el-button size="small" text type="danger" @click="askDelete(node.stage)">删</el-button>
                </template>
              </div>

              <div v-if="node.stage.note" class="tl-note">{{ node.stage.note }}</div>

              <!-- 子段：只列，不参与空档（它们被父段包着，不是人生断档） -->
              <div v-if="node.children.length" class="tl-children">
                <div v-for="c in node.children" :key="c.id" class="tl-child">
                  <span class="tl-child-name">{{ c.name }}</span>
                  <span class="tl-child-range">{{ c.range_label }}</span>
                  <span class="tl-child-days">{{ c.days_label }}</span>
                  <span class="tl-spacer" />
                  <!-- 🔴 子段也要按类型分流：子段可以是**运转型小阶段**
                       （「三年赎回期 › 离职适应期」就是），它带着 KPI 和已归档周期。
                       给运转型一个「删」等于让它顺手删掉 9 条 KPI —— 而且不报错。
                       运转型小阶段去主视图改/收尾。 -->
                  <template v-if="c.stage_kind === 'record'">
                    <el-button size="small" text type="primary" @click="openEdit(c)">改</el-button>
                    <el-button size="small" text type="danger" @click="askDelete(c)">删</el-button>
                  </template>
                  <span v-else class="tl-meta">在主视图管理</span>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 尾部空档：最后一段结束之后到今天 -->
        <div v-if="view.tail_gap" class="tl-gap tl-gap--tail">
          <span class="tl-gap-line" />
          <span class="tl-gap-text">{{ view.tail_gap.label }}</span>
          <span class="tl-gap-line" />
        </div>
      </div>
    </div>

    <!-- 底部口径：空档只在「段与段之间」和「最后一段之后」两处产生。
         🔴 第一段**之前**的日子不算空档 —— 那时还没开始配阶段，
            把 1970 到今天全算成空档会得出一个没意义的巨大数字。
            这一点必须写出来：用户看「人生全貌」时第一个问题就是「我前面那 30 年呢」。 -->
    <!-- 🔴 必须同时要求 `roots.length`：只判 `loaded` 的话，一段都没有时
         下面会印出「这几段首尾相接，中间没有空档」+「— 之前尚未开始配置」——
         空库凭空长出一句关于空档的结论。 -->
    <div v-if="loaded && view.roots.length" class="tl-foot">
      <template v-if="t.gap_days > 0">
        空档合计 <b>{{ t.gap_days }}</b> 天<template v-if="view.tail_gap">（含最后一段结束到今天）</template>
        —— 这些日子里没有配阶段。
      </template>
      <template v-else>
        这几段首尾相接，中间<b>没有空档</b>。
      </template>
      <span class="tl-foot-note">
        第一段之前的空白不计入（{{ t.first_start || '—' }} 之前尚未开始配置）。
      </span>
    </div>

    <!-- ── 补录 / 修改一段记录型阶段 ─────────────────────────────── -->
    <el-dialog
      v-model="dlgVisible"
      :title="editing ? '改这一段' : '补录一段人生阶段'"
      width="520px"
      append-to-body
    >
      <el-form label-width="72px" @submit.prevent>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="100" placeholder="例如：谋生期 / 小学期 / 大学期" />
        </el-form-item>
        <el-form-item label="起点" required>
          <el-date-picker
            v-model="form.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="这一段的开始"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="终点">
          <el-date-picker
            v-model="form.end_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="留空 = 持续中"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="editing && editing.parent_name" label="上级">
          <span class="tl-form-static">{{ editing.parent_name }}</span>
          <span class="tl-form-tip">（层级建好后不可改：先删掉再重挂）</span>
        </el-form-item>
        <el-form-item v-else-if="!editing" label="上级">
          <el-select v-model="form.parent" clearable placeholder="不挂，作为顶级一段" style="width: 100%">
            <el-option
              v-for="o in recordOptions"
              :key="o.id"
              :label="o.name"
              :value="o.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="一句话">
          <el-input
            v-model="form.note"
            maxlength="200"
            type="textarea"
            :rows="2"
            placeholder="这段是什么状态（只记事实，不写目标）"
          />
        </el-form-item>
      </el-form>

      <div class="tl-dlg-tip">
        记录型阶段<b>不配 KPI、不产生周月周期、不参与任何判定</b> ——
        它只是把「那几年我在哪儿」留在时间轴上。
      </div>

      <template #footer>
        <el-button @click="dlgVisible = false">算了</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ editing ? '保存' : '记下这一段' }}
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '../api/selfrunApi'
import type { SelfRunStage, StageTimelineResponse } from '../types/selfrunTypes'

const emit = defineEmits<{ changed: [] }>()

const loading = ref(false)
const loaded = ref(false)
const saving = ref(false)
const dlgVisible = ref(false)
const editing = ref<SelfRunStage | null>(null)

const EMPTY: StageTimelineResponse = {
  roots: [],
  tail_gap: null,
  totals: { all: 0, run: 0, record: 0, first_start: null, last_end: null, gap_days: 0 },
  enum: { kind: [] },
  written: {},
}
const view = ref<StageTimelineResponse>(EMPTY)
const t = computed(() => view.value.totals)

const form = reactive({
  name: '',
  start_date: '',
  end_date: '' as string | null,
  note: '',
  parent: null as number | null,
})

/** 可挂的上层候选：**只有记录型**（后端也会拒运转型做父级）。
 *  编辑时排除自己 —— 自己挂到自己下面会让树成环。 */
const recordOptions = computed(() => {
  const out: SelfRunStage[] = []
  for (const r of view.value.roots) {
    if (r.stage.stage_kind === 'record' && r.stage.id !== editing.value?.id) out.push(r.stage)
    for (const c of r.children) {
      if (c.stage_kind === 'record' && c.id !== editing.value?.id) out.push(c)
    }
  }
  return out
})

function kindTagType(s: SelfRunStage) {
  // 运转型=主色（要你动手），记录型=info（只是档案）—— 一眼看出哪类会考核你
  return s.stage_kind === 'run' ? 'primary' : 'info'
}

function dotClass(s: SelfRunStage) {
  if (s.stage_kind === 'record') {
    return s.status_display === '持续中' ? 'is-open' : 'is-record'
  }
  if (s.status === 'active') return 'is-active'
  if (s.status === 'paused') return 'is-paused'
  return 'is-closed'
}

function statusClass(s: SelfRunStage) {
  if (s.stage_kind === 'record') return 'is-record'
  if (s.status === 'active') return 'is-active'
  if (s.status === 'paused') return 'is-paused'
  return 'is-closed'
}

async function load() {
  loading.value = true
  try {
    // ⚠️ `request()` 返回的是 axios 响应体包装（`res.data` 才是数据）——
    //    直接赋值会得到一个 `AxiosResponse`，模板里 `view.roots` 是 undefined，
    //    页面静默渲染成空态（看着像「一段都没有」）。
    const res = await api.getStageTimeline()
    view.value = res.data
    loaded.value = true
  } catch (e: any) {
    // 拉不到就把空态说清 —— 不要静默留一片空白（看着像「这段人生不存在」）
    ElMessage.error(e?.response?.data?.detail ?? '阶段时间轴拉取失败')
    view.value = EMPTY
    loaded.value = true
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.name = ''
  form.start_date = ''
  form.end_date = ''
  form.note = ''
  form.parent = null
  dlgVisible.value = true
}

function openEdit(s: SelfRunStage) {
  editing.value = s
  form.name = s.name
  form.start_date = s.start_date
  form.end_date = s.end_date
  form.note = s.note ?? ''
  form.parent = s.parent
  dlgVisible.value = true
}

async function save() {
  if (!form.name.trim()) return ElMessage.warning('先给它一个名字')
  if (!form.start_date) return ElMessage.warning('起点是这一段唯一的事实，必须填')
  saving.value = true
  try {
    if (editing.value) {
      await api.patchRecordStage(editing.value.id, {
        name: form.name.trim(),
        start_date: form.start_date,
        end_date: form.end_date || null,
        note: form.note,
      })
      ElMessage.success('改好了')
    } else {
      await api.createRecordStage({
        name: form.name.trim(),
        start_date: form.start_date,
        end_date: form.end_date || null,
        note: form.note,
        parent: form.parent || null,
      })
      ElMessage.success('记下了 —— 它只占时间轴上的一格，不会考核你')
    }
    dlgVisible.value = false
    await load()
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function askDelete(s: SelfRunStage) {
  try {
    await ElMessageBox.confirm(
      `删除「${s.name}」？\n\n它只是一条记录：没有 KPI、没有周期、没有打卡，删除不会影响任何数字。\n（运转型阶段不提供删除——那些阶段的结束只有「收尾」。）`,
      '删掉这一段？',
      { confirmButtonText: '删除', cancelButtonText: '算了', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await api.deleteRecordStage(s.id)
    ElMessage.success('已删除')
    await load()
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.tl-card { border-radius: 10px; }
.tl-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.tl-title { font-weight: 600; }
.tl-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }
.tl-spacer { flex: 1; }
.tl-count {
  font-size: 12px; color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.tl-list { display: flex; flex-direction: column; }

/* 一行：区间 | 轴 | 内容。轴用固定宽度的中间列，竖线才能贯穿 */
.tl-row { display: flex; gap: 0; padding: 2px 0; }
.tl-when {
  width: 232px; flex: none; padding: 8px 12px 8px 0; text-align: right;
  font-variant-numeric: tabular-nums;
}
.tl-range { font-size: 12px; color: var(--el-text-color-regular); line-height: 1.5; }
.tl-days { font-size: 12px; color: var(--el-text-color-secondary); }

.tl-axis { width: 22px; flex: none; position: relative; display: flex; justify-content: center; }
/* 竖线：上下都画，首尾由容器裁掉溢出即可（不追求精确首尾封口） */
.tl-axis::before {
  content: ''; position: absolute; top: 0; bottom: 0;
  width: 1px; background: var(--el-border-color);
}
.tl-dot {
  position: relative; margin-top: 12px; width: 9px; height: 9px; border-radius: 50%;
  background: var(--el-text-color-placeholder);
  box-shadow: 0 0 0 3px var(--el-bg-color);
}
.tl-dot.is-active { background: var(--el-color-primary); }
.tl-dot.is-paused { background: var(--el-color-warning); }
.tl-dot.is-closed { background: var(--el-text-color-placeholder); }
.tl-dot.is-record { background: var(--el-color-info-light-3); }
.tl-dot.is-open { background: var(--el-color-success); }

.tl-body {
  flex: 1; min-width: 0; padding: 8px 0 10px 12px;
}
.tl-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tl-name { font-weight: 600; }
.tl-status { font-size: 12px; }
.tl-status.is-active { color: var(--el-color-primary); }
.tl-status.is-paused { color: var(--el-color-warning); }
.tl-status.is-closed,
.tl-status.is-record { color: var(--el-text-color-secondary); }
.tl-meta { font-size: 12px; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.tl-note {
  margin-top: 3px; font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6;
}

.tl-children {
  margin-top: 8px; padding-left: 10px;
  border-left: 2px solid var(--el-border-color-lighter);
}
.tl-child {
  display: flex; align-items: center; gap: 8px; padding: 3px 0;
  font-size: 12px; color: var(--el-text-color-regular);
}
.tl-child-name { font-weight: 500; }
.tl-child-range,
.tl-child-days { color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }

/* 空档：虚线 + 灰字。它要「看着像缺口」，不能用和阶段一样的实线边框 */
.tl-gap { display: flex; align-items: center; gap: 10px; padding: 6px 0 6px 0; }
.tl-gap--tail { padding-bottom: 2px; }
.tl-gap-line { flex: 1; border-top: 1px dashed var(--el-border-color); }
.tl-gap-text { font-size: 12px; color: var(--el-text-color-placeholder); white-space: nowrap; }

.tl-foot {
  margin-top: 12px; padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.7;
}
/* 口径说明比结论更淡：它是「这个数字是怎么算的」，不是结论本身 */
.tl-foot-note { margin-left: 8px; color: var(--el-text-color-placeholder); }
.tl-form-static { color: var(--el-text-color-regular); }
.tl-form-tip { margin-left: 8px; font-size: 12px; color: var(--el-text-color-secondary); }
.tl-dlg-tip {
  margin-top: 4px; padding: 8px 10px; border-radius: 6px;
  background: var(--el-fill-color-lighter);
  font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.7;
}
</style>
