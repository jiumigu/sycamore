<!--
  口径气泡提示（v3.58.24）

  「这个数字是怎么算出来的」以前只存在于代码注释与后端常量里 ——
  使用者看见 12.8 这个数，无从判断它可不可信。现在它随接口下发，
  悬浮即见。

  🔴 本组件**不持有任何口径文案**。公式、要点、档位全部来自后端
     `constants.RATIO_BANDS`，经 /wealth/ratios/meta/ 下发。
     在这里补一句「其实是……」就等于口径有了两份，改后端时必然漏改。

  ⚠️ 触发区要 `@click.stop`：气泡常挂在可点击的卡片 / 按钮旁边，
     不拦住冒泡的话点一下 ⓘ 会顺带触发外层的展开或跳转。
-->
<template>
  <el-popover
    v-if="meta"
    placement="top"
    :width="width"
    trigger="hover"
    :show-after="120"
    popper-class="metric-tooltip__popper"
  >
    <template #reference>
      <span class="metric-tooltip__trigger" @click.stop>
        <el-icon><InfoFilled /></el-icon>
      </span>
    </template>

    <div class="metric-tooltip">
      <div class="metric-tooltip__head">
        <span class="metric-tooltip__title">{{ meta.label }}</span>
        <span v-if="meta.unit" class="metric-tooltip__unit">单位：{{ meta.unit }}</span>
      </div>

      <div class="metric-tooltip__formula">{{ meta.formula }}</div>

      <ul v-if="meta.note.length" class="metric-tooltip__note">
        <li v-for="(line, idx) in meta.note" :key="idx">{{ line }}</li>
      </ul>

      <!-- 档位分界：与卡片刻度条同源，都来自后端 bands -->
      <div v-if="bands.length" class="metric-tooltip__bands">
        <div class="metric-tooltip__bands-title">判定分界</div>
        <div
          v-for="band in bands"
          :key="band.range"
          class="metric-tooltip__band"
        >
          <span class="metric-tooltip__band-range">{{ band.range }}</span>
          <span
            class="metric-tooltip__band-dot"
            :style="{ background: levelColor(band.level) }"
          />
          <span class="metric-tooltip__band-label">{{ band.label }}</span>
        </div>
      </div>
      <div v-else class="metric-tooltip__bands metric-tooltip__bands--none">
        不设绝对判定线 —— 读趋势方向，不与阈值比较
      </div>

      <!-- 调用方可补一段「本次实际取值」，如 O / M / P / E -->
      <slot />
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import { levelColor } from '../../utils/ratioLevel'
import type { RatioMeta } from '../../types/wealthTypes'

const props = withDefaults(defineProps<{
  /** 后端下发的口径元信息；为 null 时**不渲染**（而不是渲染一个空气泡） */
  meta: RatioMeta | null | undefined
  width?: number
}>(), {
  width: 320,
})

/**
 * 区间文案：`lo ~ hi`；末档上界是 null → 显示 `≥ lo`。
 *
 * ⚠️ 与刻度条用的是同一份 bands，故两条展示路径不会给出不同的分界点。
 */
const bands = computed(() => {
  const raw = props.meta?.bands
  if (!raw) return []
  return raw.map(([lo, hi, level, label]) => ({
    level,
    label,
    range: hi === null ? `≥ ${lo}` : `${lo} ~ ${hi}`,
  }))
})
</script>

<style scoped>
.metric-tooltip__trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  color: var(--el-text-color-secondary);
  cursor: help;
  vertical-align: middle;
}
.metric-tooltip__trigger:hover {
  color: var(--el-color-primary);
}
</style>

<!-- 气泡内容渲染在 body 上，scoped 不生效，故用非 scoped 块 + 前缀类 -->
<style>
.metric-tooltip {
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-primary);
}
.metric-tooltip__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.metric-tooltip__title {
  font-size: 13px;
  font-weight: 600;
}
.metric-tooltip__unit {
  color: var(--el-text-color-secondary);
}
.metric-tooltip__formula {
  padding: 6px 8px;
  margin-bottom: 8px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--el-text-color-regular);
}
.metric-tooltip__note {
  margin: 0 0 8px;
  padding-left: 16px;
  color: var(--el-text-color-regular);
}
.metric-tooltip__note li + li {
  margin-top: 2px;
}
.metric-tooltip__bands-title {
  margin-bottom: 4px;
  color: var(--el-text-color-secondary);
}
.metric-tooltip__band {
  display: flex;
  align-items: center;
  gap: 6px;
}
.metric-tooltip__band-range {
  min-width: 74px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--el-text-color-regular);
}
.metric-tooltip__band-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
}
.metric-tooltip__band-label {
  color: var(--el-text-color-regular);
}
.metric-tooltip__bands--none {
  color: var(--el-text-color-secondary);
}
</style>
