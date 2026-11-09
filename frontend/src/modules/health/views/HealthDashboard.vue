<template>
  <div class="health-dashboard">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">🏃 生命步数目标</h1>
        <el-tag type="success" class="module-tag">身心健康</el-tag>
      </div>
      <div class="header-actions">
        <!-- v3.63.12：体重 / 好朋友两条记录原本各占一行菜单，现收回本页页头 ——
             它们和步数记录是同一份身体账本，日常动作都是「进来记一笔」。
             ⚠️ 放在最左、也放在「添加记录」之前：先选「记哪本账」，再记。 -->
        <el-button size="default" @click="$router.push('/health/weight')">
          ⚖️ 体重管理
        </el-button>
        <el-button size="default" @click="$router.push('/health/menstrual')">
          🩷 好朋友跟踪
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 添加记录
        </el-button>
        <el-button @click="refresh">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <!-- 长期不变的那几块（进度条 / 统计卡 / 里程碑地图 / 年度对比）搬去了总览页，
             本页只做「每天要干的活」：录入与查明细。—— 按钮样式与「贡献图」对齐。 -->
        <el-button size="default" @click="$router.push('/health/overview')">
          📈 步数总览
        </el-button>
        <el-button size="default" @click="$router.push('/health/contrib')">
          📊 贡献图
        </el-button>
      </div>
    </div>

    <!-- 运动记录 -->
    <el-card class="section-card">
      <template #header>
        <div class="section-header">
          <span>📝 运动记录</span>
        </div>
      </template>

      <!-- 筛选栏：年份 / 类型 / 日期范围 / 备注关键字 + 重置。
           ⚠️ 每个条件的 `@change` 都走 `resetAndFetch()`（**回第 1 页**再取）——
              拿着第 20 页去筛新条件，必然得到一张空表（v3.62.14 §93.3 的坑）。 -->
      <div class="filter-bar">
        <el-select
          v-model="filterYear" size="default" style="width: 112px"
          placeholder="全部年份" clearable @change="resetAndFetch"
        >
          <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
        </el-select>

        <el-select
          v-model="filterHtype" size="default" style="width: 118px"
          placeholder="全部类型" clearable @change="resetAndFetch"
        >
          <el-option v-for="t in HTYPE_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>

        <el-date-picker
          v-model="dateRange" type="daterange" size="default"
          value-format="YYYY-MM-DD" range-separator="→"
          start-placeholder="开始日期" end-placeholder="结束日期"
          style="width: 240px" @change="resetAndFetch"
        />

        <el-input
          v-model="filterKeyword" size="default" style="width: 190px"
          placeholder="搜索备注，回车确认" clearable
          @keyup.enter="resetAndFetch" @clear="resetAndFetch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <el-button size="default" @click="resetFilters">重置</el-button>
      </div>

      <!-- 🔴 `store.records` 就是**当前页**那 N 条 —— 分页交给后端。
           这里曾写 `displayRecords`（在本地对这 N 条再切一次），
           而后端只给了第 1 页 ⇒ 页码有 38 页、第 2 页起全空（v3.62.14 修）。 -->
      <el-table v-loading="store.loading" :data="store.records" style="width: 100%" size="small" stripe>
        <el-table-column label="日期" width="110">
          <template #default="{ row }">{{ formatTime(row.time) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="80">
          <template #default="{ row }">{{ row.htype_label }}</template>
        </el-table-column>
        <el-table-column label="原始量" width="80" prop="steps" />
        <el-table-column label="折算步数" width="110" prop="total" />
        <el-table-column label="备注" min-width="160" prop="remark" show-overflow-tooltip />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)"><el-icon><Edit /></el-icon></el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)"><el-icon><Delete /></el-icon></el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="store.totalCount > 0"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="PAGE_SIZE_OPTIONS"
        :total="store.totalCount"
        layout="total, sizes, prev, pager, next"
        small
        class="pagination"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog v-model="formVisible" :title="isEdit ? '编辑运动记录' : '🏃 添加运动记录'" width="480px" @close="resetForm">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="80px">
        <el-form-item label="运动类型" prop="htype">
          <el-select v-model="formData.htype" placeholder="选择类型" style="width:100%">
            <el-option v-for="t in HTYPE_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="运动量" prop="steps">
          <el-input-number v-model="formData.steps" :min="0" :max="100000" style="width:100%"
            :placeholder="formData.htype === 1 ? '输入步数' : formData.htype === 2 ? '输入跳绳个数' : formData.htype === 3 ? '输入跑步公里数(可小数)' : '输入骑行公里数(可小数)'" />
        </el-form-item>

        <el-form-item v-if="formData.htype !== 1" label="说明">
          <div class="convert-hint">
            {{
              formData.htype === 2 ? '1个跳绳 ≈ 0.5步 · 系统自动转换' :
              formData.htype === 3 ? '1公里跑步 ≈ 1300步 · 系统自动转换' :
              formData.htype === 4 ? '1公里骑行 ≈ 400步 · 系统自动转换' : ''
            }}
          </div>
        </el-form-item>

        <el-form-item label="日期" prop="time">
          <el-date-picker v-model="formData.time" type="datetime" placeholder="选择日期"
            format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" :rows="2" maxlength="255" placeholder="可选备注..." />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Edit, Delete, Search } from '@element-plus/icons-vue'
