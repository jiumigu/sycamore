<template>
  <div class="preset-manager">
    <div class="page-header">
      <h1 class="page-title">系统预设管理</h1>
      <div class="header-actions">
        <el-button :loading="loading" @click="fetchPresets">刷新</el-button>
        <el-button type="primary" plain @click="handleResetAll" :loading="resetting">
          恢复默认
        </el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      title="标签与快捷短语统一在此管理，各模块弹窗实时读取该配置"
      class="alert"
    />

    <div class="preset-grid">
      <el-card v-for="p in presets" :key="p.preset_type" class="preset-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">{{ PRESET_TYPE_LABELS[p.preset_type] || p.preset_type }}</span>
            <el-button size="small" type="primary" plain @click="openEditor(p)">编辑</el-button>
          </div>
        </template>

        <div class="values-list">
          <el-tag
            v-for="(v, i) in p.values"
            :key="`${v}-${i}`"
            size="small"
            :type="p.preset_type === 'quick_phrases' ? 'primary' : 'warning'"
            class="value-tag"
          >
            {{ v }}
          </el-tag>
          <span v-if="!p.values.length" class="empty">暂无内容</span>
        </div>
      </el-card>
    </div>

    <PresetEditor
      v-model:visible="editorVisible"
      :preset-type="editingType"
      :values="editingValues"
      @saved="fetchPresets"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPresets, savePresetByType } from '@/shared/api/coreApi'
import type { SystemPreset } from '@/shared/api/coreApi'
import PresetEditor from '../components/PresetEditor.vue'

const PRESET_TYPE_LABELS: Record<string, string> = {
  tags: '标签预设（摘录馆）',
  quick_phrases: '快捷短语（里程碑完成感悟）',
  sugar_tags: '小确幸预设标签',
  diary_tags: '日记流预设标签',
}

const DEFAULT_PRESETS: Record<string, string[]> = {
  tags: ['励志', '人生感悟', '写作', '成长', '情感', '职场', '哲思', '幽默', '治愈', '自律'],
  quick_phrases: [
    '辛苦了，这段时间不容易',
    '做得不错，继续保持',
    '比想象中难，但坚持下来了',
    '下次可以提前准备',
    '这件事让我学到了...',
    '完成了！下一个目标是什么？',
  ],
  sugar_tags: ['美食', '旅行', '人际关系', '学习成长', '工作成就', '自然', '音乐', '阅读', '运动', '意外惊喜'],
  diary_tags: [
    '美食', '旅行', '人际关系', '学习成长', '工作成就',
    '自然', '音乐', '阅读', '运动', '意外惊喜', '日常', '思考', '复盘',
  ],
}

const presets = ref<SystemPreset[]>([])
const loading = ref(false)
const resetting = ref(false)

const editorVisible = ref(false)
const editingType = ref('')
const editingValues = ref<string[]>([])

async function fetchPresets() {
  loading.value = true
  try {
    const res = await getPresets()
    presets.value = res.data.results || []
  } catch {
    ElMessage.error('加载预设失败')
  } finally {
    loading.value = false
  }
}

function openEditor(p: SystemPreset) {
  editingType.value = p.preset_type
  editingValues.value = [...p.values]
  editorVisible.value = true
}

async function handleResetAll() {
  try {
    await ElMessageBox.confirm('将清空并恢复为默认预设，确认继续？', '恢复默认', {
      confirmButtonText: '恢复',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  resetting.value = true
  try {
    for (const [type, values] of Object.entries(DEFAULT_PRESETS)) {
      await savePresetByType({ preset_type: type, values })
    }
    ElMessage.success('已恢复默认')
    await fetchPresets()
  } catch {
    ElMessage.error('恢复失败')
  } finally {
    resetting.value = false
  }
}

onMounted(fetchPresets)
</script>

<style scoped lang="scss">
.preset-manager {
  padding: 24px;
  background: var(--el-bg-color-page);
  min-height: 100vh;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .page-title {
      margin: 0;
      font-size: 22px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
  }

  .alert {
    margin-bottom: 20px;
  }

  .preset-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;

    .preset-card {
      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;

        .card-title {
          font-weight: 600;
        }
      }

      .values-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;

        .empty {
          font-size: 13px;
          color: var(--el-text-color-placeholder);
        }
      }
    }
  }
}
</style>
