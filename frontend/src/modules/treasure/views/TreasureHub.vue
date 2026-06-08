<template>
  <div class="treasure-hub">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">好恶物档案馆</h1>
        <el-tag type="warning" class="module-tag">精神滋养</el-tag>
      </div>
      <div class="header-actions">
        <el-dropdown @command="handleAddNew">
          <el-button type="primary">
            <el-icon><Plus /></el-icon>
            新增记录
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="好">👍 好物</el-dropdown-item>
              <el-dropdown-item command="歹">👎 歹物</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 类型 TAB -->
    <el-card class="filter-card">
      <el-radio-group v-model="filterType" @change="fetchData" class="type-tabs">
        <el-radio-button value="">📋 全部</el-radio-button>
        <el-radio-button value="好">👍 好物</el-radio-button>
        <el-radio-button value="歹">👎 歹物</el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- 类别筛选 -->
    <el-card v-if="filterType !== '歹'" class="filter-card">
      <el-radio-group v-model="filterCategory" @change="fetchData" class="category-tabs">
        <el-radio-button value="">全类别</el-radio-button>
        <el-radio-button v-for="c in CATEGORY_OPTIONS" :key="c.value" :value="c.value">
          {{ c.label }}
        </el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- 歹物防遗忘提示 -->
    <el-card v-if="showBadReminder" class="reminder-card">
      <el-alert
        title="👀 你有歹物记录，看看之前踩过的坑！"
        type="warning"
        :closable="true"
        show-icon
        @close="showBadReminder = false"
      />
    </el-card>

    <!-- 卡片网格 -->
    <div v-loading="store.loading" class="card-grid">
      <TreasureCard
        v-for="thing in store.thingList" :key="thing.id"
        :thing="thing"
        @edit="openEdit"
        @delete="handleDelete"
      />
      <el-empty v-if="!store.thingList.length && !store.loading" description="还没有记录，快添加一个吧" :image-size="120" />
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="540px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="叫什么名字？" maxlength="200" />
        </el-form-item>
        <el-form-item label="类别" prop="category">
          <el-select v-model="form.category" placeholder="属于哪一类？" style="width:100%">
            <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>

        <!-- 好物字段 -->
        <template v-if="form.record_type === '好'">
          <el-form-item label="为什么好" prop="why_good">
            <el-input v-model="form.why_good" type="textarea" :rows="3" placeholder="它好在哪？你的真实感受…" maxlength="1000" />
          </el-form-item>
          <el-form-item label="场景">
            <el-input v-model="form.scene" placeholder="在什么场景下遇到的？" maxlength="200" />
          </el-form-item>
          <el-form-item label="还能找到吗">
            <el-switch v-model="form.still_available" active-text="能" inactive-text="不能" />
          </el-form-item>
          <el-form-item label="在哪能找到">
            <el-input v-model="form.where_to_find" placeholder="店铺、地点、链接…" maxlength="200" :disabled="!form.still_available" />
          </el-form-item>
        </template>

        <!-- 歹物字段 -->
        <template v-if="form.record_type === '歹'">
          <el-form-item label="踩坑原因" prop="avoid_reason">
            <el-input v-model="form.avoid_reason" type="textarea" :rows="2" placeholder="为什么踩坑？" maxlength="1000" />
          </el-form-item>
          <el-form-item label="实际后果">
            <el-input v-model="form.consequence" type="textarea" :rows="2" placeholder="造成了什么后果？" maxlength="1000" />
          </el-form-item>
          <el-form-item label="场景">
            <el-input v-model="form.scene" placeholder="在哪遇到的？" maxlength="200" />
          </el-form-item>
        </template>

        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="多个标签用逗号分隔" maxlength="200" />
        </el-form-item>
        <el-form-item v-if="form.record_type === '好'" label="评分">
          <el-rate v-model="form.rating" :max="5" show-score />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, ArrowDown } from '@element-plus/icons-vue'
