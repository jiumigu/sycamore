<template>
  <div class="tool-detail">
    <div class="back-bar">
      <el-button text @click="$router.push('/toolkit')">
        <el-icon><ArrowLeft /></el-icon> 返回工具集
      </el-button>
      <el-button v-if="isExecutionTool" class="history-link" text @click="$router.push('/toolkit/history')">
        <el-icon><Timer /></el-icon> 执行历史
      </el-button>
    </div>
    <div v-loading="loading">
      <!-- 独立组件（页面标题由各自组件提供） -->
      <TravelRoute v-if="toolKey === 'travel-route'" />
      <EnvironmentAudit v-else-if="toolKey === 'environment-audit'" />
      <CareerEnergyAudit v-else-if="toolKey === 'career-energy-audit'" />
      <HealthSelfCheck v-else-if="toolKey === 'health-self-check'" />
      <FinanceCalculators v-else-if="toolKey === 'finance-calculators'" />
      <ReviewToolbox v-else-if="toolKey === 'review-toolbox'" />
      <GifCompressor v-else-if="toolKey === 'gif-compressor'" />
      <ElectricityRecord v-else-if="toolKey === 'electricity-record'" />

      <!-- 执行区 -->
      <template v-else>
      <div class="tool-page-head" v-if="tool">
        <h2 class="page-title">{{ tool.name }}</h2>
        <p class="subtitle">{{ tool.description }}</p>
      </div>
      <el-row :gutter="16">
        <el-col :span="result && result.success ? 14 : 24">
          <!-- 参数表单 -->
          <el-card class="section-card" v-if="tool">
            <template #header><span>⚙️ 参数设置</span></template>

            <!-- 文件上传（繁简转换） -->
            <div v-if="isTrad2Simp" class="file-convert-area">
              <div class="file-upload-zone">
                <el-upload
                  ref="fileUploadRef"
                  :auto-upload="false"
                  accept=".txt"
                  :limit="1"
                  :on-change="handleFileChange"
                  :on-exceed="() => ElMessage.warning('仅支持上传单个文件')"
                  drag
                >
                  <el-icon class="upload-icon"><UploadFilled /></el-icon>
                  <div class="upload-text">将 .txt 文件拖到此处，或点击上传</div>
                  <template #tip>
                    <div class="upload-hint">仅支持 UTF-8 编码的 .txt 文件</div>
                  </template>
                </el-upload>
                <div v-if="selectedFile" class="file-selected">
                  <el-icon><Document /></el-icon>
                  <span>{{ selectedFile.name }}</span>
                  <el-button size="small" text type="danger" @click="selectedFile = null">移除</el-button>
                </div>
              </div>

              <div class="mode-section">
                <span class="mode-label">转换方向：</span>
                <el-radio-group v-model="convertMode">
                  <el-radio value="t2s">繁体 → 简体</el-radio>
                  <el-radio value="s2t">简体 → 繁体</el-radio>
                </el-radio-group>
              </div>

              <div class="form-actions">
                <el-button type="primary" :loading="store.executing" @click="handleFileConvert">
                  <el-icon><CaretRight /></el-icon> {{ store.executing ? '转换中...' : '开始转换' }}
                </el-button>
                <el-button @click="resetConvert">重置</el-button>
              </div>
            </div>

            <!-- 动态表单（通用） -->
            <template v-else>
              <el-form :model="formData" label-width="100px" class="tool-form">
                <template v-for="(prop, key) in formFields" :key="key">
                  <el-form-item v-if="prop.type === 'integer' || prop.type === 'number'" :label="prop.description || key">
                    <el-slider
                      v-if="key === 'fps' || key === 'quality'"
                      v-model="formData[key]"
                      :min="prop.minimum || 0"
                      :max="prop.maximum || 100"
                      :step="1"
                      show-input
                    />
                    <el-input-number v-else v-model="formData[key]" :min="prop.minimum" :max="prop.maximum" style="width:100%" />
                  </el-form-item>
                  <el-form-item v-else-if="prop.type === 'string'" :label="prop.description || key">
                    <el-select v-if="prop.enum" v-model="formData[key]" style="width:100%">
                      <el-option v-for="opt in prop.enum" :key="opt" :label="enumLabel(key, opt)" :value="opt" />
                    </el-select>
                    <el-input v-else v-model="formData[key]" :placeholder="'请输入' + (prop.description || key)" />
                  </el-form-item>
                </template>
              </el-form>
              <div class="form-actions">
                <el-button type="primary" :loading="store.executing" @click="handleExecute">
                  <el-icon><CaretRight /></el-icon> {{ store.executing ? '执行中...' : '开始执行' }}
                </el-button>
                <el-button @click="resetForm">重置</el-button>
              </div>
            </template>
          </el-card>
        </el-col>

        <!-- 结果区 -->
        <el-col :span="10" v-if="result && result.success">
          <el-card class="section-card result-card">
            <template #header><span>✅ 执行结果</span></template>

            <!-- 进度 -->
            <div v-if="store.progress < 100" class="progress-area">
              <el-progress :percentage="store.progress" :stroke-width="12" />
              <div class="progress-text">{{ tool?.name }} 处理中...</div>
            </div>

            <!-- 文本结果 -->
            <div v-if="result.output_text" class="result-text">
              <el-input type="textarea" :rows="12" :model-value="result.output_text" readonly />
              <el-button class="copy-btn" size="small" @click="copyResult(result.output_text!)">
                <el-icon><CopyDocument /></el-icon> 复制
              </el-button>
            </div>

            <!-- 文件结果下载 -->
            <div v-if="result.output_file" class="result-file">
              <div class="file-preview">
                <span class="file-icon">📄</span>
                <span>{{ resultFilename }}</span>
              </div>
              <div v-if="result.preview" class="preview-box">
                <div class="preview-label">内容预览</div>
                <div class="preview-content">{{ result.preview }}</div>
              </div>
              <el-button type="primary" class="download-btn" @click="downloadFile(result.output_file!)">
                <el-icon><Download /></el-icon> 下载文件
              </el-button>
            </div>

            <!-- 统计信息 -->
            <div v-if="result.stats" class="result-stats">
              <div class="stats-title">📊 统计信息</div>
              <div class="stats-grid">
                <div v-for="(v, k) in result.stats" :key="k" class="stat-cell">
                  <div class="stat-value">{{ formatStat(v) }}</div>
                  <div class="stat-label">{{ statLabel(k) }}</div>
                </div>
              </div>
            </div>

            <el-button v-if="result.success" class="regen-btn" @click="resetExecution">
              <el-icon><Refresh /></el-icon> 重新生成
            </el-button>
          </el-card>
        </el-col>
      </el-row>

      <!-- 错误提示 -->
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="true" @close="errorMsg = ''" class="error-alert" />
    </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, CaretRight, Download, CopyDocument, Refresh, Timer, UploadFilled, Document } from '@element-plus/icons-vue'
