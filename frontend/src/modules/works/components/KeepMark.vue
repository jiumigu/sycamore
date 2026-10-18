<template>
  <!-- ⚠️ `el-popover` 而不是 `el-tooltip`：两者插槽语义**是反的** ——
       tooltip 的默认插槽是「触发元素」、正文要走 `#content`；
       popover 才是「`#reference` 触发 + 默认插槽正文」。
       写错不报错，只是正文被当成触发内容**内联渲染、常驻可见**。 -->
  <el-popover placement="top" :width="330" trigger="hover" :show-after="150">
    <template #reference>
      <!-- ⚠️ 用原生 `<span>` 而不是 `el-button`：
           `el-button` 声明了 `emits: ['click']`，`@click.stop` 的修饰符
           在「自定义事件 + `$attrs` 透传到根元素」这两条路径下**可能各触发一次**
           —— 表现正好是「点一下、勾上又取消」（像没反应），而且不报错。
           原生元素上的 `.stop` 只有一条路径，不会歧义。
           它还要出现在表格行里（行本身有 `@row-click`），必须拦得住冒泡。 -->
      <span
        class="keep-mark"
        :class="[`is-${state}`, { 'is-busy': busy }]"
        role="button"
        :tabindex="busy ? -1 : 0"
        @click.stop="emit('toggle')"
        @keydown.enter.stop.prevent="emit('toggle')"
        @keydown.space.stop.prevent="emit('toggle')"
      >
        <el-icon v-if="busy" class="keep-spin"><Loading /></el-icon>
        <el-icon v-else><Collection /></el-icon>
        <span>{{ TEXT[state] }}</span>
      </span>
    </template>

    <div class="keep-tip">
      <template v-if="state === 'none'">
        <p>把它标成<b>「值得留」</b> —— 不用现在写任何东西。</p>
        <p>
          哪天你顺手了，在<b>「本周状态」页末</b>把它收成一件东西
          （一份清单、一个方法、一段记录都算）。
        </p>
      </template>

      <template v-else-if="state === 'pending'">
        <p>已标成<b>「待提炼」</b>，还什么都没写 —— 这是对的。</p>
        <p>去<b>「本周状态」页末</b>把它收成一件东西。</p>
        <p>再点一下 = <b>取消</b>这个标记。</p>
      </template>

      <template v-else>
        <p>已经收进《{{ workName || '某件作品' }}》了。</p>
        <p>
          要拆开请去<b>「作品」页</b>处理 —— 在这里点<b>不会</b>把它从作品里拿掉，
          免得作品凭空少一个来源。
        </p>
      </template>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { Collection, Loading } from '@element-plus/icons-vue'

import type { KeepState } from '../types/workTypes'

withDefaults(defineProps<{
  state: KeepState
  /** 已收进作品时，那件作品叫什么（气泡里要能说出名字） */
  workName?: string | null
  busy?: boolean
}>(), { workName: null, busy: false })

const emit = defineEmits<{ toggle: [] }>()

const TEXT: Record<KeepState, string> = {
  none: '值得留',
  pending: '待提炼',
  used: '已留下',
}
</script>

<style scoped>
/* ⚠️ 这一份样式**在 teleport 之后仍然命中**（`.keep-tip` 是组件模板的一部分，
   即使它被搬到 body 下）；但 `.el-popper` 外壳不命中 —— 所以宽度走 `:width`。 */
.keep-mark {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  font-size: 12px;
  line-height: 1.4;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  outline: none;
}
.keep-mark.is-none { color: var(--el-text-color-secondary); }
.keep-mark.is-none:hover,
.keep-mark.is-none:focus-visible {
  color: var(--el-color-primary);
}
.keep-mark.is-pending {
  color: var(--el-color-primary);
  font-weight: 600;
}
.keep-mark.is-used {
  color: var(--el-color-success);
  font-weight: 600;
}
/* 悬停 / 键盘聚焦都要有「能点的样子」（三种态都试出来） */
.keep-mark:hover,
.keep-mark:focus-visible {
  text-decoration: underline dashed;
  text-underline-offset: 3px;
}
.keep-mark.is-busy { cursor: default; text-decoration: none; }

.keep-spin { animation: keep-spin 0.9s linear infinite; }
@keyframes keep-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.keep-tip { font-size: 12px; line-height: 1.8; }
.keep-tip p { margin: 0 0 6px; }
.keep-tip p:last-child { margin-bottom: 0; }
</style>
