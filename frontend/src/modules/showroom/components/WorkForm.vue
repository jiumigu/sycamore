<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import * as showroomApi from '../api/showroomApi'
import type { ShowroomMedia, ShowroomWork, WorkCandidate } from '../types/showroomTypes'
import MediaPicker from '@/shared/components/MediaPicker.vue'

const props = defineProps<{
  modelValue: boolean
  item: ShowroomWork | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: Record<string, unknown>]
}>()

const formRef = ref<FormInstance>()
const form = reactive({
  work: null as number | null,
  curator_note: '',
  media: [] as ShowroomMedia[],
  is_visible: true,
  sort_order: 0,
})

const rules = {
  work: [{ required: true, message: '从作品库里选一件', trigger: 'change' }],
}

const candidates = ref<WorkCandidate[]>([])
const candidateLoading = ref(false)

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const w = props.item
    form.work = w?.work ?? null
    form.curator_note = w?.curator_note ?? ''
    form.media = w?.media ? [...w.media] : []
    form.is_visible = w?.is_visible ?? true
    form.sort_order = w?.sort_order ?? 0
    formRef.value?.clearValidate()
    searchWorks('')
  },
)

async function searchWorks(keyword: string) {
  candidateLoading.value = true
  try {
    const res = await showroomApi.getWorkCandidates(keyword ? { search: keyword } : undefined)
    candidates.value = Array.isArray(res.data) ? res.data : (res.data.results ?? [])
  } catch {
    candidates.value = []
  } finally {
    candidateLoading.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}

async function uploadMedia(file: File) {
  const res = await showroomApi.uploadShowroomMedia(file)
  return res.data
}

async function submit() {
  await formRef.value?.validate()
  emit('submit', { ...form, media: [...form.media] })
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="item ? '编辑馆藏' : '选作品进馆'"
    width="560px"
    destroy-on-close
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :validate-on-rule-change="false"
      label-width="90px"
    >
      <el-form-item label="作品" prop="work">
        <el-select
          v-model="form.work"
          filterable
          remote
          :remote-method="searchWorks"
          :loading="candidateLoading"
          placeholder="从作品库里搜一件"
          style="width: 100%"
        >
          <el-option
            v-for="c in candidates"
            :key="c.id"
            :label="c.name"
            :value="c.id"
          >
            <span>{{ c.name }}</span>
            <span class="candidate-summary">{{ c.summary }}</span>
          </el-option>
        </el-select>
        <div class="form-tip">只挑「能证明能力」的那几件 —— 作品馆是能力的现场，不是作品全集。</div>
      </el-form-item>
      <el-form-item label="策展导语">
        <el-input
          v-model="form.curator_note"
          type="textarea"
          :rows="3"
          placeholder="给访客写一句：这件作品证明了什么（可留空）"
        />
      </el-form-item>
      <el-form-item label="配图 / 视频">
        <MediaPicker v-model="form.media" :upload="uploadMedia" />
      </el-form-item>
      <el-form-item label="是否展示">
        <el-switch v-model="form.is_visible" />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.candidate-summary {
  float: right;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: 12px;
}
.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
</style>
