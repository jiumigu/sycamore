<template>
  <div class="book-view">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">阅读管理</h1>
        <el-tag type="primary" class="module-tag">知识沉淀</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="goCharts">
          <el-icon><DataAnalysis /></el-icon>
          图形分析
        </el-button>
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新建书籍
        </el-button>
        <el-button @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 「当前这本」横条 —— 一本书闸门（v3.65.x）
         存在的理由：状态只回答「这本书走到哪一步」，而「在读」的书可以有很多本，
         于是「今天读哪本」没有唯一答案，每天早上都要重新挑一次、挑的还总是同一批。
         这一条是**指针**（`book_reading_focus`，全库一行），不是状态：
         它答的是「现在读哪本」，不参与任何统计、不随列表筛选变化。 -->
    <div class="focus-bar" :class="{ 'is-empty': !focusBook }">
      <div class="focus-main">
        <span class="focus-label">当前这本</span>
        <template v-if="focusBook">
          <span class="focus-title">{{ formatBookTitle(focusBook.btitle) }}</span>
          <span v-if="focusBook.author" class="focus-author">{{ focusBook.author }}</span>
          <el-tag size="small" effect="plain" class="focus-status">
            {{ focusBook.status_display }}
          </el-tag>
          <span v-if="focusDays !== null" class="focus-days">第 {{ focusDays }} 天</span>
        </template>
        <span v-else class="focus-empty">
          还没指定 —— 列表里开着的都只是「在读」，不等于「现在这本」
        </span>
      </div>
      <el-button size="small" :type="focusBook ? 'default' : 'primary'" @click="openSwitchDialog">
        {{ focusBook ? '换一本' : '选一本开始' }}
      </el-button>
    </div>

    <div class="stats-section">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon" style="background: #e6f7ff">
                <el-icon color="#1890ff"><Document /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats?.total_count || 0 }}</div>
                <div class="stat-label">总书籍数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon" style="background: #f6ffed">
                <el-icon color="#52c41a"><Check /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats?.completed_count || 0 }}</div>
                <div class="stat-label">已读完</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon" style="background: #fff7e6">
                <el-icon color="#fa8c16"><Star /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats?.avg_recommend?.toFixed(1) || '0' }}</div>
                <div class="stat-label">平均推荐</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon" style="background: #fff1f0">
                <el-icon color="#f5222d"><Calendar /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats?.month_count || 0 }}</div>
                <div class="stat-label">本月新增</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-card class="filter-card">
      <div class="filter-header">
        <div class="search-section">
          <el-input
            v-model="searchForm.search"
            placeholder="搜索书名或作者..."
            class="search-input"
            :prefix-icon="Search"
            clearable
            @input="handleSearch"
          />
        </div>
        <div class="filter-section">
          <el-select v-model="searchForm.year" placeholder="年份" clearable @change="handleSearch" class="filter-select">
            <el-option v-for="y in yearOptions" :key="y" :label="y" :value="String(y)" />
          </el-select>
          <el-select v-model="searchForm.btype" placeholder="书籍类型" clearable @change="handleSearch" class="filter-select">
            <el-option v-for="t in BTYPE_OPTIONS" :key="t" :label="t" :value="t" />
          </el-select>
          <el-select v-model="searchForm.status" placeholder="阅读状态" clearable @change="handleSearch" class="filter-select">
            <el-option v-for="s in STATUS_OPTIONS" :key="s" :label="STATUS_LABELS[s]" :value="s" />
          </el-select>
          <el-select v-model="searchForm.reading_depth" placeholder="阅读深度" clearable @change="handleSearch" class="filter-select">
            <el-option v-for="d in READING_DEPTH_OPTIONS" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
          <el-button @click="resetSearch" class="reset-btn">
            <el-icon><RefreshRight /></el-icon>重置
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 批量工具条 —— **选中行后才出现**。
         和上面那张筛选卡分开，是因为两者「量的不是同一类东西」：
         筛选卡改的是「这张表给我看什么」，这里改的是「选中的那几本变成什么」，
         混成一条会把筛选状态和选中状态搅在一起（§81.1）。
         ⚠️ 只有两件事：状态 / 深度 —— 「弃读」不在状态选项里（见 BULK_STATUS_OPTIONS）。 -->
    <div v-if="selectedCount" class="bulk-bar">
      <span class="bulk-count">已选 <b>{{ selectedCount }}</b> 本</span>

      <el-dropdown trigger="click" @command="applyBatchStatus">
        <el-button size="small" type="primary" plain>
          批量改状态<el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="s in BULK_STATUS_OPTIONS" :key="s" :command="s">
              <el-tag :type="getStatusTagType(s)" size="small" effect="plain">{{ STATUS_LABELS[s] }}</el-tag>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-dropdown trigger="click" @command="applyBatchDepth">
        <el-button size="small" type="primary" plain>
          批量改阅读深度<el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="d in READING_DEPTH_OPTIONS" :key="d.value" :command="d.value">
              <el-tag :type="getDepthTagType(d.value)" size="small" effect="plain">{{ d.label }}</el-tag>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-button size="small" @click="clearSelection">取消选择</el-button>
    </div>

    <el-card class="table-card">
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="bookList"
        style="width: 100%"
        @selection-change="handleSelectionChange"
        @row-dblclick="openEditDialog"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="bid" label="ID" width="70" sortable />
        <el-table-column label="书名" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ formatBookTitle(row.btitle) }}</template>
        </el-table-column>
        <el-table-column prop="author" label="作者" width="120" show-overflow-tooltip />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ row.btype_display || row.btype }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">{{ row.status_display || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="阅读深度" width="90">
          <template #default="{ row }">
            <el-tag :type="getDepthTagType(row.reading_depth)" size="small">{{ row.reading_depth_display || '未知' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="推荐" width="100">
          <template #default="{ row }">
            <div class="recommend-stars">
              <span v-for="i in 5" :key="i" class="star" :class="{ active: i <= (row.recommend || 0) }">★</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="阅读日期" width="110" sortable>
          <template #default="{ row }">{{ row.readDate?.slice(0, 10) || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEditDialog(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalCount"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'create' ? '新建书籍' : '编辑书籍'"
      width="700px"
      destroy-on-close
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="110px" class="book-form">
        <div class="form-section">
          <h3 class="section-title">📖 基本信息</h3>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="书名" prop="btitle">
                <el-input v-model="formData.btitle" placeholder="请输入书名" />
                <div class="field-hint">书名号《》会自动补全，无需手动输入</div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="作者" prop="author">
                <el-input v-model="formData.author" placeholder="请输入作者" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="原著书名" prop="original_title">
                <el-input v-model="formData.original_title" placeholder="原著书名（可选）" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="年度" prop="years">
                <el-input v-model="formData.years" disabled />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="书籍类型" prop="btype">
                <el-select v-model="formData.btype" placeholder="请选择类型" style="width: 100%">
                  <el-option v-for="t in BTYPE_OPTIONS" :key="t" :label="t" :value="t" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="阅读状态" prop="status">
                <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%" @change="onStatusChange">
                  <el-option v-for="s in STATUS_OPTIONS" :key="s" :label="STATUS_LABELS[s]" :value="s" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <!-- 作品（v3.62.0）：**只有状态是「已读完」时才出现** ——
               在读的书没有「读完了留下什么」这回事。 -->
          <el-form-item v-if="formData.status === 'finished'">
            <div class="keep-row">
              <el-checkbox v-model="formData.keepIt">这本书里有东西值得留下</el-checkbox>
              <!-- ⚠️ `el-popover` 而不是 `el-tooltip`（两者插槽语义是反的）：
                   tooltip 的默认插槽是「触发元素」、正文要走 `#content`；
                   popover 才是「`#reference` 触发 + 默认插槽正文」。
                   写错不报错，只是正文被当成触发内容**内联渲染、常驻可见**。 -->
              <el-popover placement="top" :width="340" trigger="hover" :show-after="120">
                <template #reference>
                  <el-icon class="keep-icon"><QuestionFilled /></el-icon>
                </template>
                <div class="keep-tip">
                  <p>勾了<b>不用现在写</b>什么 —— 它只把这本书放进「待提炼」。</p>
                  <p>
                    在<b>「本周状态」页末</b>把它收成一件东西
                    （一个模型、一段书评、一份清单都算）。
                  </p>
                </div>
              </el-popover>
            </div>
          </el-form-item>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="阅读深度" prop="reading_depth">
                <el-select v-model="formData.reading_depth" placeholder="请选择" style="width: 100%">
                  <el-option v-for="d in READING_DEPTH_OPTIONS" :key="d.value" :label="d.label" :value="d.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="推荐指数" prop="recommend">
                <el-rate v-model="formData.recommend" :max="5" show-text :texts="RECOMMEND_TEXTS" style="line-height: 32px" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="阅读日期" prop="readDate">
            <el-date-picker
              v-model="formData.readDate"
              type="date"
              placeholder="选择阅读日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              style="width: 100%"
              @change="onReadDateChange"
            />
          </el-form-item>
        </div>

        <div class="form-section">
          <h3 class="section-title">💭 阅读体验</h3>
          <el-form-item label="读前观点" prop="openop">
            <el-input v-model="formData.openop" type="textarea" rows="3" placeholder="记录打开书时的观点和期待" maxlength="1000" show-word-limit />
          </el-form-item>
          <el-form-item label="读后感" prop="closedop">
            <el-input v-model="formData.closedop" type="textarea" rows="4" placeholder="记录读完书后的感想和收获" maxlength="2000" show-word-limit />
          </el-form-item>
          <el-form-item label="行动项" prop="action_item">
            <el-input v-model="formData.action_item" type="textarea" rows="2" placeholder="读完这本书，我决定做一件什么事？" maxlength="500" show-word-limit />
          </el-form-item>
          <el-form-item v-if="formData.status === 'abandoned'" label="弃读原因" prop="abandon_reason">
            <el-input v-model="formData.abandon_reason" type="textarea" rows="3" placeholder="请记录弃读原因..." maxlength="500" show-word-limit />
          </el-form-item>
          <el-form-item label="标签" prop="tags">
            <div class="tags-wrapper">
              <span class="preset-label">常用：</span>
              <el-tag
                v-for="tag in presetTags"
                :key="tag"
                size="small"
                :class="{ selected: formData.tags.includes(tag) }"
                class="preset-tag"
                @click="togglePresetTag(tag)"
              >
                {{ tag }}
              </el-tag>

              <div class="custom-tags">
                <el-tag
                  v-for="tag in customTags"
                  :key="tag"
                  closable
                  size="small"
                  type="warning"
                  @close="removeTag(tag)"
                >
                  {{ tag }}
                </el-tag>
                <el-input
                  v-if="showTagInput"
                  ref="tagInputRef"
                  v-model="newTag"
                  size="small"
                  style="width: 90px"
                  placeholder="回车添加"
                  @keyup.enter="addTag"
                  @blur="addTag"
                />
                <el-button v-else size="small" @click="openTagInput">+ 自定义</el-button>
              </div>
            </div>
            <div class="tags-hint">常用标签可在「系统预设管理 → 图书预设标签」中维护</div>
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 换书弹窗 —— 三个出口是**强制**的：不选出口不给换。
         原因：悄悄切走会让一本读了半年的书无声消失（既没读完、也没弃读、
         也没回待读池），而这正是「一堆书同时开着」的成因。 -->
    <el-dialog v-model="switchVisible" :title="focusBook ? '换一本' : '选一本开始'" width="520px">
      <div v-if="focusBook" class="switch-current">
        <span class="switch-current-label">现在读</span>
        <span class="switch-current-title">{{ formatBookTitle(focusBook.btitle) }}</span>
        <span v-if="focusDays !== null" class="switch-current-days">第 {{ focusDays }} 天</span>
      </div>

      <template v-if="focusBook">
        <div class="switch-field-label">先给它一个结论</div>
        <el-radio-group v-model="switchForm.close_mode" class="switch-modes">
          <el-radio-button value="finished">读完</el-radio-button>
          <el-radio-button value="abandoned">弃读</el-radio-button>
          <el-radio-button value="later">先放回</el-radio-button>
        </el-radio-group>
        <div v-if="switchForm.close_mode === 'finished'" class="switch-hint">
          标记为「已读完」，阅读日期记今天。
        </div>
        <div v-else-if="switchForm.close_mode === 'later'" class="switch-hint">
          放回「待读」，不做结论。
        </div>
        <el-input
          v-else-if="switchForm.close_mode === 'abandoned'"
          v-model="switchForm.reason"
          type="textarea"
          :rows="2"
          maxlength="500"
          show-word-limit
          placeholder="为什么读不下去？（必填）"
          class="switch-reason"
        />
      </template>

      <div class="switch-field-label">接下来读哪本</div>
      <el-select
        v-model="switchForm.book_id"
        filterable
        remote
        clearable
        reserve-keyword
        :remote-method="searchCandidates"
        :loading="candidateLoading"
        popper-class="focus-switch-popper"
        placeholder="搜书名或作者"
        class="switch-select"
      >
        <el-option
          v-for="b in candidates"
          :key="b.bid"
          :label="formatBookTitle(b.btitle)"
          :value="b.bid"
        >
          <span class="switch-option-row">
            <span class="switch-option-title">{{ formatBookTitle(b.btitle) }}</span>
            <span class="switch-option-meta">{{ b.author || '—' }} · {{ b.status_display || '—' }}</span>
          </span>
        </el-option>
      </el-select>
      <div v-if="candidateLoaded && !candidates.length" class="switch-hint">
        没搜到。换个关键词，或先去「新建书籍」把它加进来。
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="switchVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="submitting"
            :disabled="!canSwitch"
            @click="submitSwitch"
          >
            确定
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  Search, Refresh, Plus, Delete, Edit, Document, Check, Star, Calendar, RefreshRight, DataAnalysis,
  QuestionFilled, ArrowDown,
} from '@element-plus/icons-vue'
import { useBookStore } from '../stores/bookStore'
import { getPresetByType } from '@/shared/api/coreApi'
// 「值得留下」→ 作品库的「待提炼」（v3.62.0）。三个入口同一个模式：**前端串联**。
import { capture as captureWork } from '@/modules/works/api/workApi'
import {
  BTYPE_OPTIONS, STATUS_OPTIONS, STATUS_LABELS, STATUS_TAG_TYPE,
  READING_DEPTH_OPTIONS, RECOMMEND_TEXTS, BULK_STATUS_OPTIONS,
} from '../types/bookTypes'
import type { Book, BookStatus, ReadingFocusCloseMode } from '../types/bookTypes'

const router = useRouter()
const bookStore = useBookStore()

const loading = computed(() => bookStore.loading)
const submitting = computed(() => bookStore.submitting)
const bookList = computed(() => bookStore.bookList)
const stats = computed(() => bookStore.stats)
const totalCount = computed(() => bookStore.totalCount)

const currentPage = ref(1)
const pageSize = ref(20)
// 表格选中：**只存「选中的行」这一份**，编号与数量都从它推出来。
// 原先另有一个 `selectedIds`，赋值之后没有任何消费方 ——
// 勾选框勾了等于没勾（本轮需求的由来）。两份状态各写各的，迟早
// 出现「勾了说没勾」（§64/§76：身份/去重/判据只许一把尺子）。
const selectedRows = ref<Book[]>([])
const selectedIds = computed(() => selectedRows.value.map(r => r.bid))
const selectedCount = computed(() => selectedRows.value.length)
const tableRef = ref<{ clearSelection: () => void } | null>(null)
const dialogVisible = ref(false)
const dialogType = ref<'create' | 'edit'>('create')
const formRef = ref<FormInstance>()

// ── 一本书闸门（v3.65.x）──────────────────────────────────────
// `focus` 的三字段要么同时有值、要么同时为 null（后端保证）。
// 所以「有没有当前这本」只判 `focusBook`，不判 `days` —— `days` 为 null
// 只说明「开始日期算不出来」，不是「没有当前这本」。
const focusBook = computed(() => bookStore.focus?.book ?? null)
const focusDays = computed(() => bookStore.focus?.days ?? null)

const switchVisible = ref(false)
// 🔴 `close_mode` 默认 **空**，不是 `'finished'`：
//    默认成「读完」的话，忘了选出口的人会静默把书标成已读完 ——
//    这个功能存在的意义正是「不许悄悄切走」。
const switchForm = reactive<{
  book_id: number | undefined
  close_mode: ReadingFocusCloseMode | ''
  reason: string
}>({ book_id: undefined, close_mode: '', reason: '' })
const candidates = computed(() => bookStore.focusCandidates)
const candidateLoading = ref(false)
const candidateLoaded = ref(false)

const canSwitch = computed(() => {
  if (!switchForm.book_id) return false
  if (focusBook.value && !switchForm.close_mode) return false
  if (switchForm.close_mode === 'abandoned' && !switchForm.reason.trim()) return false
  return true
})

const yearOptions = computed(() => {
  const years: number[] = []
  const cy = new Date().getFullYear()
  for (let i = cy; i >= cy - 10; i--) years.push(i)
  return years
})

const searchForm = reactive({
  year: '', btype: '', status: '',
  reading_depth: undefined as number | undefined,
  search: '',
})

const formData = reactive({
  bid: undefined as number | undefined,
  years: '', btitle: '', author: '', original_title: '',
  btype: '', status: '', recommend: 3, reading_depth: 3,
  readDate: '', openop: '', closedop: '', action_item: '', abandon_reason: '',
  tags: [] as string[],
  // 作品（v3.62.0）：**只在状态是「已读完」时**才露出来。
  // ⚠️ 默认「不勾」—— 把它默认打开，等于替用户判断「这本书值得留」。
  keepIt: false,
})

const formRules: FormRules = {
  btitle: [
    { required: true, message: '请输入书名', trigger: 'blur' },
    { max: 255, message: '书名不能超过 255 个字符', trigger: 'blur' },
  ],
  btype: [{ required: true, message: '请选择书籍类型', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

/** 状态 → el-tag type。🔴 表在 `bookTypes.ts`（唯一一份）：
 *  列表、批量下拉、图表页共用；这里再写一份就会出现「同一条状态两个颜色」，
 *  而两处各自都看着正常。 */
function getStatusTagType(status: string) {
  return STATUS_TAG_TYPE[status as BookStatus] ?? 'info'
}

function getDepthTagType(depth: number) {
  const map: Record<number, string> = { 1: 'info', 2: 'info', 3: 'primary', 4: 'warning', 5: 'success' }
  return map[depth] || 'info'
}

function onReadDateChange(val: string) {
  formData.years = val ? new Date(val).getFullYear().toString() : ''
}

/** 剥离书名号——存量导入数据可能带《》，统一在展示层归一化，不入库 */
function stripBookMarks(title?: string | null) {
  return (title || '').trim().replace(/^《+/, '').replace(/》+$/, '').trim()
}

/** 书名统一展示为《书名》，避免“有的带有的不带” */
function formatBookTitle(title?: string | null) {
  const t = stripBookMarks(title)
  return t ? `《${t}》` : ''
}

function onStatusChange(status: string) {
  if (status !== 'abandoned') formData.abandon_reason = ''
  // 状态离开「已读完」⇒ 把勾也收掉 ——
  // 否则改回「在读」再保存，那条「值得留下」还会跟着发出去（静默的错）。
  if (status !== 'finished') formData.keepIt = false
}

function handleSelectionChange(val: Book[]) {
  selectedRows.value = val
}

function clearSelection() {
  tableRef.value?.clearSelection()
  selectedRows.value = []
}

/** 批量提交的**唯一出口** —— 两个动作只有 `payload` 与文案不同。 */
async function runBulk(
  ids: number[],
  payload: { status?: string; reading_depth?: number },
  what: string,
) {
  try {
    const res = await bookStore.bulkUpdateBooks(ids, payload)
    const n = res?.updated ?? 0
    // 🔴 命中 0 条要说出来：选中的书可能已被别处删掉。静默报「成功」
    // 会让人以为改了 —— 和「勾了没反应」是同一个病（把「没做」说成「做了」）。
    if (n) ElMessage.success(`已把 ${n} 本改为${what}`)
    else ElMessage.warning('没有书籍被改动 —— 选中的书可能已经不在了，刷新看看')
    clearSelection()
    await fetchData()
    await fetchStats()
  } catch {
    ElMessage.error('批量修改失败')
  }
}

/** 批量改状态。`弃读` 不在这里（它要逐本填原因，见 `BULK_STATUS_OPTIONS`）。 */
async function applyBatchStatus(status: string) {
  const ids = selectedIds.value.slice()
  if (!ids.length) return
  // 文案用中文词：`status` 现在是英文 key（`shelved`），直接拼进句子会写成
  // 「把选中的 3 本改成「shelved」？」—— 用户看不懂，而且看着像出了 bug。
  const label = STATUS_LABELS[status as BookStatus] ?? status
  // 判据读**选中行自己的状态**（不读任何「还没答的东西」）
  const todo = selectedRows.value.filter(r => r.status !== status).length
  if (!todo) {
    ElMessage.warning(`选中的 ${ids.length} 本都已经是「${label}」了，不用改`)
    return
  }
  const same = ids.length - todo
  const tail = same ? `（另外 ${same} 本已经是这个状态）` : ''
  try {
    await ElMessageBox.confirm(`把选中的 ${todo} 本改成「${label}」？${tail}`, '批量改状态', {
      type: 'warning',
    })
  } catch {
    return // 用户点了取消（Element 以 'cancel'/'close' reject）—— 什么都不做才是对的
  }
  await runBulk(ids, { status }, `「${label}」`)
}

/** 批量改阅读深度。
 *  `command` 的静态类型是 `string | number | object`（同 SurvivalStocktakePanel 的写法）。 */
async function applyBatchDepth(depthRaw: string | number | object) {
  const depth = Number(depthRaw)
  const ids = selectedIds.value.slice()
  if (!ids.length || !depth) return
  const label = READING_DEPTH_OPTIONS.find(d => d.value === depth)?.label || String(depth)
  const todo = selectedRows.value.filter(r => r.reading_depth !== depth).length
  if (!todo) {
    ElMessage.warning(`选中的 ${ids.length} 本都已经是「${label}」了，不用改`)
    return
  }
  const same = ids.length - todo
  const tail = same ? `（另外 ${same} 本已经是这个深度）` : ''
  try {
    await ElMessageBox.confirm(`把选中的 ${todo} 本改成「${label}」？${tail}`, '批量改阅读深度', {
      type: 'warning',
    })
  } catch {
    return
  }
  await runBulk(ids, { reading_depth: depth }, `「${label}」`)
}

function handleSearch() { currentPage.value = 1; fetchData() }

function resetSearch() {
  Object.assign(searchForm, { year: '', btype: '', status: '', reading_depth: undefined, search: '' })
  fetchData()
}

async function fetchData() {
  const params: Record<string, unknown> = { page: currentPage.value, page_size: pageSize.value }
  if (searchForm.year) params.years = searchForm.year
  if (searchForm.btype) params.btype = searchForm.btype
  if (searchForm.status) params.status = searchForm.status
  if (searchForm.reading_depth !== undefined) params.reading_depth = searchForm.reading_depth
  if (searchForm.search) params.search = stripBookMarks(searchForm.search)
  try {
    await bookStore.fetchBookList(params)
  } catch { ElMessage.error('获取数据失败') }
}

async function fetchStats() {
  try { await bookStore.fetchStats() } catch {}
}

function goCharts() {
  router.push('/books/charts')
}

// ── 一本书闸门 ────────────────────────────────────────────────
async function fetchFocus() {
  try { await bookStore.fetchReadingFocus() } catch { /* 横条空着即可，不打断页面 */ }
}

function openSwitchDialog() {
  switchForm.book_id = undefined
  switchForm.close_mode = ''
  switchForm.reason = ''
  candidateLoaded.value = false
  switchVisible.value = true
  // 一打开就预载 20 本（按最近更新排），省得必须先打字才看得见东西
  void searchCandidates('')
}

async function searchCandidates(keyword: string) {
  candidateLoading.value = true
  try {
    await bookStore.searchFocusCandidates((keyword || '').trim())
    candidateLoaded.value = true
  } catch {
    ElMessage.error('搜索书目失败')
  } finally {
    candidateLoading.value = false
  }
}

async function submitSwitch() {
  if (!switchForm.book_id) return
  // 没有旧书时**不能**传 close_mode：后端会按「你以为在关一本书」拒掉（400）
  const closeMode = focusBook.value
    ? (switchForm.close_mode as ReadingFocusCloseMode)
    : undefined
  try {
    const result = await bookStore.switchFocus(
      switchForm.book_id, closeMode, switchForm.reason,
    )
    ElMessage.success(`现在读：${formatBookTitle(result.book?.btitle)}`)
    switchVisible.value = false
    // 旧书状态变了 ⇒ 表格与统计都要重取（不能只改横条）
    await Promise.all([fetchData(), fetchStats()])
  } catch (error) {
    const detail = (error as { response?: { data?: { error?: string } } })
      ?.response?.data?.error
    ElMessage.error(detail || '换书失败')
  }
}

function resetForm() {
  const now = new Date()
  formData.bid = undefined
  formData.years = now.getFullYear().toString()
  formData.btitle = ''
  formData.author = ''
  formData.original_title = ''
  formData.btype = ''
  formData.status = ''
  formData.recommend = 3
  formData.reading_depth = 3
  formData.readDate = now.toISOString().slice(0, 10)
  formData.openop = ''
  formData.closedop = ''
  formData.abandon_reason = ''
  formData.tags = []
}

function openCreateDialog() { dialogType.value = 'create'; resetForm(); dialogVisible.value = true }

async function openEditDialog(row: Book) {
  dialogType.value = 'edit'
  try {
    const detail = await bookStore.fetchBookById(row.bid)
    if (!detail) return
    formData.bid = detail.bid
    formData.years = detail.years || ''
    formData.btitle = stripBookMarks(detail.btitle)
    formData.author = detail.author || ''
    formData.original_title = detail.original_title || ''
    formData.btype = detail.btype || ''
    formData.status = detail.status || ''
    formData.recommend = detail.recommend ?? 3
    formData.reading_depth = detail.reading_depth || 3
    formData.readDate = detail.readDate || ''
    formData.openop = detail.openop || ''
    formData.closedop = detail.closedop || ''
    formData.action_item = detail.action_item || ''
    formData.abandon_reason = detail.abandon_reason || ''
    formData.tags = ensureArray(detail.tags)
    dialogVisible.value = true
  } catch {
    ElMessage.error('获取书籍详情失败')
  }
}

function ensureArray(value: unknown): string[] {
  if (Array.isArray(value)) return value
  if (typeof value === 'string') return value ? value.split(',') : []
  return []
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    try {
      const data: Record<string, unknown> = {
        years: formData.years,
        btitle: stripBookMarks(formData.btitle),
        btype: formData.btype,
        status: formData.status,
        recommend: formData.recommend,
        reading_depth: Number(formData.reading_depth),
        readDate: formData.readDate || null,
      }
      if (formData.author?.trim()) data.author = formData.author.trim()
      if (formData.original_title?.trim()) data.original_title = formData.original_title.trim()
      if (formData.openop) data.openop = formData.openop
      if (formData.closedop) data.closedop = formData.closedop
      if (formData.status === 'abandoned' && formData.abandon_reason) data.abandon_reason = formData.abandon_reason
      if (formData.tags.length) data.tags = formData.tags.join(',')

      if (dialogType.value === 'create') {
        await bookStore.createNewBook(data)
        ElMessage.success('创建成功')
      } else if (formData.bid) {
        await bookStore.updateExistingBook(formData.bid, data)
        ElMessage.success('更新成功')
      }

      // 「值得留下」→ 作品库（v3.62.0）。🔴 **单独 try**：附加标记，失败不阻断保存。
      // ⚠️ 只在**编辑已有书**时打勾：新建那一路拿不到新书的 `bid`，
      //    而捕获必须带 `source_id`（拿不到就宁可不记，也不记一条指错的）。
      if (formData.keepIt && formData.status === 'finished' && formData.bid) {
        try {
          await captureWork({
            source_type: 'book',
            source_id: formData.bid,
            title: formData.btitle,
            excerpt: (formData.action_item || '').slice(0, 300),
          })
        } catch {
          ElMessage.warning('已保存；「值得留下」没记上（作品库可能还没就绪）')
        }
      }

      dialogVisible.value = false
      await fetchData(); await fetchStats()
    } catch {
      ElMessage.error('操作失败')
    }
  })
}

async function handleDelete(row: Book) {
  try {
    await ElMessageBox.confirm(`确定要删除${formatBookTitle(row.btitle)}吗？`, '提示', { type: 'warning' })
    await bookStore.deleteExistingBook(row.bid)
    ElMessage.success('删除成功')
    await fetchData(); await fetchStats()
  } catch (error) { if (error !== 'cancel') ElMessage.error('删除失败') }
}

function handleDialogClose() { formRef.value?.resetFields() }

function handleSizeChange(val: number) { pageSize.value = val; currentPage.value = 1; fetchData() }
function handleCurrentChange(page: number) { currentPage.value = page; fetchData() }
function refreshData() { fetchData(); fetchStats(); ElMessage.success('数据已刷新') }

// ── 标签（预设 + 自定义，预设来自「系统预设管理 → 图书预设标签」，交互同日记流） ──
const presetTags = ref<string[]>([])
const showTagInput = ref(false)
const newTag = ref('')
const tagInputRef = ref()

const customTags = computed(() => formData.tags.filter(t => !presetTags.value.includes(t)))

async function loadPresetTags() {
  try {
    const res = await getPresetByType('book_tags')
    presetTags.value = res.data.values || []
  } catch {
    presetTags.value = []
  }
}

function togglePresetTag(tag: string) {
  const idx = formData.tags.indexOf(tag)
  if (idx > -1) {
    formData.tags.splice(idx, 1)
  } else {
    formData.tags.push(tag)
  }
}

function addTag() {
  const tag = newTag.value.trim()
  if (tag && !formData.tags.includes(tag)) formData.tags.push(tag)
  newTag.value = ''
  showTagInput.value = false
}

function removeTag(tag: string) {
  formData.tags = formData.tags.filter(t => t !== tag)
}

function openTagInput() {
  showTagInput.value = true
  nextTick(() => tagInputRef.value?.focus())
}

onMounted(() => { fetchData(); fetchStats(); loadPresetTags(); fetchFocus() })
</script>

<style scoped lang="scss">
.book-view {
  padding: 20px;
  background-color: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  .header-left { display: flex; align-items: center; gap: 12px;
    .page-title { margin: 0; font-size: 24px; font-weight: 600; color: var(--el-text-color-primary); }
    .module-tag { font-size: 12px; }
  }
  .header-actions { display: flex; gap: 12px; }
}

.stats-section { margin-bottom: 24px;
  .stat-card {
    :deep(.el-card__body) { padding: 20px; }
    .stat-content { display: flex; align-items: center; gap: 16px;
      .stat-icon { width: 48px; height: 48px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
      .stat-info {
        .stat-value { font-size: 24px; font-weight: 600; line-height: 1; color: var(--el-text-color-primary); margin-bottom: 4px; }
        .stat-label { font-size: 14px; color: var(--el-text-color-regular); }
      }
    }
  }
}

.filter-card { margin-bottom: 20px;
  :deep(.el-card__body) { padding: 20px; }
  .filter-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;
    .search-section { flex: 1; min-width: 250px; .search-input { width: 100%; } }
    .filter-section { display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
      .filter-select { width: 130px; }
      .reset-btn { margin-left: 8px; }
    }
  }
}

/* 批量工具条（选中行后才出现）—— 和筛选卡分开，两者量的不是同一类东西 */
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 16px;
  margin-bottom: 16px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: var(--el-border-radius-base);
  background: var(--el-color-primary-light-9);

  .bulk-count {
    font-size: 13px;
    color: var(--el-text-color-regular);
    b { margin: 0 2px; font-size: 16px; color: var(--el-color-primary); }
  }
}

.table-card {
  :deep(.el-card__body) { padding: 20px; }
  .recommend-stars { display: inline-flex; gap: 2px;
    .star { color: #d4d4d8; font-size: 14px; &.active { color: #f5a623; } }
  }
  .pagination-container { margin-top: 20px; display: flex; justify-content: flex-end; }
}

.book-form { max-height: 70vh; overflow-y: auto; padding-right: 12px;
  .form-section { margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--el-border-color-light);
    .section-title { margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: var(--el-color-primary); }
  }
}

.dialog-footer { display: flex; justify-content: flex-end; gap: 12px; }

.field-hint {
  width: 100%;
  margin-top: 2px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  line-height: 1.4;
}

@media (max-width: 768px) {
  .page-header { flex-direction: column; align-items: stretch; gap: 16px; }
  .stats-section .el-row { flex-direction: column; .el-col { width: 100%; margin-bottom: 16px; } }
  .filter-card .filter-header { flex-direction: column; align-items: stretch; }
}

/* 标签点选（样式同日记流） */
.tags-wrapper {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.preset-label {
  font-size: 12px;
  color: #999;
  flex-shrink: 0;
}

.preset-tag {
  cursor: pointer;
  transition: all 0.2s;

  &:hover { opacity: 0.8; }

  &.selected {
    background: #ecf5ff;
    border-color: #409eff;
    color: #409eff;
  }
}

.custom-tags {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.tags-hint {
  width: 100%;
  margin-top: 4px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  line-height: 1.4;
}
/* 「值得留下」那一行（只在状态 = 已读完时出现） */
.keep-row { display: flex; align-items: center; gap: 6px; }
.keep-icon {
  color: var(--el-text-color-secondary); cursor: help;
  border-bottom: 1px dashed var(--el-border-color);
}
.keep-icon:hover { color: var(--el-color-primary); }
.keep-tip { max-width: 330px; font-size: 12px; line-height: 1.8; }
.keep-tip p { margin: 0 0 6px; }
.keep-tip p:last-child { margin-bottom: 0; }

/* ── 一本书闸门（v3.65.x）────────────────────────────────── */
.focus-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 18px;
  margin-bottom: 16px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-left: 3px solid var(--el-color-primary);
  border-radius: 6px;

  /* 空态用虚线：一眼能看出「这里本来就该有东西，只是还没指定」，
     而不是「系统出错了 / 这条没加载出来」 */
  &.is-empty {
    border-left-style: dashed;
    border-left-color: var(--el-border-color);
  }
}

.focus-main {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
  flex-wrap: wrap;
}

.focus-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  letter-spacing: 1px;
  flex: none;
}

.focus-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 420px;
}

