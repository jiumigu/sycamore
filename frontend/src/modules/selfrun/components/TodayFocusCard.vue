<!--
  仪表盘「今天」轻卡（v3.64.77）

  🔴 只显示三样：今天选了哪一格（或「还没定」）、那一格的前 2 件、
     一个去整页的按钮。**不显示四格选择器** ——
     定档是一个仪式，应该发生在整页里，不在仪表盘的小格子里顺手点掉；
     顺手点掉的那一下，第二天不会有任何印象。

  🔴 它**不复用** `TodayPanel`：那个页面有候选、结算条、周色带、
     换格入口，塞进仪表盘会把首屏撑成第二个今日页，两处口径各长各的。
-->
<template>
  <el-card v-if="payload" shadow="never" class="tc">
    <div class="tc-head">
      <span class="tc-title">☀️ 今天</span>
      <span class="tc-date">{{ payload.weekday }}</span>
      <el-button size="small" text type="primary" class="tc-more" @click="go">
        {{ cell ? '去今天 →' : '去定档 →' }}
      </el-button>
    </div>

    <!-- 未定档：一句状态 + 四格的名字（名字只在这里出现一次，不做成按钮） -->
    <div v-if="!cell" class="tc-body">
      <span class="tc-empty">还没定今天走哪一格</span>
      <span class="tc-hint">
        {{ payload.quadrants.map((q) => q.label).join(' / ') }} —— 选一格，今天只看它
      </span>
    </div>

    <!-- 已定档：格名 + 前 2 件 -->
    <div v-else class="tc-body">
      <div class="tc-quad">
        <span class="tc-dot" :style="{ background: activeColor }"></span>
        <span class="tc-quad-label">{{ cell.quadrant_label }}</span>
        <span v-if="cell.quadrant === 'rest'" class="tc-hint">今天不排活</span>
      </div>
      <ul v-if="top.length" class="tc-list">
        <li v-for="c in top" :key="`${c.kind}-${c.id}`">
          <!-- 副标题由后端给（「哪个目标下的第几个里程碑」）—— 前端不拼，
               也不另存一份「书 / 里程碑 / 收件箱 / 作品」的对照表 -->
          <span class="tc-name">{{ c.title }}</span>
          <span v-if="c.subtitle" class="tc-sub">{{ c.subtitle }}</span>
        </li>
      </ul>
      <span v-else-if="cell.quadrant !== 'rest'" class="tc-hint">
        这一格今天没有排着的活
      </span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getToday } from '../api/selfrunApi'
import type { TodayPayload } from '../types/selfrunTypes'

/** 仪表盘只露前 2 件 —— 第 3 件留给整页。看三件就该动手了，不是接着往下看。 */
const DASH_LIMIT = 2

const router = useRouter()
const payload = ref<TodayPayload | null>(null)

const cell = computed(() => payload.value?.cell ?? null)
const top = computed(() => (cell.value?.candidates ?? []).slice(0, DASH_LIMIT))
const activeColor = computed(
  () => payload.value?.quadrants.find((q) => q.quadrant === cell.value?.quadrant)?.color ?? '#4A4A4A',
)

async function load() {
  try {
    payload.value = (await getToday()).data
  } catch {
    // 取不到就整张卡不渲染：仪表盘上摆一张「今天：—」的空卡，
    // 每天看到的第一件事就是「系统坏了」，而它并不是这一屏的重点。
    payload.value = null
  }
}

function go() {
  router.push('/selfrun/today')
}

onMounted(load)
</script>

<style scoped>
.tc { margin-bottom: 16px; }
.tc-head { display: flex; align-items: baseline; gap: 10px; }
.tc-title { font-size: 15px; font-weight: 600; }
.tc-date { font-size: 12px; color: var(--el-text-color-secondary); }
.tc-more { margin-left: auto; }
.tc-body { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.tc-empty { font-size: 14px; color: var(--el-text-color-regular); }
.tc-hint { font-size: 12px; color: var(--el-text-color-secondary); }
.tc-quad { display: flex; align-items: center; gap: 8px; }
.tc-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.tc-quad-label { font-size: 14px; font-weight: 600; }
.tc-list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 4px; }
.tc-list li { display: flex; align-items: baseline; gap: 8px; font-size: 13px; min-width: 0; }
.tc-name {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 60%;
}
.tc-sub {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 12px; color: var(--el-text-color-secondary);
}
</style>
