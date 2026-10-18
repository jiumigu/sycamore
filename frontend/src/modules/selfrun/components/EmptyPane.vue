<!-- 自我运转 · 单个子页的「还没有内容」说明
     ────────────────────────────────────────────────────────────
     为什么要有这个组件：**没有进行中的阶段时，六个子页不能长得一模一样**。
     一旦一样，从侧边栏点「本周状态 / 本月状态 / 历史复盘」就等于点了同一个链接，
     用户只能得出「菜单坏了」——而页面其实没错，是**没说清自己在哪一页**。

     所以每一页都自己回答两件事：
       ① 这一页为什么是空的（说具体：本周是哪一周 / 这一页要等什么才有内容）；
       ② 要怎么做它才有内容（出口：去「制定配置」）。
     文案由调用方给（每页不同），出口按钮与版式由这里统一 —— 出口只有一条路。
-->
<template>
  <div class="empty-pane">
    <el-alert type="info" :closable="false" show-icon :title="title" :description="desc" />
    <div class="ep-cta">
      <el-button type="primary" @click="goSetup">去「制定配置」</el-button>
      <span class="ep-hint">阶段 → 选 KPI → 配目标与底线 → 生效，四步；开通后这一页自动有内容</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

defineProps<{
  /** 这一页为什么是空的 —— 要带上「本周是哪一周」这类**本页专属**的事实 */
  title: string
  desc: string
}>()

const router = useRouter()

/** 出口走**路由名**而不是路径字面量 —— 路径改了这里不用跟着改 */
function goSetup() {
  router.push({ name: 'selfrun-setup' })
}
</script>

<style scoped>
.empty-pane { display: flex; flex-direction: column; gap: 12px; }
.ep-cta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ep-hint { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
