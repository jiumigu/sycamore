<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'
import { useShowroomStore } from '../stores/showroomStore'
import type { ShowroomCase, ShowroomSkill, ShowroomWork } from '../types/showroomTypes'
import CaseForm from '../components/CaseForm.vue'
import SkillForm from '../components/SkillForm.vue'
import WorkForm from '../components/WorkForm.vue'

const store = useShowroomStore()
const router = useRouter()
const activeTab = ref('profile')

const profileForm = reactive({
  ip_name: '',
  tagline: '',
  positioning: '',
  bio: '',
  email: '',
  wechat: '',
  other_contact: '',
})

const caseDialog = ref(false)
const editingCase = ref<ShowroomCase | null>(null)
const skillDialog = ref(false)
const editingSkill = ref<ShowroomSkill | null>(null)
const workDialog = ref(false)
const editingWork = ref<ShowroomWork | null>(null)

onMounted(async () => {
  await Promise.all([
    store.fetchProfile(),
    store.fetchMeta(),
    store.fetchCases(),
    store.fetchSkills(),
    store.fetchWorks(),
  ])
  const p = store.profile
  if (p) {
    profileForm.ip_name = p.ip_name
    profileForm.tagline = p.tagline
    profileForm.positioning = p.positioning
    profileForm.bio = p.bio
    profileForm.email = p.email
    profileForm.wechat = p.wechat
    profileForm.other_contact = p.other_contact
  }
})

async function saveProfile() {
  await store.saveProfile({ ...profileForm })
  ElMessage.success('品牌信息已保存')
}

// ── 案例 ──
function openCase(c: ShowroomCase | null = null) {
  editingCase.value = c
  caseDialog.value = true
}

async function saveCase(payload: Record<string, unknown>) {
  if (editingCase.value) {
    await store.updateCase(editingCase.value.id, payload)
  } else {
    await store.createCase(payload)
  }
  caseDialog.value = false
  await store.fetchCases()
  ElMessage.success('案例已保存')
}

async function toggleCaseVisible(c: ShowroomCase) {
  try {
    await store.updateCase(c.id, { is_visible: c.is_visible })
  } catch {
    await store.fetchCases()
  }
}

async function removeCase(c: ShowroomCase) {
  await ElMessageBox.confirm(`确定删除案例「${c.title}」？`, '删除确认', { type: 'warning' })
  await store.deleteCase(c.id)
  await store.fetchCases()
  ElMessage.success('已删除')
}

// ── 技能 ──
function openSkill(s: ShowroomSkill | null = null) {
  editingSkill.value = s
  skillDialog.value = true
}

async function saveSkill(payload: Record<string, unknown>) {
  if (editingSkill.value) {
    await store.updateSkill(editingSkill.value.id, payload)
  } else {
    await store.createSkill(payload)
  }
  skillDialog.value = false
  await store.fetchSkills()
  ElMessage.success('技能已保存')
}

async function toggleSkillVisible(s: ShowroomSkill) {
  try {
    await store.updateSkill(s.id, { is_visible: s.is_visible })
  } catch {
    await store.fetchSkills()
  }
}

async function removeSkill(s: ShowroomSkill) {
  await ElMessageBox.confirm(`确定删除技能「${s.name}」？`, '删除确认', { type: 'warning' })
  await store.deleteSkill(s.id)
  await store.fetchSkills()
  ElMessage.success('已删除')
}

// ── 作品馆 ──
function openWork(w: ShowroomWork | null = null) {
  editingWork.value = w
  workDialog.value = true
}

async function saveWork(payload: Record<string, unknown>) {
  if (editingWork.value) {
    await store.updateWork(editingWork.value.id, payload)
  } else {
    await store.createWork(payload)
  }
  workDialog.value = false
  await store.fetchWorks()
  ElMessage.success('馆藏已保存')
}

async function toggleWorkVisible(w: ShowroomWork) {
  try {
    await store.updateWork(w.id, { is_visible: w.is_visible })
  } catch {
    await store.fetchWorks()
  }
}

async function removeWork(w: ShowroomWork) {
  const name = w.work_name ?? w.title_snapshot
  await ElMessageBox.confirm(`确定把「${name}」移出馆？`, '移出确认', { type: 'warning' })
  await store.deleteWork(w.id)
  await store.fetchWorks()
  ElMessage.success('已移出')
}

function levelLabel(level: string) {
  return store.meta?.skill_levels.find(o => o.value === level)?.label ?? level
}
</script>

