<!--
  必需品缺口对账 —— 弹窗外壳（v3.59.9）

  这一块回答的是**第二把尺子**上的问题：不是「够撑多久」，而是「漏了什么」。

  它原先嵌在总览正文里（四卡之下、类别明细之上，v3.59.7），于是每次看
  「还能撑多久」都要先路过一张二十来行的表 —— 而这两件事本来就不在
  同一个问题上。现在它是页头右侧的一个入口，点开才是这份对账。

  ⚠️ 搬进弹窗的代价，必须记下来：
     `unclosed_core`（核心项还没闭合）跟着一起被藏进了弹窗，
     而它是「这份结论能不能用」的**唯一提示** —— 未录入的牙膏不进天数计算
     （那会把「还没录」说成「只够撑 0 天」，而 0 是「真的撑不了」的结论）。
     所以入口按钮**必须**带角标把这个数留在页头，见 `SurvivalView.essentialEntry`。
     一个「只在弹窗里可见」的可信度信号，等于没有信号。

  ⚠️ 内容不在这里：展示与上色全在 `SurvivalEssentialPanel`（含它自己的
     新增 / 编辑弹窗与口径气泡）。本组件只管「壳」——宽度、遮罩不误关、取数时机。
-->
<template>
  <el-dialog
    v-model="visible"
    title="必需品缺口对账"
    width="min(1000px, 94vw)"
    top="6vh"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <SurvivalEssentialPanel embedded />
  </el-dialog>
</template>

<script setup lang="ts">
import SurvivalEssentialPanel from './SurvivalEssentialPanel.vue'

/**
 * 🔴 `destroy-on-close` 不是随手加的开关：
 *
 *   明细由面板自己取（`onMounted` → `store.fetchEssentials()`），而汇总走的是
 *   分析里的那一份（`analysis.essentials`，每次 `refreshAll` 都会更新）。
 *   销毁重建 ⇒ **每次打开都重新拉一次**，关闭期间在别处改过的关联/基准项
 *   不会以旧快照的形式显示出来。
 *
 *   去掉它就会变成：只有第一次打开时取数，之后再打开看到的都是那份旧数据，
 *   而界面上完全看不出它没刷新。
 */
const visible = defineModel<boolean>('visible', { required: true })
</script>
