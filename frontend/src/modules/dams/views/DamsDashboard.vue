<template>
  <div class="dams-dashboard">
    <!-- 归档提示（仅在当前仍处于归档状态时显示，重新启用后自动消失） -->
    <el-alert v-if="ready && isArchived" title="此模块已归档，随时可重新启用" type="info" show-icon :closable="false" class="archive-banner" />
    <h1 class="page-title">数字资产管理</h1>

    <!-- 注意力分区总览 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span class="section-title">注意力分区</span>
      </template>
      <AttentionMap :data="store.attentionMap" />
    </el-card>

    <!-- 文件列表 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span class="section-title">文件资源</span>
      </template>
      <FileList
        :files="store.files"
        :loading="store.loading"
        @add="openAdd"
        @edit="openEdit"
        @delete="handleDelete"
        @organize="handleOrganize"
        @filter="handleFilter"
      />
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <FileForm
      v-model:visible="formVisible"
      :file="editingFile"
      @submit="handleSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useDamsStore } from '../stores/damsStore'
import type { DamsFileResourceList } from '../types/damsTypes'
import { useMenuArchive } from '@/shared/composables/useMenuArchive'

// 归档横幅的判据唯一实现在 useMenuArchive（存档态含用户偏好，非写死的 defaultArchived）
const { ready, isArchived } = useMenuArchive('dams')
import AttentionMap from '../components/AttentionMap.vue'
import FileList from '../components/FileList.vue'
import FileForm from '../components/FileForm.vue'

const store = useDamsStore()
const formVisible = ref(false)
const editingFile = ref<Partial<DamsFileResourceList> | null>(null)

onMounted(() => {
  store.fetchFiles()
  store.fetchAttentionMap()
})

function openAdd() {
  editingFile.value = null
  formVisible.value = true
}

function openEdit(file: DamsFileResourceList) {
  editingFile.value = { ...file }
  formVisible.value = true
}

async function handleSubmit(data: Record<string, unknown>) {
  if (editingFile.value?.id) {
    await store.updateFile(editingFile.value.id, data)
    ElMessage.success('更新成功')
  } else {
    await store.createFile(data)
    ElMessage.success('新增成功')
  }
  store.fetchAttentionMap()
}

async function handleDelete(id: number) {
  await store.deleteFile(id)
  ElMessage.success('删除成功')
  store.fetchAttentionMap()
}

async function handleOrganize(id: number) {
  await store.markOrganized(id)
  ElMessage.success('已标记为已整理')
  store.fetchAttentionMap()
}

async function handleFilter(filters: Record<string, unknown>) {
  const params: Record<string, unknown> = {}
  if (filters.category) params.category = filters.category
  if (filters.organized !== undefined) params.is_organized = String(filters.organized)
  if (filters.duplicate !== undefined) params.is_duplicate = String(filters.duplicate)
  await store.fetchFiles(params)
}
</script>

<style scoped lang="scss">
.dams-dashboard {
  padding: 24px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  margin-bottom: 20px;
}

.section-card {
  margin-bottom: 20px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
}
</style>
