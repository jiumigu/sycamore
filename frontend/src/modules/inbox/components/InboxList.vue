<template>
  <div class="inbox-list">
    <div v-if="store.loading" class="list-loading">
      <el-skeleton :rows="3" animated />
    </div>
    <div v-else-if="store.items.length === 0" class="list-empty">
      <div class="empty-icon">📭</div>
      <div class="empty-text">收件箱空空如也</div>
      <div class="empty-hint">在上方输入框中记录你想记住的事</div>
    </div>
    <div v-else class="list-items">
      <InboxItemComponent
        v-for="item in groupedItems"
        :key="item.id"
        :item="item"
        :batch-mode="batchMode"
        :selected="store.selectedIds.has(item.id)"
        @select="handleSelect(item)"
        @action="(cmd: string) => handleAction(item, cmd)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useInboxStore } from '../stores/inboxStore'
import type { InboxItem } from '../types/inboxTypes'
import InboxItemComponent from './InboxItem.vue'

const emit = defineEmits<{
  edit: [item: InboxItem]
  convert: [item: InboxItem]
  complete: [item: InboxItem]
}>()

const props = defineProps<{
  batchMode: boolean
}>()

const store = useInboxStore()

const groupedItems = computed(() => store.items)

function handleSelect(item: InboxItem) {
  if (props.batchMode) {
    const set = store.selectedIds
    if (set.has(item.id)) set.delete(item.id)
    else set.add(item.id)
  } else {
    emit('edit', item)
  }
}

function handleAction(item: InboxItem, cmd: string) {
  if (cmd === 'complete') emit('complete', item)
  else if (cmd === 'edit') emit('edit', item)
  else if (cmd === 'convert') emit('convert', item)
  else if (cmd === 'delete') store.deleteItem(item.id)
  else if (cmd === 'resume') {
    store.updateItem(item.id, { status: 'pending', hesitate_reason: '' })
  }
}
</script>

<style scoped>
.list-loading {
  padding: 20px;
}
.list-empty {
  text-align: center;
  padding: 48px;
  color: #9CA3AF;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 8px;
}
.empty-text {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 13px;
}
.list-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
