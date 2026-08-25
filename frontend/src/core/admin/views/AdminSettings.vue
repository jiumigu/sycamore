<template>
  <div class="admin-settings">
    <div class="page-header">
      <h1 class="page-title">系统设置</h1>
    </div>

    <el-card class="settings-card">
      <template #header>
        <span>Logseq 集成配置</span>
      </template>

      <el-form label-width="140px" label-position="left">
        <el-form-item label="Logseq 日记目录">
          <el-input
            v-model="profile.logseq_path"
            placeholder="如：/Users/syca/logseq/journals"
            clearable
          />
          <div class="form-hint">配置后，日记流中可直接打开 Logseq 源文件</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">
            保存配置
          </el-button>
          <el-button v-if="saved" type="success" plain>已保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="settings-card">
      <template #header>
        <span>隐私模式</span>
      </template>

      <el-form label-width="140px" label-position="left">
        <el-form-item label="脱敏模式">
          <el-switch v-model="profile.privacy_mode" />
          <div class="form-hint">开启后，敏感数据将以 *** 显示</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">
            保存配置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="settings-card">
      <template #header>
        <span>Obsidian 集成配置</span>
      </template>

      <el-form label-width="140px" label-position="left">
        <el-form-item label="启用集成">
          <el-switch v-model="obsidian.enabled" />
          <div class="form-hint">启用后，「人生样本」模块可读取 Obsidian 仓库中的样本文件</div>
        </el-form-item>

        <el-form-item label="仓库路径">
          <el-input
            v-model="obsidian.vault_path"
            placeholder="如：/Users/syca/Documents/ObsidianVault"
            clearable
          />
          <div class="form-hint">Obsidian 仓库根目录的绝对路径</div>
        </el-form-item>

        <el-form-item label="样本文件夹">
          <el-input v-model="obsidian.samples_folder" placeholder="如：05_人生样本(LifeSamples)" />
          <div class="form-hint">存放人生样本 Markdown 的文件夹，相对于仓库根目录</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="obsidianSaving" @click="handleObsidianSave">
            保存配置
          </el-button>
          <el-button :loading="scanning" @click="handleTestConnection">测试连接</el-button>
        </el-form-item>

        <div v-if="scanResult" class="connection-status" :class="scanResult.success ? 'success' : 'error'">
          {{ scanResult.message }}
        </div>
      </el-form>

      <el-divider />

      <div class="config-info">
        <h4>当前配置预览</h4>
        <p><strong>仓库路径：</strong>{{ obsidian.vault_path || '未设置' }}</p>
        <p><strong>样本文件夹：</strong>{{ obsidian.samples_folder || '未设置' }}</p>
        <p>
          <strong>完整路径：</strong>
          <code>{{ obsidian.vault_path ? `${obsidian.vault_path}/${obsidian.samples_folder}` : '请先设置路径' }}</code>
        </p>
      </div>

      <el-divider />

      <div class="quick-actions">
        <h4>快速操作</h4>
        <el-button :disabled="!obsidian.enabled" @click="openObsidianVault">📂 打开 Obsidian 仓库</el-button>
        <el-button :disabled="!obsidian.enabled" @click="openObsidianFolder">📁 打开样本文件夹</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/shared/utils/request'
import { getProfile, updateProfile } from '@/core/privacy/api/privacyApi'
import type { ProfileData } from '@/core/privacy/api/privacyApi'

const profile = reactive<ProfileData>({
  privacy_mode: false,
  logseq_path: '',
})

const obsidian = reactive({
  enabled: false,
  vault_path: '',
  samples_folder: '05_人生样本(LifeSamples)',
})

const saving = ref(false)
const saved = ref(false)
const obsidianSaving = ref(false)
const scanning = ref(false)
const scanResult = ref<{ success: boolean; message: string } | null>(null)