import { useHealthStore } from '../stores/healthStore'
import { HTYPE_OPTIONS, HTYPE_LABELS } from '../types/healthTypes'
import * as healthApi from '../api/healthApi'

const store = useHealthStore()

// ─── 筛选栏 ───
const filterYear = ref<number | undefined>(undefined)
const filterHtype = ref<number | undefined>(undefined)
const filterKeyword = ref('')
/** `el-date-picker` 的 range 值：`['YYYY-MM-DD', 'YYYY-MM-DD']`；清空时为 `null` */
const dateRange = ref<[string, string] | null>(null)

const currentPage = ref(1)
/** 每页条数：默认 20，可在分页条上切换（10 / 20 / 30 / 50） */
const PAGE_SIZE_OPTIONS = [10, 20, 30, 50]
const pageSize = ref(20)

const yearOptions = computed(() => {
  const years: number[] = []
  const y = new Date().getFullYear()
  for (let i = y; i >= y - 5; i--) years.push(i)
  return years
})

// 🔴 **页码与筛选必须一起发给后端** —— 分页只有一把尺子。
//
// 这个接口走 DRF 全局 `StandardPagination`，响应是 `{count, results}`：
// `results` 只是**当前页**。曾经这里不传 `page`，于是 `store.records` 永远只有
// 第 1 页那 10 条，而 `totalCount` 是 373 ⇒ 分页条照实渲染 **38 页**，
// 点第 2 页起却全空（v3.62.14 修）。
//
// ⚠️ `page_size` 也显式传：后端默认值改了这一页就会错位，尺子握在自己手里。
function buildRecordParams(): Record<string, unknown> {
  const params: Record<string, unknown> = { page: currentPage.value, page_size: pageSize.value }
  if (filterYear.value) params.year = filterYear.value
  if (filterHtype.value) params.htype = filterHtype.value
  if (filterKeyword.value) params.search = filterKeyword.value
  // 日期范围走后端 `start` / `end`（半开区间，含结束日整天）——
  // 不在这里做「前端过滤已取的那一页」，那会变成「总数与内容两把尺子」。
  if (dateRange.value && dateRange.value.length === 2) {
    params.start = dateRange.value[0]
    params.end = dateRange.value[1]
  }
  return params
}

/** 只重取「记录」那一块（翻页 / 删改后用；不打扰筛选栏本身） */
async function loadRecords() {
  await store.fetchRecords(buildRecordParams())
}

/** 筛选条件变了 ⇒ **回第 1 页**再取（旧页码在新条件下没有意义） */
async function resetAndFetch() {
  currentPage.value = 1
  await loadRecords()
}

function resetFilters() {
  filterYear.value = undefined
  filterHtype.value = undefined
  filterKeyword.value = ''
  dateRange.value = null
  resetAndFetch()
}

/** 手动刷新 ⇒ 也回第 1 页（刷新按钮的语义是「看最新的」，最新的一条排在最前） */
async function refresh() {
  await resetAndFetch()
}

