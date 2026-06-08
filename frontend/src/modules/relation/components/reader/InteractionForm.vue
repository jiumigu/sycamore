<template>
  <el-dialog
    v-model="visible"
    title="✍️ 新增互动"
    width="520px"
    :close-on-click-modal="false"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" label-position="left">
      <!-- 记录模式 -->
      <el-form-item label="记录模式">
        <el-radio-group v-model="isBatchMode">
          <el-radio :value="false">单条记录</el-radio>
          <el-radio :value="true">批量汇总</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="groups.length > 1" label="所属群体" prop="reader_group">
        <el-select v-model="form.reader_group" placeholder="选择群体" style="width: 100%">
          <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
      </el-form-item>

      <!-- 单条模式 -->
      <template v-if="!isBatchMode">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="读者昵称" prop="reader_name">
              <el-input v-model="form.reader_name" placeholder="读者昵称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="互动类型" prop="interaction_type">
              <el-select v-model="form.interaction_type" placeholder="选择" style="width: 100%">
                <el-option v-for="opt in INTERACTION_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="互动时间" prop="interaction_date">
              <el-date-picker
                v-model="form.interaction_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="不选默认为今天"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="互动内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="3" placeholder="留言/转发/打赏等具体内容" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="关联文章" prop="article_title">
          <el-input v-model="form.article_title" placeholder="选填" />
        </el-form-item>
      </template>

      <!-- 批量模式 -->
      <template v-if="isBatchMode">
        <el-form-item label="汇总类型" prop="interaction_type">
          <el-select v-model="form.interaction_type" style="width: 100%">
            <el-option label="➕ 新增关注" value="follow" />
            <el-option label="➖ 取关" value="unfollow" />
            <el-option label="❤️ 新增点赞" value="like" />
            <el-option label="🔄 转发" value="share" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="form.batch_count" :min="1" :max="999" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.content" type="textarea" :rows="2" placeholder="如：本周新增关注来源《XXX》文章" />
        </el-form-item>
      </template>

      <el-form-item label="能量分" prop="energy_score">
        <div class="energy-row">
          <el-slider
            v-model="form.energy_score"
            :min="-5"
            :max="10"
            :step="1"
            :marks="energyMarks"
            show-stops
            style="flex:1"
          />
          <span class="energy-value" :style="{ color: scoreColor }">{{ form.energy_score }}</span>
        </div>
      </el-form-item>
      <el-form-item label="共振关键词" prop="tags">
        <el-input v-model="form.tags" placeholder="逗号分隔，如：系统思维,个人管理" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import { INTERACTION_TYPE_OPTIONS, energyColor } from '../../types/readerTypes'
import type { ReaderGroup } from '../../types/readerTypes'

const props = defineProps<{
  visible: boolean
  groups: ReaderGroup[]
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: Record<string, unknown>]
}>()

const visible = computed({
  get: () => props.visible,
  set: (val: boolean) => emit('update:visible', val),
})

const formRef = ref<FormInstance>()
const isBatchMode = ref(false)

const form = ref({
  reader_group: null as number | null,
  reader_name: '',
  interaction_type: 'comment',
  content: '',
  article_title: '',
  energy_score: 1,
  tags: '',
  interaction_date: '',
  batch_count: 1,
})

const rules = {
  reader_group: [{ required: true, message: '请选择所属群体', trigger: 'change' }],
  reader_name: [{ required: true, message: '请输入读者昵称', trigger: 'blur' }],
  interaction_type: [{ required: true, message: '请选择互动类型', trigger: 'change' }],
}

const energyMarks = {
  0: '0',
  3: '3',
  5: '5',
  10: '10',
}

const scoreColor = computed(() => energyColor(form.value.energy_score))

function defaultGroupId(): number | null {
  if (props.groups.length === 0) return null
  const found = props.groups.find(g => g.name === '公众号读者')
  return found ? found.id : props.groups[0].id
}

function resetForm() {
  isBatchMode.value = false
  form.value = {
    reader_group: defaultGroupId(),
    reader_name: '',
    interaction_type: 'comment',
    content: '',
    article_title: '',
    energy_score: 1,
    tags: '',
    interaction_date: '',
    batch_count: 1,
  }
}

function buildPayload(): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...form.value }
  if (isBatchMode.value) {
    payload.reader_name = '批量汇总'
    payload.article_title = ''
    if (payload.interaction_type === 'unfollow') {
      payload.energy_score = 0
    } else if (payload.interaction_type === 'follow') {
      payload.energy_score = payload.energy_score || 1
    }
  }
  if (!payload.interaction_date) {
    delete payload.interaction_date
  }
  return payload
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  emit('submit', buildPayload())
}

watch(() => props.visible, (v) => {
  if (v) {
    if (!form.value.reader_group) form.value.reader_group = defaultGroupId()
  } else {
    resetForm()
  }
})
watch(() => props.groups, () => {
  if (props.visible && !form.value.reader_group) {
    form.value.reader_group = defaultGroupId()
  }
})
</script>

<style scoped>
.energy-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.energy-value {
  font-size: 20px;
  font-weight: 700;
  min-width: 30px;
  text-align: center;
}
</style>
