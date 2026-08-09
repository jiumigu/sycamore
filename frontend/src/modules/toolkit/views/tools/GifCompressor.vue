<template>
  <div class="gif-compressor">
    <el-row :gutter="16">
      <el-col :span="result ? 14 : 24">
        <el-card class="section-card">
          <template #header><span>🎞️ 参数设置</span></template>

          <div class="upload-zone">
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              accept=".gif"
              drag
              :limit="1"
              :on-change="handleFileChange"
              :on-exceed="() => ElMessage.warning('仅支持上传单个文件')"
              :on-remove="() => { selectedFile = null; store.resetExecution() }"
            >
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="upload-text">将 GIF 文件拖到此处，或点击上传</div>
              <template #tip>
                <div class="upload-hint">仅支持 .gif 格式</div>
              </template>
            </el-upload>
            <div v-if="selectedFile" class="file-selected">
              <el-icon><Document /></el-icon>
              <span>{{ selectedFile.name }}</span>
              <el-button size="small" text type="danger" @click="removeFile">移除</el-button>
            </div>
          </div>

          <el-form :model="config" label-width="110px" class="config-form">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="抽帧间隔">
                  <el-input-number v-model="config.frame_skip" :min="1" :max="10" style="width: 100%" />
                  <span class="hint">每隔 N 帧保留 1 帧</span>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="颜色数">
                  <el-select v-model="config.colors" style="width: 100%">
                    <el-option :value="256" label="256 色（标准）" />
                    <el-option :value="128" label="128 色" />
                    <el-option :value="64" label="64 色" />
                    <el-option :value="32" label="32 色（小文件）" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="压缩质量">
              <el-slider v-model="config.quality" :min="10" :max="100" show-input />
              <span class="hint">值越小体积越小</span>
            </el-form-item>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="缩放比例">
                  <el-select v-model="config.scale" style="width: 100%">
                    <el-option :value="1.0" label="原始尺寸" />
                    <el-option :value="0.75" label="75%" />
                    <el-option :value="0.5" label="50%" />
                    <el-option :value="0.25" label="25%" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="指定尺寸">
                  <div class="size-row">
                    <el-input-number v-model="config.width" :min="0" :max="1920" placeholder="宽" controls-position="right" />
                    <span class="size-x">×</span>
                    <el-input-number v-model="config.height" :min="0" :max="1920" placeholder="高" controls-position="right" />
                  </div>
                  <span class="hint">px，0 = 不限制</span>
                </el-form-item>
              </el-col>
            </el-row>

            <div class="form-actions">
              <el-button type="primary" :loading="store.executing" :disabled="!selectedFile" @click="compress">
                <el-icon><CaretRight /></el-icon> {{ store.executing ? '压缩中...' : '开始压缩' }}
              </el-button>
              <el-button @click="resetForm">重置</el-button>
            </div>
          </el-form>
        </el-card>
      </el-col>

      <!-- 结果区 -->
      <el-col :span="10" v-if="result">
        <el-card class="section-card result-card">
          <template #header><span>✅ 压缩结果</span></template>

          <div class="preview-box">
            <el-image
              :src="result.output_file"
              fit="contain"
              class="preview-img"
              :preview-src-list="[result.output_file]"
            />
          </div>

          <div class="result-grid">
            <div class="result-item">
              <div class="result-label">原始大小</div>
              <div class="result-value">{{ stats.original_size }}</div>
            </div>
            <div class="result-item">
              <div class="result-label">压缩后</div>
              <div class="result-value accent">{{ stats.compressed_size }}</div>
            </div>
            <div class="result-item">
              <div class="result-label">压缩率</div>
              <div class="result-value" :class="ratioClass">{{ stats.ratio }}</div>
            </div>
            <div class="result-item">
              <div class="result-label">帧数</div>
              <div class="result-value">{{ stats.frames_before }} → {{ stats.frames_after }}</div>
            </div>
          </div>

          <el-button type="primary" class="download-btn" @click="download">
            <el-icon><Download /></el-icon> 下载压缩文件
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { CaretRight, Download, UploadFilled, Document } from '@element-plus/icons-vue'
import { useToolkitStore } from '../../stores/toolkitStore'