// ─── 表单 ───
const formVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()
const formData = ref({
  steps: 0,
  htype: 1,
  time: '',
  remark: '',
})

const formRules = {
  steps: [{ required: true, message: '请输入运动量', trigger: 'blur' }],
  htype: [{ required: true, message: '请选择运动类型', trigger: 'change' }],
  time: [{ required: true, message: '请选择日期', trigger: 'change' }],
}

function formatTime(t: string | undefined | null): string {
  if (!t) return '-'
  return t.slice(0, 10)
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  formData.value = { steps: 0, htype: 1, time: '', remark: '' }
  formVisible.value = true
}

function openEdit(row: any) {
  isEdit.value = true
  editingId.value = row.hid
  formData.value = {
    steps: row.steps ?? 0,
    htype: row.htype ?? 1,
    time: row.time || '',
    remark: row.remark || '',
  }
  formVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const payload = { ...formData.value }
    if (isEdit.value && editingId.value) {
      await healthApi.updateHealth(editingId.value, payload)
    } else {
      await healthApi.createHealth(payload)
    }
    ElMessage.success(isEdit.value ? '已更新' : '已添加')
    formVisible.value = false
    // 新增 ⇒ 回第 1 页（新记录按时间倒序排在最前，那儿才看得到它）；
    // 编辑 ⇒ **留在原页**（把人从第 5 页弹回开头 = 另一种「看不到刚才那条」）
    if (isEdit.value) await loadRecords()
    else await resetAndFetch()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除 ${formatTime(row.time)} ${HTYPE_LABELS[row.htype] || ''}？`, '提示', { type: 'warning' })
    await healthApi.deleteHealth(row.hid)
    ElMessage.success('已删除')
    // 🔴 删掉本页最后一条 ⇒ 留原页会显示空表（页码还在、数据没了）。
    //    `store.totalCount` 此刻还是**删除前**的数，减 1 才是删完的总数。
    //    ⚠️ 这里不能走 `resetAndFetch()`：它会把人从第 20 页弹回第 1 页 ——
    //       那是另一种「看不到刚才那条」。
    const lastPage = Math.max(1, Math.ceil(Math.max(0, store.totalCount - 1) / pageSize.value))
    if (currentPage.value > lastPage) currentPage.value = lastPage
    await loadRecords()
  } catch { /* cancelled */ }
}

function resetForm() {
  formRef.value?.resetFields()
}

async function handlePageChange(p: number) {
  // 🔴 改页码必须**重新取数** —— 后端分页时 `store.records` 里只有当前页，
  //    只改 `currentPage` 不重新请求 = 表里还是上一页的内容（或空）。
  // ⚠️ 顺便夹住页码：DRF 对**超出范围**的页码回 404（不是空数组），
  //    点到一个不存在的页会得到一条报错，而不是「暂无数据」。
  const lastPage = Math.max(1, Math.ceil(store.totalCount / pageSize.value))
  currentPage.value = Math.min(p, lastPage)
  await loadRecords()
}

async function handleSizeChange() {
  // 🔴 每页条数变了 ⇒ 「第几页」不再指向同一批数据（第 5 页在 20 条/页与
  //    50 条/页下完全是两段）⇒ 必须回第 1 页重取，不能只改 pageSize 让它自己算。
  currentPage.value = 1
  await loadRecords()
}

onMounted(async () => {
  // 记录那一块要带上 `page` + `page_size` —— 否则后端只给第 1 页（见 `buildRecordParams`）
  await loadRecords()
})
</script>

<style scoped lang="scss">
.health-dashboard {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    .header-left { display: flex; align-items: center; gap: 12px;
      .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    }
    .header-actions { display: flex; gap: 8px; align-items: center; }
  }

  .section-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px;
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
    .pagination { margin-top: 12px; justify-content: flex-end; }
    .section-header { display: flex; justify-content: space-between; align-items: center; }
  }

  .filter-bar {
    display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
    margin-bottom: 14px; padding-bottom: 14px; border-bottom: 1px dashed #ebeef5;
  }

  .convert-hint { font-size: 12px; color: #909399; line-height: 1.5; }
}
</style>