.focus-author {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.focus-status { flex: none; }

.focus-days {
  font-size: 13px;
  color: var(--el-color-primary);
  font-variant-numeric: tabular-nums;
}

.focus-empty {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.switch-current {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 18px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
.switch-current-label { font-size: 12px; color: var(--el-text-color-secondary); }
.switch-current-title { font-size: 14px; font-weight: 600; }
.switch-current-days { font-size: 12px; color: var(--el-color-primary); }

.switch-field-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}

.switch-modes { margin-bottom: 8px; }

.switch-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  margin-bottom: 8px;
}

.switch-reason { margin-bottom: 8px; }

.switch-select { width: 100%; margin-bottom: 6px; }
</style>

<!-- el-select 的下拉默认 teleport 到 body，scoped 样式够不到它 ⇒
     用 popper-class 命名空间隔离，只影响这个弹窗的下拉。
     ⚠️ 选项内容必须用 flex + 各自 ellipsis：作者名一长（如「（俄罗斯）玛丽亚·斯捷潘诺娃」），
     `float:right` 会把「· 在读」挤到第二行，看着像状态另起一栏。 -->
<style>
.focus-switch-popper .switch-option-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.focus-switch-popper .switch-option-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.focus-switch-popper .switch-option-meta {
  flex: none;
  max-width: 52%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