import { useTreasureStore } from '../stores/treasureStore'
import { CATEGORY_OPTIONS, RECORD_TYPE_OPTIONS } from '../types/treasureTypes'
import type { GoodThing } from '../types/treasureTypes'
import TreasureCard from '../components/TreasureCard.vue'

const store = useTreasureStore()

const filterType = ref('')
const filterCategory = ref('')
const showBadReminder = ref(true)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  record_type: '好',
  name: '',
  category: '',
  why_good: '',
  scene: '',
  still_available: true,
  where_to_find: '',
  avoid_reason: '',
  consequence: '',
  tags: '',
  rating: 5,
})

const dialogTitle = computed(() => {
  const t = form.record_type === '歹' ? '歹物' : '好物'
  return editingId.value ? `编辑${t}` : `新增${t}`
})

const formRules = computed(() => ({
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择类别', trigger: 'change' }],
  why_good: form.record_type === '好'
    ? [{ required: true, message: '请描述为什么好', trigger: 'blur' }]
    : [],
  avoid_reason: form.record_type === '歹'
    ? [{ required: true, message: '请描述踩坑原因', trigger: 'blur' }]
    : [],
}))

function resetForm(type = '好') {
  form.record_type = type
  form.name = ''
  form.category = ''
  form.why_good = ''
  form.scene = ''
  form.still_available = true
  form.where_to_find = ''
  form.avoid_reason = ''
  form.consequence = ''
  form.tags = ''
  form.rating = 5
}

function handleAddNew(type: string) {
  editingId.value = null
  resetForm(type)
  dialogVisible.value = true
}

function openEdit(thing: GoodThing) {
  editingId.value = thing.id
  form.record_type = thing.record_type
  form.name = thing.name
  form.category = thing.category
  form.why_good = thing.why_good
  form.scene = thing.scene
  form.still_available = thing.still_available
  form.where_to_find = thing.where_to_find
  form.avoid_reason = thing.avoid_reason
  form.consequence = thing.consequence
  form.tags = thing.tags
  form.rating = thing.rating
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const data: Record<string, unknown> = {
      record_type: form.record_type,
      name: form.name.trim(),
      category: form.category,
      scene: form.scene.trim(),
      tags: form.tags.trim(),
    }
    if (form.record_type === '好') {
      data.why_good = form.why_good.trim()
      data.still_available = form.still_available
      data.where_to_find = form.where_to_find.trim()
      data.rating = form.rating
    } else {
      data.avoid_reason = form.avoid_reason.trim()
      data.consequence = form.consequence.trim()
    }
    if (editingId.value) {
      await store.updateThing(editingId.value, data)
      ElMessage.success('已更新')
    } else {
      await store.createThing(data)
      ElMessage.success('已记录')
    }
    dialogVisible.value = false
    fetchData()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(thing: GoodThing) {
  try {
    await ElMessageBox.confirm(`确定删除"${thing.name}"？`, '提示', { type: 'warning' })
    await store.deleteThing(thing.id)
    ElMessage.success('已删除')
    fetchData()
  } catch { /* cancelled */ }
}

function fetchData() {
  const params: Record<string, unknown> = {}
  if (filterType.value) params.record_type = filterType.value
  if (filterCategory.value && filterType.value !== '歹') params.category = filterCategory.value
  store.fetchThingList(params)
}

function refreshData() {
  fetchData()
}

onMounted(() => { fetchData() })
</script>

<style scoped lang="scss">
.treasure-hub {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .header-left { display: flex; align-items: center; gap: 12px;
    .page-title { margin: 0; font-size: 24px; font-weight: 600; }
  }
  .header-actions { display: flex; gap: 8px; }
}

.filter-card { margin-bottom: 12px;
  :deep(.el-card__body) { padding: 12px 16px; }
  .type-tabs, .category-tabs { width: 100%; display: flex; flex-wrap: wrap; gap: 4px; }
}

.reminder-card { margin-bottom: 12px;
  :deep(.el-card__body) { padding: 8px 12px; }
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}
</style>