interface CompressStats {
  original_size: string
  compressed_size: string
  ratio: string
  frames_before: number
  frames_after: number
}

const store = useToolkitStore()

const uploadRef = ref()
const selectedFile = ref<File | null>(null)
const config = reactive({
  frame_skip: 1,
  quality: 75,
  scale: 1.0,
  width: 0,
  height: 0,
  colors: 256,
})

const result = computed(() => (store.executionResult?.success ? store.executionResult : null))

const stats = computed<CompressStats>(() => (result.value?.stats || {}) as unknown as CompressStats)

const ratioClass = computed(() => {
  const pct = parseFloat(stats.value.ratio)
  if (Number.isNaN(pct)) return ''
  if (pct >= 60) return 'good'
  if (pct >= 30) return 'mid'
  return 'low'
})

function handleFileChange(file: any) {
  selectedFile.value = file.raw
}

function removeFile() {
  selectedFile.value = null
  uploadRef.value?.clearFiles()
  store.resetExecution()
}

async function compress() {
  if (!selectedFile.value) {
    ElMessage.warning('请先上传 GIF 文件')
    return
  }
  store.resetExecution()
  try {
    await store.runFileTool('gif-compressor', selectedFile.value, { ...config })
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '压缩失败')
  }
}

function download() {
  if (!result.value?.output_file) return
  const a = document.createElement('a')
  a.href = result.value.output_file
  a.download = result.value.filename || result.value.output_file.split('/').pop() || 'compressed.gif'
  a.click()
}

function resetForm() {
  selectedFile.value = null
  config.frame_skip = 1
  config.quality = 75
  config.scale = 1.0
  config.width = 0
  config.height = 0
  config.colors = 256
  store.resetExecution()
}
</script>

<style scoped lang="scss">
.gif-compressor {
  padding: 0;

  .section-card {
    border: none;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    margin-bottom: 18px;

    :deep(.el-card__header) {
      padding: 14px 20px;
      font-size: 14px;
      font-weight: 500;
      border-bottom: 1px solid #f2f2f2;
    }
  }

  .upload-zone {
    margin-bottom: 24px;

    :deep(.el-upload-dragger) {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 30px 20px;
      width: 100%;
    }

    .upload-icon { font-size: 48px; color: #409EFF; margin-bottom: 12px; }
    .upload-text { font-size: 14px; color: #6B7280; margin-bottom: 8px; }
    .upload-hint { font-size: 12px; color: #9CA3AF; }

    .file-selected {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 12px;
      padding: 10px 16px;
      background: #ecf5ff;
      border-radius: 8px;
      font-size: 14px;
      color: #374151;
    }
  }

  .config-form {
    .hint {
      display: block;
      font-size: 12px;
      color: #9CA3AF;
      margin-top: 2px;
    }

    .size-row {
      display: flex;
      align-items: center;
      gap: 6px;
      width: 100%;

      .el-input-number { flex: 1; }
      .size-x { color: #9CA3AF; flex-shrink: 0; }
    }
  }

  .form-actions {
    display: flex;
    gap: 12px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #f0f0f0;
  }

  .result-card {
    .preview-box {
      text-align: center;
      padding: 12px 0;

      .preview-img {
        max-width: 100%;
        max-height: 220px;
        border-radius: 8px;
        background: #f5f7fa;
      }
    }

    .result-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin: 12px 0;

      .result-item {
        text-align: center;
        padding: 10px 0;
        background: #f9fafb;
        border-radius: 8px;

        .result-label {
          font-size: 11px;
          color: #9CA3AF;
          margin-bottom: 4px;
        }

        .result-value {
          font-size: 16px;
          font-weight: 600;
          color: #1F2937;

          &.accent { color: #67C23A; }
          &.good { color: #67C23A; }
          &.mid { color: #E6A23C; }
          &.low { color: #909399; }
        }
      }
    }

    .download-btn { width: 100%; }
  }
}
</style>
