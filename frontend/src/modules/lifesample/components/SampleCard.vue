<template>
  <div class="sample-card" @click="handleClick">
    <div class="card-top">
      <StatusBadge :status="sample.status" />
      <RelevanceBadge :relevance="sample.relevance" />
    </div>

    <div class="card-header">
      <span class="card-icon">{{ icon }}</span>
      <span class="card-name">{{ sample.name }}</span>
      <el-tag v-if="sample.sample_type" size="small" class="type-tag" :type="typeTagType">
        {{ typeLabel }}
      </el-tag>
    </div>

    <div class="card-body">
      <div v-if="sample.summary" class="card-summary">
        {{ sample.summary }}
      </div>

      <div v-if="sample.relevance_reason" class="relevance-reason">
        💡 {{ sample.relevance_reason }}
      </div>

      <div v-if="sample.tags && sample.tags.length" class="card-tags">
        <el-tag
          v-for="tag in sample.tags.slice(0, 3)"
          :key="tag"
          size="small"
          type="info"
          class="tag"
        >
          #{{ tag }}
        </el-tag>
        <span v-if="sample.tags.length > 3" class="tag-more">+{{ sample.tags.length - 3 }}</span>
      </div>
    </div>

    <div class="card-footer">
      <span v-if="sample.obsidian_path" class="obsidian-badge">📂 {{ pathLabel }}</span>
      <span v-else class="local-badge">📝 本地记录</span>

      <el-button v-if="sample.obsidian_path" text size="small" @click.stop="openObsidian">
        打开
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { SampleTypeIcons, SampleTypeLabels } from '../types'
import type { LifeSample, SampleType } from '../types'
import { StatusBadge, RelevanceBadge } from './index'
import { sampleApi } from '../api'

const props = defineProps<{
  sample: LifeSample
}>()

const emit = defineEmits<{
  (e: 'click', sample: LifeSample): void
}>()

const icon = computed(() => SampleTypeIcons[props.sample.sample_type as SampleType] || '📄')
const typeLabel = computed(
  () => SampleTypeLabels[props.sample.sample_type as SampleType] || props.sample.sample_type,
)
const typeTagType = computed(() => {
  const map: Partial<Record<SampleType, 'warning' | 'success' | 'info' | 'primary' | 'danger'>> = {
    acquaintance: 'success',
    online: 'info',
    historical: 'warning',
    celebrity: 'primary',
    fictional: 'danger',
  }
  return map[props.sample.sample_type as SampleType] || 'info'
})

// 路径只显示文件名（仓库文件夹前缀恒定无区分度，全路径过长）
const pathLabel = computed(() => {
  const p = props.sample.obsidian_path
  if (!p) return ''
  const seg = p.split('/').filter(Boolean)
  return seg[seg.length - 1] || p
})

const handleClick = () => {
  emit('click', props.sample)
}

const openObsidian = async () => {
  if (!props.sample.obsidian_path) {
    ElMessage.warning('未关联 Obsidian 文件')
    return
  }
  try {
    const res = await sampleApi.openObsidianFile(props.sample.obsidian_path)
    if (!res.data.uri) {
      ElMessage.warning('Obsidian 集成未配置，请在系统设置中启用')
      return
    }
    window.open(res.data.uri, '_blank')
  } catch {
    ElMessage.error('打开失败，请确保 Obsidian 已安装')
  }
}
</script>

<style scoped>
.sample-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 8px;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  }
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-icon {
  font-size: 20px;
}

.card-name {
  font-size: 16px;
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.type-tag {
  flex-shrink: 0;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-summary {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.relevance-reason {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  padding: 4px 8px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  line-height: 1.4;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;

  .tag {
    font-size: 11px;
  }

  .tag-more {
    font-size: 11px;
    color: var(--el-text-color-secondary);
  }
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-light);
  font-size: 12px;
  color: var(--el-text-color-secondary);

  .obsidian-badge {
    color: #409eff;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .local-badge {
    color: var(--el-text-color-secondary);
  }
}
</style>
