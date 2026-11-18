<template>
  <el-card shadow="never" class="oc-card">
    <template #header>
      <div class="oc-head">
        <span>{{ title }}</span>
        <span class="oc-hint">三个来源，各自的数</span>
      </div>
    </template>

    <!-- 三栏各报各的数：同一件事可能既是成品又被记进小确幸，合并成一个总数
         就是重复计数（后端 `_period_outcomes` 顶部有同样的说明）。 -->
    <div class="oc-tally">
      <span class="oc-tally-item">
        <i class="oc-dot works" />出了成品 <b>{{ outcomes.works.count }}</b>
      </span>
      <span class="oc-tally-item">
        <i class="oc-dot milestone" />完成了里程碑 <b>{{ outcomes.milestones.count }}</b>
      </span>
      <span class="oc-tally-item">
        <i class="oc-dot finished" />办完的事 <b>{{ outcomes.finished.count }}</b>
      </span>
    </div>

    <div class="oc-rows">
      <!-- 外层一行 = 一条记录。批阅单独占第二行：它是**人说的话**，
           和右侧那串元数据（属于哪个目标 / 什么类型）不是同一种东西，
           挤进同一行会把两句都截断（v3.64.85）。 -->
      <div v-for="r in rows" :key="r.key" class="oc-item">
        <div class="oc-row">
          <span class="oc-when">{{ r.md }}<i>{{ r.weekday }}</i></span>
          <span class="oc-src" :class="r.kindClass">{{ r.srcLabel }}</span>
          <span class="oc-title">{{ r.title }}</span>
          <span v-if="r.note" class="oc-note">{{ r.note }}</span>
        </div>
        <div v-if="r.review" class="oc-review">{{ r.review }}</div>
      </div>
    </div>

    <div v-if="hints.length" class="oc-foot">
      <span v-for="h in hints" :key="h" class="oc-hint">{{ h }}</span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { OutcomeRow, PeriodOutcomes, PeriodType } from '../types/selfrunTypes'

const props = defineProps<{
  outcomes: PeriodOutcomes
  periodType: PeriodType
}>()

const title = computed(() => (props.periodType === 'monthly'
  ? '这个月，干成了这几件事'
  : '这一周，干成了这几件事'))

/** 三个来源合成一条时间线 —— 前端只做**排序**，不做任何计算。
 *
 * 🔴 每栏的 `count` 是全量、`items` 可能被截断，所以行数少于 `count`
 *    是正常的：底部会说明「还有 N 条」。不许拿 `items.length` 当件数。
 */
interface Row extends OutcomeRow {
  key: string
  srcLabel: string
  kindClass: string
  note: string
  /** 第二行（人写的那句话）。三栏统一成这个键，模板里不必按来源分支。
   *  空串 = 这一条没有可念的话（成品 / 办完的事本来就没有，里程碑是没留下批阅）。 */
  review: string
  /** 插入顺序，仅用于同一天内的稳定排序 */
  seq: number
}

const rows = computed<Row[]>(() => {
  const out: Row[] = []
  for (const it of props.outcomes.works.items) {
    out.push({
      ...it,
      key: `w-${it.id}`,
      srcLabel: '成品',
      kindClass: 'works',
      note: [it.kind, it.status].filter(Boolean).join(' · '),
      review: '',
      seq: out.length,
    })
  }
  for (const it of props.outcomes.milestones.items) {
    out.push({
      ...it,
      key: `m-${it.id}`,
      srcLabel: '里程碑',
      kindClass: 'milestone',
      note: it.goal ? `属于《${it.goal}》` : '',
      review: it.self_review ?? '',
      seq: out.length,
    })
  }
  for (const it of props.outcomes.finished.items) {
    out.push({
      ...it,
      key: `f-${it.id}`,
      // `both` = 收件箱与小确幸都记过（后端已合并成一行）
      srcLabel: it.source === 'inbox' ? '收件箱' : it.source === 'both' ? '两处' : '小确幸',
      kindClass: 'finished',
      note: it.happiness_label ?? '',
      review: '',
      seq: out.length,
    })
  }
  // 日期倒序（ISO 串直接比大小，不解析成 Date）。
  // 🔴 同一天内用 `seq`（= 成品 → 里程碑 → 办完的事，各栏内部保持后端给的时间序），
  //    **不能用 `id` 兜底**：那是跨表的裸 id，作品 5 和里程碑 5 毫无可比性 ——
  //    排出来看着有顺序，其实是撞号（项目铁律：跨表禁止裸 id 当键）。
  return out.sort((a, b) => {
    if (a.date !== b.date) return a.date < b.date ? 1 : -1
    return a.seq - b.seq
  })
})