async function fetchProfile() {
  try {
    const res = await getProfile()
    Object.assign(profile, res.data)
  } catch {
    ElMessage.error('获取配置失败')
  }
}

async function handleSave() {
  saving.value = true
  saved.value = false
  try {
    await updateProfile({
      privacy_mode: profile.privacy_mode,
      logseq_path: profile.logseq_path,
    })
    saved.value = true
    ElMessage.success('配置已保存')
    setTimeout(() => { saved.value = false }, 2000)
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function fetchObsidianConfig() {
  try {
    const res = await request<{ enabled: boolean; vault_path: string; samples_folder: string }>({
      url: '/lifesample/obsidian/config/',
      method: 'get',
    })
    Object.assign(obsidian, res.data)
  } catch {
    // 忽略加载失败，保留默认值
  }
}

async function handleObsidianSave() {
  obsidianSaving.value = true
  try {
    await request({
      url: '/lifesample/obsidian/config/',
      method: 'post',
      data: {
        enabled: obsidian.enabled,
        vault_path: obsidian.vault_path,
        samples_folder: obsidian.samples_folder,
      },
    })
    ElMessage.success('Obsidian 配置已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    obsidianSaving.value = false
  }
}

async function handleTestConnection() {
  scanning.value = true
  scanResult.value = null
  try {
    // 先持久化表单当前值再扫描（扫描读数据库配置，避免「填了没保存」扫不到）
    await request({
      url: '/lifesample/obsidian/config/',
      method: 'post',
      data: {
        enabled: obsidian.enabled,
        vault_path: obsidian.vault_path,
        samples_folder: obsidian.samples_folder,
      },
    })
    const res = await request<unknown[]>({ url: '/lifesample/obsidian/scan/', method: 'get' })
    const count = res.data.length
    scanResult.value = {
      success: count > 0,
      message:
        count > 0
          ? `✅ 连接成功，找到 ${count} 个样本文件`
          : `⚠️ 连接成功，但「${obsidian.samples_folder}」中未找到 .md 文件`,
    }
    ElMessage.success(`扫描完成，发现 ${count} 个样本文件`)
  } catch {
    scanResult.value = { success: false, message: '❌ 连接失败，请检查仓库路径是否正确' }
    ElMessage.error('扫描失败，请检查仓库路径配置')
  } finally {
    scanning.value = false
  }
}

function openObsidianVault() {
  window.open('obsidian://open', '_blank')
}

function openObsidianFolder() {
  if (!obsidian.vault_path) {
    ElMessage.warning('请先设置仓库路径')
    return
  }
  const path = `${obsidian.vault_path}/${obsidian.samples_folder}`
  window.open(`obsidian://open?path=${encodeURIComponent(path)}`, '_blank')
}

onMounted(() => {
  fetchProfile()
  fetchObsidianConfig()
})
</script>

<style scoped lang="scss">
.admin-settings {
  padding: 24px;
  background: var(--el-bg-color-page);
  min-height: 100vh;

  .page-header {
    margin-bottom: 24px;

    .page-title {
      margin: 0;
      font-size: 22px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
  }

  .settings-card {
    margin-bottom: 20px;

    .form-hint {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
      margin-top: 4px;
      line-height: 1.4;
    }

    .connection-status {
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 13px;
      margin-bottom: 4px;
      white-space: pre-line;

      &.success {
        background: #f0f9eb;
        color: #67c23a;
        border: 1px solid #e1f3d8;
      }

      &.error {
        background: #fef0f0;
        color: #f56c6c;
        border: 1px solid #fde2e2;
      }
    }

    .config-info,
    .quick-actions {
      h4 {
        margin: 0 0 10px;
        font-size: 14px;
        color: var(--el-text-color-primary);
      }

      p {
        margin: 6px 0;
        font-size: 13px;
        color: var(--el-text-color-regular);
      }

      code {
        background: var(--el-fill-color-light);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
      }
    }
  }
}
</style>
