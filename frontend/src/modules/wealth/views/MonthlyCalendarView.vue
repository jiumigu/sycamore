<template>
  <div class="monthly">
    <div class="monthly__toolbar">
      <el-button size="small" @click="showImportDialog = true">
        <el-icon><Upload /></el-icon>
        导入CSV
      </el-button>
    </div>

    <CalendarHeader
      :year="store.currentYear"
      :month="store.currentMonth"
      :view-mode="store.viewMode"
      @navigate="store.navigateMonth"
      @today="store.goToToday"
      @update:year="store.goToYearMonth($event, store.currentMonth)"
      @update:month="store.goToYearMonth(store.currentYear, $event)"
    />

    <div v-if="store.monthlyLoading" class="monthly__loading">
      <el-skeleton :rows="6" animated />
    </div>

    <template v-else>
      <CalendarGrid
        :days="store.monthlyDays"
        :year="store.currentYear"
        :month="store.currentMonth"
        :selected-date="store.selectedDate"
        @select="handleDaySelect"
      />
    </template>

    <StatsFooter :summary="store.monthlySummary" />

    <!-- 单日明细弹窗 -->
    <DayDetailModal
      :visible="detailVisible"
      :loading="store.dailyDetailLoading"
      :detail="store.currentDailyDetail"
      :date-str="store.selectedDate"
      @close="handleDetailClose"
      @submit-bill="handleBillSubmit"
    />

    <!-- CSV 导入弹窗 -->
    <el-dialog v-model="showImportDialog" title="导入随手记CSV" width="450px" @close="handleImportClose">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        accept=".csv"
        drag
        :limit="1"
        :on-change="handleFileChange"
        :on-exceed="handleExceed"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">将随手记导出的 CSV 文件拖到此处</div>
        <template #tip>
          <div class="upload-tip">支持随手记导出的账单 CSV 格式</div>
        </template>
      </el-upload>

      <div v-if="importResult" class="import-result">
        <el-alert
          :type="importResult.created > 0 ? 'success' : 'warning'"
          show-icon
        >
          <template #title>
            <div>导入完成：成功 {{ importResult.created }} 条<template v-if="importResult.duplicated">，重复 {{ importResult.duplicated }} 条（已忽略）</template><template v-if="importResult.skipped">，跳过 {{ importResult.skipped }} 条</template></div>
          </template>
        </el-alert>
        <div v-if="importResult.errors?.length" class="import-errors">
          <div v-for="err in importResult.errors" :key="err" class="import-error-item">{{ err }}</div>
        </div>
      </div>

      <template #footer>
        <el-button @click="showImportDialog = false">关闭</el-button>
        <el-button type="primary" :loading="importing" @click="handleImportUpload">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, UploadFilled } from '@element-plus/icons-vue'
import { useWealthStore } from '../stores/wealthStore'
import CalendarHeader from '../components/monthly/CalendarHeader.vue'
import CalendarGrid from '../components/monthly/CalendarGrid.vue'
import StatsFooter from '../components/monthly/StatsFooter.vue'
import DayDetailModal from '../components/monthly/DayDetailModal.vue'
import { importCSV } from '../api/wealthApi'
import type { BillCreateData } from '../types/wealthTypes'

const store = useWealthStore()
const detailVisible = ref(false)
const showImportDialog = ref(false)
const importing = ref(false)
const uploadRef = ref()
const selectedFile = ref<File | null>(null)
const importResult = ref<{
  created: number
  skipped: number
  duplicated: number
  total: number
  errors?: string[]
} | null>(null)

async function handleDaySelect(dateStr: string) {
  await store.selectDate(dateStr)
  detailVisible.value = true
}

function handleDetailClose() {
  detailVisible.value = false
}

async function handleBillSubmit(data: BillCreateData) {
  await store.createBill(data)
}

function handleFileChange(file: { raw: File }) {
  selectedFile.value = file.raw
  importResult.value = null
}

function handleExceed() {
  ElMessage.warning('只能选择一个文件')
}

async function handleImportUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importing.value = true
  try {
    const res = await importCSV(selectedFile.value)
    importResult.value = res.data
    if (res.data.created > 0) {
      ElMessage.success(`成功导入 ${res.data.created} 条`)
      store.fetchMonthlyData()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '导入失败')
  } finally {
    importing.value = false
  }
}

function handleImportClose() {
  selectedFile.value = null
  importResult.value = null
}

onMounted(() => {
  if (store.monthlyDays.length === 0) {
    store.fetchMonthlyData()
  }
})
</script>

<style scoped lang="scss">
.monthly {
  padding: 24px;
  max-width: 1200px;

  &__toolbar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 8px;
  }

  &__loading {
    padding: 24px;
    background: #fff;
    border-radius: 8px;
  }
}

.upload-icon { font-size: 48px; color: #c0c4cc; margin-bottom: 8px; }
.upload-text { color: #606266; font-size: 14px; }
.upload-tip { margin-top: 8px; font-size: 12px; color: #999; }
.import-result { margin-top: 16px; }
.import-errors { margin-top: 8px; max-height: 120px; overflow-y: auto; }
.import-error-item { font-size: 12px; color: #e6a23c; padding: 2px 0; }
</style>
