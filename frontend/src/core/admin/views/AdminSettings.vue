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
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getProfile, updateProfile } from '@/core/privacy/api/privacyApi'
import type { ProfileData } from '@/core/privacy/api/privacyApi'

const profile = reactive<ProfileData>({
  privacy_mode: false,
  logseq_path: '',
})

const saving = ref(false)
const saved = ref(false)

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

onMounted(fetchProfile)
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
  }
}
</style>
