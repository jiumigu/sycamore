<template>
  <div class="attr-note">
    <el-alert
      type="info" :closable="false" show-icon
      title="归因只剩一处真源：任务清单 → 分类映射编辑器 → L1 归因"
      description="本页不再写归因。六类小时、覆盖率、成长占比都读那一列（temporal_task_meta.default_attribution），与时间统计页 / 贡献图 / 今日三条线 / 周复盘读的是同一列。"
    />

    <el-card class="block" shadow="never">
      <template #header><span class="card-title">这页的数字怎么来的</span></template>
      <ol class="rules">
        <li>
          每条时间记录的归因 = 该任务名在映射表里设的 <b>L1 归因</b>；
          <b>全部记录都会计入</b>六类，不会因为「没配过」而被丢掉。
        </li>
        <li>
          没设默认归因的任务名 → 兜底「成长」（<code>DEFAULT_FALLBACK_ATTR</code>），
          仪表盘会单独提示「其中 N 小时是兜底」，好让你知道哪几条还没归好。
        </li>
        <li>
          覆盖率 = 已记录小时 ÷ 理论小时（每天 12h 可支配）。
          记录里包含睡眠，所以<b>可能超过 100%</b> —— 那不是 bug，是「记的比可支配的多」。
        </li>
      </ol>
      <div class="chip-row">
        <span class="chip-cap">六类词表（真源 temporal/constants.py）</span>
        <span
          v-for="(v, k) in ATTRIBUTION_META" :key="k"
          class="chip" :style="{ color: v.color, background: v.bg }"
        >{{ k }}</span>
      </div>
      <el-button type="primary" plain size="small" @click="goMapping">
        去「分类映射编辑器」改归因
      </el-button>
    </el-card>

    <el-card class="block" shadow="never">
      <template #header><span class="card-title">原来的「归因规则」去哪了（v3.64.16 退役）</span></template>
      <div class="retired">
        <p>
          此前这里有第二个入口：按「任务名 / 活动类型(L2) / 任务类型」写规则，带优先级，覆盖默认归因。
          而映射表改 L1 时也会<b class="plain">顺带</b>往这张表写一条 priority=100 的规则 —— 它其实是同一件事的副本。
        </p>
        <p>
          问题不在重复，在<b>漏数</b>：规则只覆盖被改过的那几个任务名，而本页当时拿「命中规则」
          当统计口径，未覆盖的记录<b>静默不计</b>。实测 2 天窗口 33.96h 只算了 20h，
          「成长」1.99h（真实 12.39h）、「谋生」恒为 0，覆盖率还显示 83%。
        </p>
        <p>
          所以两套合并成一套：改归因请到映射表；本页只读。
          停用/删除旧规则表的事在数据库侧完成（迁移 <code>redemption 0009</code>）。
        </p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ATTRIBUTION_META } from '../types/redemptionTypes'

const router = useRouter()

/** 归因的唯一入口在 temporal 的映射编辑器（回程由它自己的「返回任务清单」负责） */
function goMapping() {
  router.push('/temporal/mapping')
}
</script>

<style scoped>
.attr-note { display: flex; flex-direction: column; gap: 14px; }
.block { border-radius: 10px; }
.card-title { font-weight: 600; }
.rules { margin: 0; padding-left: 20px; font-size: 13px; line-height: 1.9; color: var(--el-text-color-regular); }
.rules li { margin-bottom: 4px; }
.chip-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 14px 0; }
.chip-cap { font-size: 12px; color: var(--el-text-color-secondary); margin-right: 4px; }
.chip { font-size: 12px; padding: 2px 10px; border-radius: 10px; }
.retired { font-size: 13px; line-height: 1.9; color: var(--el-text-color-regular); }
.retired p { margin: 0 0 8px; }
.retired b { color: var(--el-color-danger); }
.retired b.plain { color: inherit; font-weight: 600; }
</style>
