<template>
  <el-popover
    placement="bottom"
    :width="500"
    trigger="click"
    :show-arrow="false"
    popper-class="global-search-popover"
  >
    <template #reference>
      <div class="search-container">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索摘录、日记、复盘..."
          class="search-input"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
          <template #suffix v-if="searchKeyword">
            <el-icon class="clear-icon" @click.stop="searchKeyword = ''">
              <Close />
            </el-icon>
          </template>
        </el-input>
      </div>
    </template>

    <div class="search-results">
      <div v-if="searchKeyword.length > 0 && searchKeyword.length < 2" class="empty-results">
        <el-icon><Search /></el-icon>
        <p>输入至少 2 个字符搜索</p>
      </div>
      <div v-else-if="searching" class="empty-results">
        <p>搜索中...</p>
      </div>
      <div v-else-if="groups.length > 0">
        <div class="search-header">共 {{ total }} 条结果</div>
        <div v-for="group in groups" :key="group.module_name" class="result-group">
          <div class="group-title">{{ group.module_name }} ({{ group.items.length }})</div>
          <div
            v-for="item in group.items"
            :key="item.id"
            class="result-item"
            @click="handleResultClick(item)"
          >
            <div class="result-title">{{ item.title }}</div>
            <div class="result-content">{{ item.content }}</div>
            <div class="result-date">{{ item.date }}</div>
          </div>
        </div>
      </div>
      <div v-else-if="searched" class="empty-results">
        <el-icon><Search /></el-icon>
        <p>未找到相关内容</p>
      </div>
      <div v-else class="empty-results">
        <el-icon><Search /></el-icon>
        <p>输入关键词搜索人生记录</p>
      </div>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Close } from '@element-plus/icons-vue'
import { globalSearch } from '@/shared/api/coreApi'

const router = useRouter()

const searchKeyword = ref('')
const groups = ref<any[]>([])
const total = ref(0)
const searching = ref(false)
const searched = ref(false)

const handleResultClick = (item: any) => {
  const routeMap: Record<string, string> = {
    quote: '/toolkit/quote-manager',
    diary: '/temporal/daily',
    sugar: '/sugar',
    treasure: '/treasure',
    review: '/toolkit/review-toolbox',
  }
  if (routeMap[item.module]) {
    router.push(routeMap[item.module])
  }
  searchKeyword.value = ''
}

let searchTimer: ReturnType<typeof setTimeout>

watch(searchKeyword, () => {
  const keyword = searchKeyword.value.trim()
  if (keyword.length > 0 && keyword.length < 2) return

  clearTimeout(searchTimer)
  if (!keyword) {
    groups.value = []
    total.value = 0
    searched.value = false
    return
  }

  searchTimer = setTimeout(async () => {
    searching.value = true
    try {
      const res: any = await globalSearch(keyword)
      groups.value = res.data.groups || []
      total.value = res.data.total || 0
      searched.value = true
    } catch {
      groups.value = []
      total.value = 0
      searched.value = true
    } finally {
      searching.value = false
    }
  }, 300)
})
</script>

<style scoped lang="scss">
.search-container {
  flex: 1;

  .search-input {
    :deep(.el-input__wrapper) {
      border-radius: 20px;
      background: var(--lm-bg-secondary);
      border: 1px solid transparent;
      transition: all 0.25s;

      &:hover {
        border-color: var(--lm-border-color);
        background: var(--lm-bg-primary);
      }

      &.is-focus {
        box-shadow: 0 0 0 1px var(--lm-primary-color);
        background: var(--lm-bg-primary);
      }
    }
  }

  .clear-icon {
    cursor: pointer;
    color: var(--lm-text-secondary);
    &:hover { color: var(--lm-text-primary); }
  }
}

.result-group {
  .group-title {
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
    color: var(--lm-text-secondary);
    background: var(--lm-bg-tertiary);
    border-bottom: 1px solid var(--lm-border-color);
  }
}

.result-item {
  padding: 10px 16px;
  cursor: pointer;
  transition: background-color 0.15s;
  border-bottom: 1px solid var(--lm-border-color);

  &:hover {
    background-color: var(--lm-bg-secondary);
  }

  &:last-child {
    border-bottom: none;
  }

  .result-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--lm-text-primary);
    margin-bottom: 2px;
  }

  .result-content {
    font-size: 13px;
    color: var(--lm-text-secondary);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 2px;
  }

  .result-date {
    font-size: 11px;
    color: var(--lm-text-tertiary);
  }
}
</style>
