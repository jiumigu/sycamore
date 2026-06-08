<template>
  <div class="reader-section">
    <div class="reader-actions">
      <el-button size="small" @click="groupFormVisible = true">+ 新建群体</el-button>
      <el-button size="small" type="primary" @click="store.formVisible = true">+ 新增互动</el-button>
    </div>

    <!-- 群体卡片列表 -->
    <section class="section">
      <div class="section-title">📋 读者群体</div>
      <div v-if="store.groups.length === 0" class="empty-state">
        还没有读者群体，<el-button link type="primary" @click="groupFormVisible = true">新建一个</el-button>
      </div>
      <div v-else class="groups-grid">
        <ReaderGroupCard
          v-for="g in filteredGroups"
          :key="g.id"
          :group="g"
          :is-active="store.selectedGroupId === g.id"
          @select="handleGroupSelect"
          @delete="handleGroupDelete"
        />
      </div>
    </section>

    <!-- 认知共振点 -->
    <section class="section">
      <div class="section-title">⭐ 认知共振点</div>
      <ResonanceList :items="store.resonancePoints" />
    </section>

    <!-- 全部互动记录 -->
    <section class="section">
      <div class="section-title">📋 全部互动记录</div>
      <div class="filter-bar">
        <el-radio-group v-model="filterType" size="small" @change="handleFilterChange">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="3">高能量</el-radio-button>
          <el-radio-button value="comment">💬 留言</el-radio-button>
          <el-radio-button value="like">❤️ 点赞</el-radio-button>
          <el-radio-button value="share">🔄 转发</el-radio-button>
          <el-radio-button value="follow">➕ 关注</el-radio-button>
          <el-radio-button value="unfollow">➖ 取关</el-radio-button>
          <el-radio-button value="reward">💰 打赏</el-radio-button>
        </el-radio-group>
      </div>
      <div v-if="filteredInteractions.length === 0" class="empty-state">暂无互动记录</div>
      <div v-else class="interaction-list">
        <div v-for="item in filteredInteractions" :key="item.id" class="interaction-item">
          <div class="interaction-left">
            <span class="interaction-energy" :style="{ background: scoreBg(item.energy_score) }">
              {{ item.energy_score > 0 ? '+' : '' }}{{ item.energy_score }}
            </span>
          </div>
          <div class="interaction-body">
            <div class="interaction-header">
              <span class="interaction-reader">{{ item.reader_name }}</span>
              <span class="interaction-type">{{ item.interaction_type_display }}</span>
              <span class="interaction-date">{{ item.interaction_date || item.created_at?.slice(0, 10) }}</span>
            </div>
            <div class="interaction-content" v-if="item.content">{{ item.content }}</div>
            <div class="interaction-article" v-if="item.article_title">📄 {{ item.article_title }}</div>
            <div class="interaction-tags" v-if="item.tags">
              🏷 <span v-for="tag in splitTags(item.tags)" :key="tag" class="tag">{{ tag }}</span>
            </div>
          </div>
          <el-button size="small" link type="danger" class="interaction-delete" @click="handleInteractionDelete(item.id)">删除</el-button>
        </div>
      </div>
    </section>

    <!-- 新建群体弹窗 -->
    <el-dialog v-model="groupFormVisible" title="📦 新建读者群体" width="400px">
      <el-form ref="groupFormRef" :model="groupForm" :rules="groupRules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="groupForm.name" placeholder="如：公众号读者" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="groupForm.description" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="store.saving" @click="handleGroupCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 新增互动弹窗 -->
    <InteractionForm
      v-model:visible="store.formVisible"
      :groups="store.groups"
      :saving="store.saving"
      @submit="store.createInteraction"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import { useReaderStore } from '../stores/readerStore'
import ReaderGroupCard from './reader/ReaderGroupCard.vue'
import InteractionForm from './reader/InteractionForm.vue'
import ResonanceList from './reader/ResonanceList.vue'

const store = useReaderStore()

const filteredGroups = computed(() => store.groups.filter(g => g !== null))

const filterType = ref('')
const groupFormRef = ref<FormInstance>()

const groupForm = ref({ name: '', description: '' })

const groupRules = {
  name: [{ required: true, message: '请输入群体名称', trigger: 'blur' }],
}

const groupFormVisible = ref(store.groupFormVisible)
watch(() => store.groupFormVisible, (v) => { groupFormVisible.value = v })
watch(groupFormVisible, (v) => { store.groupFormVisible = v })

const filteredInteractions = computed(() => {
  let items = store.interactions.filter(Boolean)
  if (filterType.value === '3') {
    items = items.filter(i => i.energy_score >= 3)
  } else if (filterType.value) {
    items = items.filter(i => i.interaction_type === filterType.value)
  }
  return items
})

function handleGroupSelect(id: number) {
  store.selectedGroupId = store.selectedGroupId === id ? null : id
  store.fetchInteractions(store.selectedGroupId || undefined)
  store.fetchResonancePoints(store.selectedGroupId || undefined)
}

function handleGroupDelete(id: number) {
  store.deleteGroup(id)
}

async function handleGroupCreate() {
  const valid = await groupFormRef.value?.validate().catch(() => false)
  if (!valid) return
  await store.createGroup({ ...groupForm.value })
  groupForm.value = { name: '', description: '' }
}

function handleInteractionDelete(id: number) {
  store.deleteInteraction(id)
}

function handleFilterChange() {
  // computed handles it
}

function scoreBg(score: number) {
  if (score >= 5) return '#10B981'
  if (score >= 3) return '#34D399'
  if (score >= 1) return '#F59E0B'
  return '#6B7280'
}

const splitTags = (val: string) => val.split(/[,，、]/).map(s => s.trim()).filter(Boolean)
</script>

<style scoped>
.reader-section {
  max-width: 1000px;
}
.reader-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.section {
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #1F2937;
  margin-bottom: 14px;
}
.groups-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
}
.filter-bar {
  margin-bottom: 12px;
}
.empty-state {
  text-align: center;
  padding: 32px;
  color: #9CA3AF;
  font-size: 14px;
}
.interaction-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.interaction-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  background: #F9FAFB;
}
.interaction-left {
  flex-shrink: 0;
  padding-top: 2px;
}
.interaction-energy {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  min-width: 36px;
  text-align: center;
}
.interaction-body {
  flex: 1;
  min-width: 0;
}
.interaction-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.interaction-reader {
  font-weight: 600;
  font-size: 13px;
  color: #1F2937;
}
.interaction-type {
  font-size: 12px;
  color: #6B7280;
}
.interaction-date {
  font-size: 11px;
  color: #9CA3AF;
  margin-left: auto;
}
.interaction-content {
  font-size: 13px;
  color: #374151;
  margin-bottom: 4px;
  line-height: 1.5;
}
.interaction-article {
  font-size: 12px;
  color: #6B7280;
  margin-bottom: 4px;
}
.interaction-tags {
  font-size: 12px;
  color: #6B7280;
}
.tag {
  display: inline-block;
  padding: 0 6px;
  margin: 0 2px;
  background: #E5E7EB;
  border-radius: 4px;
  color: #374151;
  font-size: 11px;
}
.interaction-delete {
  flex-shrink: 0;
}
</style>
