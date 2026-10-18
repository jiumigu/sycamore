<!--
  说明性正文的悬停气泡锚点（v3.62.16）

  「这块说明太占位置」的标准解法。判据见 TECH-NOTES §79.1：

  | 类型 | 去哪 |
  |---|---|
  | **状态**（每次进页面都要一眼确认，如「正在跑哪个阶段」） | **留页** |
  | **说明**（读一次就够，如「这两块是配置项」） | **气泡**（本组件） |
  | **出口**（要点的按钮，如「刷新」「新增规则」） | **留页** |

  🔴 **不许把状态也收进气泡**：状态被收起来 ⇒ 用户得先知道「要看」，才会去悬停
     （＝得先知道答案才找得到答案）。**空态解释同理留页**（§79.5）——
     页面上没数据时，人不会特意去悬停一个问号找原因。

  🔴 本组件**不持有任何文案**。文案由调用方经 `title` 与默认插槽传入。
     在这里补一句「其实是……」就等于说明有了两份，改一边必然漏一边。

  ⚠️ 锚点必须自带「我能悬停」的样子（§79.3）：ⓘ 图标 + `cursor: help` + 悬停转主题色。
     只把文字压在光标下、样貌一个字不改 = 没人知道这里有东西（等于把信息删了）。

  ⚠️ 气泡宽度走 `:width`（§79.4）：`.info-tip` 外壳在本组件模板里、带 scope id，
     scoped 样式照常命中；但气泡外壳 `.el-popper` 是 EP 自己的元素、**没有 scope id**
     ⇒ 别指望在 scoped 里写 `.el-popper { width: … }`。

  ⚠️ 插槽里**放纯文本**最稳（文本节点继承 `.info-tip` 的字体样式）。
     若要在插槽里放 `<b>` 这类元素，那些元素带的是**调用方**的 scope id，
     本组件的 scoped 样式命中不了 ⇒ 样式得由调用方自己给（或用 `:slotted()`）。

  ⚠️ 嵌在 `el-dialog` / `el-drawer` 里不会被盖住（两者都走 EP 的 zIndex 管理器、后开者更高，
     §79.8），但**不许靠眼看** —— 遮罩是半透明的，被盖住的气泡截图里看着也「差不多正常」。
     断言：`document.elementFromPoint(气泡中心).closest('.el-popper')` 必须成立。
-->
<template>
  <el-popover
    :placement="placement"
    :width="width"
    trigger="hover"
    :show-after="showAfter"
  >
    <template #reference>
      <!-- `@click.stop`：锚点常挂在标题旁或按钮附近，不拦冒泡会顺带触发外层的展开/跳转 -->
      <span class="info-tip__trigger" @click.stop>
        <el-icon><component :is="iconComp" /></el-icon>
      </span>
    </template>

    <div class="info-tip">
      <div v-if="title" class="info-tip__title">{{ title }}</div>
      <div class="info-tip__body"><slot /></div>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { InfoFilled, QuestionFilled } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  /** 气泡里的标题行（第一行，加粗）。留空则只渲染正文。 */
  title?: string
  /** 气泡宽度：**必须显式给**，别跟容器宽度联动（§79.8） */
  width?: number
  placement?: 'top' | 'top-start' | 'top-end'
    | 'bottom' | 'bottom-start' | 'bottom-end'
    | 'left' | 'left-start' | 'left-end'
    | 'right' | 'right-start' | 'right-end'
  /** ⓘ = 「这是什么」；? = 「这个数怎么来的」 */
  icon?: 'info' | 'question'
  showAfter?: number
}>(), {
  title: '',
  width: 420,
  placement: 'bottom-start',
  icon: 'info',
  showAfter: 120,
})

/**
 * 🔴 传**组件对象**，不传字符串。
 *
 * `<component :is="'QuestionFilled'" />` 会**静默不渲染** —— 本项目没做图标全局注册，
 * 字符串解析不到任何组件，页面上就是「锚点没了图标」，而且不报错、不警告。
 */
const iconComp = computed(() => (props.icon === 'question' ? QuestionFilled : InfoFilled))
</script>

<style scoped>
.info-tip__trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: -2px;
  margin-left: 4px;
  color: var(--el-text-color-placeholder);
  cursor: help;
}
.info-tip__trigger:hover {
  color: var(--el-color-primary);
}
/* 气泡内容：`.info-tip` 在本组件模板里 ⇒ 带 scope id，scoped 样式命中（§79.4） */
.info-tip {
  font-size: 12px;
  line-height: 1.75;
  color: var(--el-text-color-regular);
}
.info-tip__title {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
</style>
