<template>
  <el-card
    class="treasure-card"
    :class="{
      'is-bad': thing.record_type === '歹',
      unavailable: thing.record_type === '好' && !thing.still_available,
    }"
    shadow="hover"
    @click="$emit('click-card', thing)"
  >
    <div class="card-body">
      <div class="card-header">
        <span class="card-type-badge" :class="thing.record_type === '歹' ? 'badge-bad' : 'badge-good'">
          {{ thing.record_type_display || (thing.record_type === '歹' ? '👎 歹物' : '👍 好物') }}
        </span>
        <span class="card-category">{{ categoryText }}</span>
      </div>

      <h3 class="card-name">{{ maskText(thing.name) }}</h3>

      <!-- 好物 -->
      <template v-if="thing.record_type === '好'">
        <p class="card-content">{{ maskFreeText(thing.why_good) }}</p>
        <div class="card-meta">
          <span v-if="thing.where_to_find" class="meta-location">📍 {{ maskText(thing.where_to_find) }}</span>
          <span v-if="thing.scene" class="meta-scene">{{ maskText(thing.scene) }}</span>
          <!--
            ⚠️ 只在「不能」时显示。
            存量 19/19 全是「能」，于是每张卡片都挂着「✅ 还能找到」——
            那是**默认态噪声**：「不能」才是信息，也是唯一需要行动的那一种。
            留空的那 17 条「在哪能找到」同理：方法型根本没有「在哪」可填。
          -->
          <el-tag v-if="!thing.still_available" size="small" type="danger">❌ 已找不到</el-tag>
        </div>
      </template>

      <!-- 歹物 -->
      <template v-else>
        <div class="bad-section">
          <div class="bad-field">
            <span class="bad-label">💥 踩坑：</span>
            <span class="card-content">{{ maskFreeText(thing.avoid_reason) }}</span>
          </div>
          <div v-if="thing.consequence" class="bad-field">
            <span class="bad-label">😵 后果：</span>
            <span>{{ maskFreeText(thing.consequence) }}</span>
          </div>
          <div v-if="thing.scene" class="bad-field">
            <span class="bad-label">📍 场景：</span>
            <span>{{ maskText(thing.scene) }}</span>
          </div>
        </div>
        <div class="card-meta">
          <el-tag size="small" type="warning">⚠️ 避免再犯</el-tag>
        </div>
      </template>

      <!--
        ⭐ 待补理由的**可见出口**（v3.60.32 入口 4）。
        理由允许留空的前提，是「留空」这件事本身看得见、能回头补 ——
        否则「允许留空」会退化成「永远空着」（这正是用户抱怨的「很多信息都是空的」）。
        ⚠️ 判据 `has_reason` 由**后端**算（好物看 why_good、歹物看 avoid_reason），
           前端不自己判空 —— 那是第二份口径，改的时候必然漏一份。
      -->
      <div
        v-if="!thing.has_reason"
        class="card-pending"
        @click.stop="$emit('fill-reason', thing)"
      >
        📝 还没写理由 · 去补
      </div>

      <!-- 🔗 关联实物（入口 5）：回头看一条评价时，它的事实就在旁边 -->
      <div v-if="thing.linked_name" class="card-link">
        🔗 {{ thing.linked_kind === 'property' ? '物件资产' : '物品清单' }} ·
        {{ maskText(thing.linked_name) }}
      </div>

      <!-- 标签 -->
      <div v-if="thing.tags" class="card-tags">
        <el-tag v-for="tag in displayTags" :key="tag" size="small" type="info">
          {{ tag }}
        </el-tag>
      </div>
    </div>

    <!-- 操作行（阻止冒泡）—— 左侧「值得留」，右侧编辑 / 删除 -->
    <div class="card-actions" @click.stop>
      <!--
        ⭐ 「值得留」（v3.62.12，第七个入口）。
        ⚠️ `keepReady === false`（作品库读不到）时**整个不渲染** ——
           读不到 ≠ 没勾过，画成「值得留」是在说谎（见 useWorkKeep 文件头）。
        ⚠️ 与其余六个入口一样摆在**列表行内**，不藏进详情弹窗；
           本页两处（卡片 / 详情）用的是**同一个** `useWorkKeep` 实例，
           所以两边状态永远一致（各调一次 `useWorkKeep` 就会各持一份 rows）。
      -->
      <KeepMark
        v-if="keepReady"
        class="card-keep"
        :state="keepState"
        :work-name="keepWorkName"
        :busy="keepBusy"
        @toggle="$emit('toggle-keep', thing)"
      />
      <el-button text size="small" @click="$emit('edit', thing)">
        <el-icon><Edit /></el-icon> 编辑
      </el-button>
      <el-button text size="small" type="danger" @click="$emit('delete', thing)">
        <el-icon><Delete /></el-icon>
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Edit, Delete } from '@element-plus/icons-vue'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import { MASK_TEXT } from '@/shared/utils/privacy'
import KeepMark from '@/modules/works/components/KeepMark.vue'
import type { KeepState } from '@/modules/works/types/workTypes'
import { SUBJECT_KIND_METHOD } from '../types/treasureTypes'
import type { GoodThing } from '../types/treasureTypes'