import { useToolkitStore } from '../stores/toolkitStore'
import type { ToolDefinition, SchemaProperty } from '../types/toolkitTypes'
import TravelRoute from './tools/TravelRoute.vue'
import EnvironmentAudit from './tools/EnvironmentAudit.vue'
import CareerEnergyAudit from './tools/CareerEnergyAudit.vue'
import HealthSelfCheck from './tools/HealthSelfCheck.vue'
import FinanceCalculators from './FinanceCalculators.vue'
import ReviewToolbox from './tools/ReviewToolbox.vue'
import GifCompressor from './tools/GifCompressor.vue'
import ElectricityRecord from './tools/ElectricityRecord.vue'

const route = useRoute()
const store = useToolkitStore()
const toolKey = computed(() => route.params.toolKey as string)

const tool = ref<ToolDefinition | null>(null)
const loading = ref(false)
const errorMsg = ref('')
const fileUploadRef = ref()
const formData = ref<Record<string, any>>({})

const selectedFile = ref<File | null>(null)
const convertMode = ref('t2s')

const result = computed(() => store.executionResult)

const resultFilename = computed(() => {
  const f = store.executionResult?.filename || ''
  if (f) return f
  const p = store.executionResult?.output_file || ''
  return p ? p.split('/').pop() || '转换后文件' : '转换后文件'
})
const isTrad2Simp = computed(() => tool.value?.tool_key === 'trad2simp')