const hints = computed<string[]>(() => {
  const list: string[] = []
  const { works, milestones, finished } = props.outcomes
  if (finished.untyped_count > 0) {
    list.push(`另有 ${finished.untyped_count} 条小确幸没标快乐类型，未计入`)
  }
  if (works.truncated) list.push(`成品还有 ${works.count - works.items.length} 件未列出`)
  if (milestones.truncated) list.push(`里程碑还有 ${milestones.count - milestones.items.length} 个未列出`)
  if (finished.truncated) list.push(`办完的事还有 ${finished.count - finished.items.length} 条未列出`)
  return list
})
</script>

<style scoped>
.oc-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.oc-hint { font-size: 12px; color: var(--el-text-color-secondary); }

/* 三栏计数：横向一排，窄的时候换行 —— 抽屉 720px 下正常是一行 */
.oc-tally {
  display: flex; flex-wrap: wrap; align-items: center; gap: 18px;
  padding-bottom: 10px; margin-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.oc-tally-item {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--el-text-color-regular);
}
.oc-tally-item b {
  font-size: 16px; color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}
.oc-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.oc-dot.works { background: #7C6BD6; }
.oc-dot.milestone { background: #E0A33E; }
.oc-dot.finished { background: #3FA37A; }

.oc-rows { display: flex; flex-direction: column; gap: 2px; }
/* 一条记录 = 一行元数据 +（可能）一行批阅。分隔线挂在**记录**上，
   不挂在元数据行上 —— 否则批阅会被画到线的下方，看起来属于下一条。 */
.oc-item {
  padding: 5px 0;
  border-bottom: 1px dashed var(--el-border-color-extra-light);
}
.oc-item:last-child { border-bottom: none; }
.oc-row {
  display: flex; align-items: baseline; gap: 8px;
  font-size: 13px;
}
/* 批阅：左侧细线表示「这属于上一条」，不靠颜色 —— 颜色不解释自己 */
.oc-review {
  margin: 3px 0 0 80px;
  padding-left: 8px;
  border-left: 2px solid var(--el-border-color);
  font-size: 12px; line-height: 1.6;
  color: var(--el-text-color-regular);
  /* textarea 里敲的换行要留住；压成一行会把「分两件事写」读成一句话 */
  white-space: pre-wrap;
  overflow-wrap: break-word;
}
.oc-when {
  flex: none; width: 72px; font-variant-numeric: tabular-nums;
  color: var(--el-text-color-regular);
}
/* `.oc-when` 里的星期不占宽度：它跟着日期走，换行时不该把日期挤断 */
.oc-when i {
  font-style: normal; font-size: 11px;
  color: var(--el-text-color-secondary); margin-left: 4px;
}
/* 来源标用**文字**不用纯色：颜色不解释自己，一眼看不出「成品」和「里程碑」的差别 */
.oc-src {
  flex: none; font-size: 11px; padding: 0 6px; border-radius: 3px;
  line-height: 18px; white-space: nowrap;
}
.oc-src.works { background: #EEEAFB; color: #5B4BA8; }
.oc-src.milestone { background: #FBF0DC; color: #9A6B14; }
.oc-src.finished { background: #E6F5EE; color: #2C7A5B; }
.oc-title { flex: 1; min-width: 0; color: var(--el-text-color-primary); }
.oc-note {
  flex: none; max-width: 38%; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
  font-size: 12px; color: var(--el-text-color-secondary);
}
.oc-foot { display: flex; flex-direction: column; gap: 2px; margin-top: 8px; }
</style>