<template>
  <div class="showroom-edit">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">策展编辑</h1>
        <el-tag type="warning" class="module-tag">展厅</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="router.push('/showroom/preview')">去预览</el-button>
      </div>
    </div>

    <el-alert
      class="hub-alert"
      type="info"
      :closable="false"
      show-icon
      title="策展 = 取舍。展厅的价值不在「展示了多少」，而在「选择了什么」——只放能证明能力的东西。"
    />

    <el-tabs v-model="activeTab">
      <!-- 品牌信息 -->
      <el-tab-pane label="品牌信息" name="profile">
        <el-card>
          <el-form label-width="110px" class="profile-form">
            <el-form-item label="IP 名">
              <el-input v-model="profileForm.ip_name" placeholder="如 鸠羽岁安" />
            </el-form-item>
            <el-form-item label="一句话定位">
              <el-input v-model="profileForm.tagline" placeholder="访客离开时记住的那句话" />
            </el-form-item>
            <el-form-item label="定位副标">
              <el-input v-model="profileForm.positioning" placeholder="一句话说清你是谁" />
            </el-form-item>
            <el-form-item label="自我介绍">
              <el-input v-model="profileForm.bio" type="textarea" :rows="4" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="profileForm.email" />
            </el-form-item>
            <el-form-item label="微信号">
              <el-input v-model="profileForm.wechat" />
            </el-form-item>
            <el-form-item label="其他联系">
              <el-input v-model="profileForm.other_contact" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
          <el-button type="primary" @click="saveProfile">保存品牌信息</el-button>
        </el-card>
      </el-tab-pane>

      <!-- 案例与技能 -->
      <el-tab-pane label="案例与技能" name="case-skill">
        <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <span>能力馆 · 案例</span>
              <el-button type="primary" size="small" @click="openCase()">
                <el-icon><Plus /></el-icon>新增案例
              </el-button>
            </div>
          </template>
          <div class="list">
            <div v-for="c in store.cases" :key="c.id" class="list-row">
              <div class="row-main">
                <div class="row-title">{{ c.title }}</div>
                <div class="row-sub">{{ [c.client, c.time_label].filter(Boolean).join(' · ') || '未填客户与时间' }}</div>
              </div>
              <el-switch v-model="c.is_visible" @change="toggleCaseVisible(c)" />
              <el-button size="small" @click="openCase(c)"><el-icon><Edit /></el-icon></el-button>
              <el-button size="small" type="danger" @click="removeCase(c)"><el-icon><Delete /></el-icon></el-button>
            </div>
            <el-empty v-if="!store.cases.length" description="还没有案例 —— 能力馆的证据，从这里开始填" :image-size="100" />
          </div>
        </el-card>

        <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <span>能力馆 · 技能</span>
              <el-button type="primary" size="small" @click="openSkill()">
                <el-icon><Plus /></el-icon>新增技能
              </el-button>
            </div>
          </template>
          <div class="list">
            <div v-for="s in store.skills" :key="s.id" class="list-row">
              <div class="row-main">
                <div class="row-title">{{ s.name }}</div>
                <div class="row-sub">{{ levelLabel(s.level) }}</div>
              </div>
              <el-switch v-model="s.is_visible" @change="toggleSkillVisible(s)" />
              <el-button size="small" @click="openSkill(s)"><el-icon><Edit /></el-icon></el-button>
              <el-button size="small" type="danger" @click="removeSkill(s)"><el-icon><Delete /></el-icon></el-button>
            </div>
            <el-empty v-if="!store.skills.length" description="还没有技能" :image-size="100" />
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 作品馆 -->
      <el-tab-pane label="作品馆" name="works">
        <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <span>作品馆 · 能力的活证据</span>
              <el-button type="primary" size="small" @click="openWork()">
                <el-icon><Plus /></el-icon>选作品进馆
              </el-button>
            </div>
          </template>
          <div class="list">
            <div v-for="w in store.works" :key="w.id" class="list-row">
              <div class="row-main">
                <div class="row-title">{{ w.work_name ?? w.title_snapshot }}</div>
                <div class="row-sub">{{ w.curator_note || w.work_summary || '未写策展导语' }}</div>
              </div>
              <el-switch v-model="w.is_visible" @change="toggleWorkVisible(w)" />
              <el-button size="small" @click="openWork(w)"><el-icon><Edit /></el-icon></el-button>
              <el-button size="small" type="danger" @click="removeWork(w)"><el-icon><Delete /></el-icon></el-button>
            </div>
            <el-empty v-if="!store.works.length" description="作品馆还空着 —— 去作品库挑几件能证明能力的作品" :image-size="100" />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <CaseForm v-model="caseDialog" :item="editingCase" @submit="saveCase" />
    <SkillForm v-model="skillDialog" :item="editingSkill" @submit="saveSkill" />
    <WorkForm v-model="workDialog" :item="editingWork" @submit="saveWork" />
  </div>
</template>

<style scoped>
.showroom-edit {
  max-width: 960px;
  margin: 0 auto;
  padding: 20px 24px 48px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
}
.hub-alert {
  margin-bottom: 16px;
}
.profile-form {
  max-width: 640px;
}
.section-card {
  margin-bottom: 16px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.list-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.row-main {
  flex: 1;
  min-width: 0;
}
.row-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}
.row-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
</style>