// 数据型工具：历史在各页自身数据表、页面底部有自己的历史列表，不走"执行历史"页；
// 其余（gif-compressor / trad2simp 及通用表单工具）为执行型，执行记录进"执行历史"页
const DATA_TOOL_KEYS = new Set([
  'travel-route', 'environment-audit', 'career-energy-audit', 'health-self-check',
  'free-spending', 'review-toolbox', 'fixed-expense', 'electricity-record',
  'finance-calculators',
])
const isExecutionTool = computed(() => !DATA_TOOL_KEYS.has(toolKey.value))

const formFields = computed(() => {
  if (!tool.value?.input_schema?.properties) return {}
  const props: Record<string, SchemaProperty> = {}
  for (const [key, prop] of Object.entries(tool.value.input_schema.properties)) {
    if (key === 'images') continue
    if (key === 'file') continue
    props[key] = prop as SchemaProperty
  }
  return props
})

function enumLabel(key: string, val: string): string {
  if (key === 'mode') {
    return val === 't2s' ? '繁体 → 简体' : '简体 → 繁体'
  }
  return val
}

function statLabel(key: string): string {
  const labels: Record<string, string> = {
    frame_count: '帧数',
    duration_ms: '时长(ms)',
    file_size: '文件大小',
    dimensions: '尺寸',
    original_size: '原始大小',
    converted_size: '转换后大小',
    changed_chars: '变更字符',
    mode_label: '转换方向',
  }
  return labels[key] || key
}

function formatStat(v: unknown): string {
  if (v === null || v === undefined) return '-'
  if (typeof v === 'number' && v > 1024) return (v / 1024).toFixed(1) + 'KB'
  return String(v)
}

function buildFormData() {
  return { ...formData.value }
}

// 通用执行
async function handleExecute() {
  errorMsg.value = ''
  store.resetExecution()
  try {
    await store.runTool(toolKey.value, buildFormData())
    if (!store.executionResult?.success && store.executionStatus === 'failed') {
      errorMsg.value = '工具执行失败'
    }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.error || e?.response?.data?.detail || e?.message || '执行失败'
  }
}

// 繁简转换：文件上传执行
function handleFileChange(file: any) {
  selectedFile.value = file.raw
}

async function handleFileConvert() {
  if (!selectedFile.value) {
    ElMessage.warning('请先上传文件')
    return
  }
  errorMsg.value = ''
  store.resetExecution()
  try {
    await store.runFileTool(toolKey.value, selectedFile.value, { mode: convertMode.value })
    if (!store.executionResult?.success && store.executionStatus === 'failed') {
      errorMsg.value = '转换失败'
    }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.error || '转换失败'
  }
}

function resetConvert() {
  selectedFile.value = null
  convertMode.value = 't2s'
  store.resetExecution()
}

function downloadFile(path: string) {
  // 服务器绝对路径 → 相对 MEDIA_ROOT → 后端下载端点（浏览器无法直接访问本地路径）
  const mediaIdx = path.indexOf('/media/')
  const rel = mediaIdx > -1 ? path.slice(mediaIdx + '/media/'.length) : path
  window.open(`/api/toolkit/files/${rel}`, '_blank')
}

function copyResult(text: string) {
  navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制'))
}

function resetForm() {
  formData.value = getDefaultFormData()
}

function resetExecution() {
  store.resetExecution()
}

function getDefaultFormData(): Record<string, any> {
  const data: Record<string, any> = {}
  if (!tool.value?.input_schema?.properties) return data
  for (const [key, prop] of Object.entries(tool.value.input_schema.properties)) {
    const p = prop as SchemaProperty
    if (key === 'images' || key === 'file') continue
    data[key] = p.default ?? (p.type === 'integer' ? 0 : p.type === 'string' && p.enum ? p.enum[0] : '')
  }
  return data
}

