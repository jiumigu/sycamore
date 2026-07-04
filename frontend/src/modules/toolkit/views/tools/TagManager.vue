<template>
  <div class="tag-manager">
    <h2 class="page-title">🏷️ 标签管理器</h2>
    <p class="subtitle">统一管理所有模块的标签，合并重复，保持知识体系整洁。</p>

    <!-- 标签云 -->
    <el-card class="tag-cloud-card" shadow="never">
      <template #header>📊 标签云（{{ tags.length }} 个标签）</template>
      <div v-if="tags.length > 0" class="tag-cloud">
        <span
          v-for="tag in tags"
          :key="tag.name"
          class="tag-item"
          :style="{ fontSize: getTagSize(tag.count) + 'px' }"
          @click="handleTagClick(tag)"
        >
          {{ tag.name }}<sup>{{ tag.count }}</sup>
        </span>
      </div>
      <el-empty v-else description="暂无标签" />
    </el-card>

    <!-- 标签列表 -->
    <el-card class="tag-list-card" shadow="never">
      <template #header>📋 标签列表</template>
      <el-table :data="tags" style="width:100%" v-loading="loading">
        <el-table-column prop="name" label="标签" min-width="150" />
        <el-table-column prop="count" label="使用次数" width="100" sortable />
        <el-table-column label="来源模块" min-width="180">
          <template #default="{ row }">
            <el-tag
              v-for="m in row.modules"
              :key="m"
              size="small"
              type="info"
              style="margin-right:4px"
            >
              {{ m }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openRename(row)">重命名</el-button>
            <el-button size="small" @click="openMerge(row)">合并</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 重命名弹窗 -->
    <el-dialog v-model="showRenameDialog" title="重命名标签" width="400px">
      <el-form>
        <el-form-item label="原标签">
          <el-tag size="large" closable @close="showRenameDialog = false">{{ editingTag?.name }}</el-tag>
        </el-form-item>
        <el-form-item label="新名称">
          <el-input v-model="newTagName" placeholder="输入新的标签名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="handleRename">确认重命名</el-button>
      </template>
    </el-dialog>

    <!-- 合并弹窗 -->
    <el-dialog v-model="showMergeDialog" title="合并标签" width="400px">
      <el-form>
        <el-form-item label="原标签">
          <el-tag size="large" type="warning" closable @close="showMergeDialog = false">{{ editingTag?.name }}</el-tag>
        </el-form-item>
        <el-form-item label="合并到">
          <el-select v-model="mergeTarget" filterable placeholder="选择目标标签" style="width:100%">
            <el-option
              v-for="t in otherTags"
              :key="t.name"
              :label="`${t.name} (${t.count})`"
              :value="t.name"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMergeDialog = false">取消</el-button>
        <el-button type="warning" @click="handleMerge">确认合并</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTags, mergeTag } from '@/modules/toolkit/api/toolkitApi'
import { globalSearch } from '@/shared/api/coreApi'

const loading = ref(false)
const tags = ref<{ name: string; count: number }[]>([])
const editingTag = ref<{ name: string; count: number } | null>(null)
const newTagName = ref('')
const mergeTarget = ref('')
const showRenameDialog = ref(false)
const showMergeDialog = ref(false)

const otherTags = computed(() =>
  tags.value.filter(t => t.name !== editingTag.value?.name)
)

const getTagSize = (count: number) => {
  const max = Math.max(...tags.value.map(t => t.count), 1)
  const ratio = count / max
  return Math.round(12 + ratio * 24)
}

const fetchTags = async () => {
  loading.value = true
  try {
    const res = await getTags()
    tags.value = res.data.tags || []
  } catch {
    ElMessage.error('获取标签失败')
  } finally {
    loading.value = false
  }
}

const openRename = (tag: { name: string; count: number }) => {
  editingTag.value = tag
  newTagName.value = ''
  showRenameDialog.value = true
}

const handleRename = async () => {
  if (!newTagName.value.trim()) {
    ElMessage.warning('请输入新标签名称')
    return
  }
  try {
    await mergeTag({
      action: 'rename',
      old_tag: editingTag.value!.name,
      new_tag: newTagName.value.trim(),
    })
    showRenameDialog.value = false
    ElMessage.success('重命名成功')
    await fetchTags()
  } catch {
    ElMessage.error('重命名失败')
  }
}

const openMerge = (tag: { name: string; count: number }) => {
  editingTag.value = tag
  mergeTarget.value = ''
  showMergeDialog.value = true
}

const handleMerge = async () => {
  if (!mergeTarget.value) {
    ElMessage.warning('请选择目标标签')
    return
  }
  try {
    const res = await mergeTag({
      action: 'merge',
      old_tag: editingTag.value!.name,
      new_tag: mergeTarget.value,
    })
    showMergeDialog.value = false
    ElMessage.success(`合并成功，影响 ${res.data.affected} 条记录`)
    await fetchTags()
  } catch {
    ElMessage.error('合并失败')
  }
}

const handleTagClick = async (tag: { name: string; count: number }) => {
  try {
    const res = await globalSearch(tag.name)
    const items = res.data.groups?.flatMap((g: any) => g.items) || []
    const total = res.data.total || 0
    ElMessage.info(`标签「${tag.name}」匹配 ${total} 条记录`)
  } catch {
    ElMessage.error('搜索失败')
  }
}

onMounted(fetchTags)
</script>

<style scoped lang="scss">
.tag-manager {
  padding: 24px;
  max-width: 960px;
  margin: 0 auto;

  .page-title {
    font-size: 22px;
    font-weight: 600;
    margin: 0 0 8px;
    color: var(--lm-text-primary);
  }

  .subtitle {
    font-size: 14px;
    color: var(--lm-text-secondary);
    margin: 0 0 24px;
  }
}

.tag-cloud-card {
  margin-bottom: 24px;

  .tag-cloud {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    padding: 8px 0;
    min-height: 80px;

    .tag-item {
      cursor: pointer;
      color: var(--lm-primary-color);
      transition: color 0.2s;
      line-height: 1.4;

      &:hover {
        color: var(--lm-primary-hover);
        text-decoration: underline;
      }

      sup {
        color: var(--lm-text-tertiary);
        font-size: 0.7em;
        margin-left: 1px;
      }
    }
  }
}

.tag-list-card {
  :deep(.el-table) {
    th.el-table__cell {
      background-color: var(--lm-bg-secondary);
    }
  }
}
</style>