/**
 * ⚠️ 「值得留」的**状态由父组件传进来**，本组件不自己调 `useWorkKeep` ——
 *    每调一次就多一份独立的 `rows`，卡片与详情弹窗会各说各话。
 */
const props = withDefaults(defineProps<{
  thing: GoodThing
  /** 作品库是否读到了（假 ⇒ 整个标记不渲染，因为「读不到」不能说成「没勾过」） */
  keepReady?: boolean
  keepState?: KeepState
  keepWorkName?: string | null
  keepBusy?: boolean
}>(), {
  keepReady: false,
  keepState: 'none',
  keepWorkName: null,
  keepBusy: false,
})

const { isActive, maskText, maskFreeText } = usePrivacyMask()
const displayTags = computed(() => (isActive.value ? [MASK_TEXT] : getTags(props.thing.tags)))

/**
 * 卡片右上角那一格写什么。
 *
 * ⚠️ 方法型**没有类别**（类别是「这东西干嘛用的」，方法不是实物）——
 *    直接渲染 `category_display` 会得到一个**空白格**，看起来像这条记录
 *    缺了数据。这里改成显示「💡 方法 · 生活」。
 */
const categoryText = computed(() => {
  if (props.thing.subject_kind === SUBJECT_KIND_METHOD) {
    return props.thing.method_group
      ? `💡 方法 · ${props.thing.method_group}`
      : '💡 方法'
  }
  return props.thing.category_display || props.thing.category
})

defineEmits<{
  edit: [thing: GoodThing]
  delete: [thing: GoodThing]
  'click-card': [thing: GoodThing]
  /** ⭐ 「去补理由」—— 打开编辑弹窗并停在理由那一格 */
  'fill-reason': [thing: GoodThing]
  /** ⭐ 「值得留」打勾 / 取消（三态状态机在父组件的 `useWorkKeep` 实例里） */
  'toggle-keep': [thing: GoodThing]
}>()

function getTags(tags: string) {
  return tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : []
}
</script>

<style scoped lang="scss">
.treasure-card {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: transform 0.2s, box-shadow 0.2s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  }

  &.unavailable {
    opacity: 0.65;
  }

  &.is-bad {
    :deep(.el-card__body) { border-color: #ffd8bf; background: #fffaf5; }
  }

  :deep(.el-card__body) {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 16px;
    border-radius: 10px;
    border: 1px solid #f0f0f0;
  }
}

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.card-category { font-size: 13px; color: #666; }

.card-type-badge {
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 4px;
  &.badge-good { background: #e6f7e6; color: #389e0d; }
  &.badge-bad { background: #fff1f0; color: #cf1322; }
}

.card-name { margin: 0 0 6px; font-size: 16px; font-weight: 600; }

.card-content {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.5;
  margin: 0 0 10px;
  font-size: 14px;
  color: #444;
}

.bad-section {
  margin-bottom: 10px;
  .bad-field {
    font-size: 14px;
    line-height: 1.6;
    margin-bottom: 4px;
    .bad-label { font-weight: 500; color: #cf1322; }
  }
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

/* ⭐ 待补理由 —— 是「缺一块」而不是错误，所以用中性偏提示的样式，不用红色 */
.card-pending {
  font-size: 12px;
  color: var(--el-color-warning);
  cursor: pointer;
  margin-bottom: 6px;

  &:hover { text-decoration: underline; }
}

/* 🔗 关联实物 —— 纯事实行，不抢视觉 */
.card-link {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  border-top: 1px solid #f0f0f0;
  padding-top: 8px;
  margin-top: 8px;
  flex-shrink: 0;
}

/* ⚠️ 「值得留」顶到最左，编辑 / 删除留在右侧 —— `margin-right: auto` 比
   插一个 spacer 元素干净。`class` 会透传到 KeepMark 的根元素上，
   本组件的 scope id 也打在同一元素上，所以这里直接写就能命中。 */
.card-keep { margin-right: auto; }
</style>