onMounted(async () => {
  loading.value = true
  try {
    if (toolKey.value === 'finance-calculators') {
      // 聚合工具：无独立后端详情，直接渲染聚合页（FinanceCalculators）
      return
    }
    const t = await store.fetchToolDetail(toolKey.value)
    tool.value = t
    formData.value = getDefaultFormData()
  } catch {
    errorMsg.value = '工具不存在或加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="scss">
.tool-detail {
  padding: 20px; background: #F5F7FA; min-height: 100vh;

  .back-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; flex-wrap: nowrap;
    .history-link { margin-left: auto; }
  }

  .section-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px;
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
  }

  .tool-page-head {
    margin-bottom: 16px;
    .page-title { margin: 0; font-size: 20px; font-weight: 700; color: #1F2937; }
    .subtitle { margin: 4px 0 0; font-size: 13px; color: #6B7280; }
  }

  .upload-area { margin-bottom: 20px;
    :deep(.el-upload--picture-card) { width: 100px; height: 100px; line-height: 100px; }
    :deep(.el-upload-list--picture-card) { .el-upload-list__item { width: 100px; height: 100px; } }
    .upload-hint { font-size: 12px; color: #9CA3AF; margin-top: 8px; }
  }

  .file-convert-area {
    .file-upload-zone {
      margin-bottom: 20px;

      :deep(.el-upload-dragger) {
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        padding: 30px 20px; width: 100%;
      }

      .upload-icon { font-size: 48px; color: #7C3AED; margin-bottom: 12px; }
      .upload-text { font-size: 14px; color: #6B7280; margin-bottom: 8px; }
      .upload-hint { font-size: 12px; color: #9CA3AF; }

      .file-selected {
        display: flex; align-items: center; gap: 8px;
        margin-top: 12px; padding: 10px 16px;
        background: #f5f3ff; border-radius: 8px;
        font-size: 14px; color: #374151;
      }
    }

    .mode-section {
      display: flex; align-items: center; gap: 16px; margin-bottom: 20px;
      .mode-label { font-size: 14px; font-weight: 500; color: #374151; }
    }
  }

  .tool-form {
    max-width: 600px;
    :deep(.el-form-item__label) { font-size: 13px; color: #374151; }
  }

  .form-actions { display: flex; gap: 12px; margin-top: 20px; padding-top: 16px; border-top: 1px solid #f0f0f0; }

  .result-card {
    .progress-area { text-align: center; padding: 20px 0;
      .progress-text { margin-top: 12px; font-size: 13px; color: #6B7280; }
    }

    .result-text { position: relative;
      .copy-btn { margin-top: 8px; }
    }

    .result-file { text-align: center; padding: 16px 0;
      .file-preview { font-size: 16px; margin-bottom: 12px; display: flex; align-items: center; justify-content: center; gap: 8px; }
      .preview-box { text-align: left; margin-bottom: 16px;
        .preview-label { font-size: 12px; color: #9CA3AF; margin-bottom: 4px; }
        .preview-content { font-size: 13px; color: #374151; line-height: 1.6; background: #f9fafb; padding: 12px; border-radius: 6px; max-height: 150px; overflow-y: auto; }
      }
      .download-btn { width: 100%; }
    }

    .result-stats { margin-top: 16px; padding-top: 12px; border-top: 1px solid #f0f0f0;
      .stats-title { font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 8px; }
      .stats-grid { display: flex; flex-wrap: wrap; gap: 12px;
        .stat-cell { flex: 1; min-width: 80px; text-align: center;
          .stat-value { font-size: 16px; font-weight: 600; color: #1F2937; }
          .stat-label { font-size: 11px; color: #9CA3AF; }
        }
      }
    }

    .regen-btn { margin-top: 16px; width: 100%; }
  }

  .error-alert { margin-bottom: 16px; }
}
</style>
