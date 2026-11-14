<template>
  <el-dialog
    v-model="visible"
    title="导入账单 CSV"
    width="720px"
    class="bill-import"
    @close="handleClose"
  >
    <div class="bill-import__hint">
      随手记导出的 CSV 直接可用；换别的来源只要列名能对上，或在下方手动指定。
      <br />
      导入前可以先看清「会新增几条、哪几行重复或有问题」，确认后再落库。
    </div>

    <el-upload
      :auto-upload="false"
      accept=".csv"
      drag
      :limit="1"
      :file-list="fileList"
      :on-change="handleFileChange"
      :on-remove="handleRemove"
      :on-exceed="handleExceed"
      :disabled="importing"
      :show-file-list="false"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="upload-text">
        {{ file ? file.name : '把 CSV 拖到此处，或点击选择' }}
      </div>
      <template #tip>
        <div class="upload-tip">编码支持 UTF-8 / GBK；日期支持 2026-11-08、2026/11/08 等写法</div>
      </template>
    </el-upload>

    <div v-if="loading" class="bill-import__loading">
      <el-skeleton :rows="3" animated />
    </div>

    <!-- 整份文件不可用：把列名摆出来让人手动指认，而不是只说「格式不对」 -->
    <div v-else-if="formatError" class="block block--error">
      <el-alert type="error" :closable="false" show-icon :title="formatError" />
      <div v-if="columns.length" class="mapping">
        <div class="mapping__title">这份文件的列（未识别的请手动指定）</div>
        <div v-for="col in columns" :key="col.raw" class="mapping__row">
          <span class="mapping__raw">{{ col.raw }}</span>
          <span class="mapping__arrow">→</span>
          <el-select
            :model-value="effectiveField(col)"
            size="small"
            placeholder="未识别"
            :teleported="false"
            class="mapping__select"
            @update:model-value="setMapping(col.raw, String($event))"
          >
            <el-option label="（忽略这一列）" value="" />
            <el-option
              v-for="opt in fieldOptions"
              :key="opt.value"
              :label="opt.required ? `${opt.label}（必需）` : opt.label"
              :value="opt.value"
              :disabled="isTaken(opt.value, col.raw)"
            />
          </el-select>
          <span class="mapping__sample">{{ col.sample }}</span>
        </div>
      </div>
    </div>

    <template v-else-if="preview">
      <div class="block">
        <div class="summary">
          <span class="summary__item">共 {{ preview.summary.total }} 行</span>
          <span class="summary__item summary__item--new">新增 {{ preview.summary.new }}</span>
          <span class="summary__item summary__item--dup">重复 {{ preview.summary.duplicate }}（库中已有）</span>
          <span v-if="preview.summary.error" class="summary__item summary__item--err">
            出错 {{ preview.summary.error }}
          </span>
          <span v-if="preview.summary.inner_duplicate" class="summary__hint">
            其中 {{ preview.summary.inner_duplicate }} 行与文件内其它行相同，仍会各记一条
          </span>
        </div>

        <!-- 没认出来的列只要有值就要摆出来：否则「导入成功、分类全空」，月底才发现 -->
        <el-alert
          v-if="preview.ignored_columns?.length"
          class="ignored"
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            <span>
              有 {{ preview.ignored_columns.length }} 列有内容但不会导入：
              <b v-for="(col, i) in preview.ignored_columns" :key="col.raw">
                {{ col.raw }}<template v-if="col.sample">（例：{{ col.sample }}）</template><template v-if="i < preview.ignored_columns.length - 1">、</template>
              </b>
            </span>
          </template>
          <div class="ignored__hint">
            要保留这些内容，展开下方「列映射」把每一列指到对应字段，指完会自动重新预演。
          </div>
        </el-alert>

        <!-- 没有类型列 ⇒ 必须由人指定方向，猜错不会报错，只会把收入记成支出 -->
        <div v-if="preview.needs_default_type" class="default-type">
          <span class="default-type__label">这份文件没有「交易类型」列，这批账是：</span>
          <el-radio-group v-model="defaultType" size="small">
            <el-radio-button value="支出">支出</el-radio-button>
            <el-radio-button value="收入">收入</el-radio-button>
          </el-radio-group>
        </div>

        <div class="mapping">
          <div class="mapping__title mapping__title--clickable" @click="mappingOpen = !mappingOpen">
            <span>
              列映射：{{ mappingStatus }}
              <span class="mapping__toggle">{{ mappingOpen ? '收起' : '展开调整' }}</span>
            </span>
            <span class="mapping__hint">表头在第 {{ preview.header_row }} 行 · 改完自动重新预演，不会写库</span>
          </div>
          <template v-if="mappingOpen">
            <div v-for="col in columns" :key="col.raw" class="mapping__row">
              <span class="mapping__raw" :class="{ 'mapping__raw--bad': !effectiveField(col) }">
                {{ col.raw }}
              </span>
              <span class="mapping__arrow">→</span>
              <el-select
                :model-value="effectiveField(col)"
                size="small"
                placeholder="未识别"
                :teleported="false"
                class="mapping__select"
                @update:model-value="setMapping(col.raw, String($event))"
              >
                <el-option label="（忽略这一列）" value="" />
                <el-option
                  v-for="opt in fieldOptions"
                  :key="opt.value"
                  :label="opt.required ? `${opt.label}（必需）` : opt.label"
                  :value="opt.value"
                  :disabled="isTaken(opt.value, col.raw)"
                />
              </el-select>
              <span class="mapping__sample">{{ col.sample }}</span>
            </div>
          </template>
        </div>

        <div v-if="preview.rows.length" class="rows">
          <div class="rows__title">预览（最多 50 行）</div>
          <div v-for="row in preview.rows" :key="`${row.verdict}-${row.row_no}`" class="rows__row">
            <span class="rows__no">第 {{ row.row_no }} 行</span>
            <span class="rows__date">{{ row.date || '—' }}</span>
            <span class="rows__type">{{ row.type || '—' }}</span>
            <span class="rows__amount">{{ row.amount == null ? '—' : `¥${row.amount.toFixed(2)}` }}</span>
            <span class="rows__cat" :class="{ 'rows__cat--empty': !row.category && !row.subcategory }">
              {{ row.category || '—' }}<template v-if="row.subcategory"> / {{ row.subcategory }}</template>
            </span>
            <el-tag :type="verdictTag(row.verdict)" size="small">{{ verdictLabel(row.verdict) }}</el-tag>
            <span class="rows__reason">{{ row.reason }}</span>
          </div>
        </div>
      </div>
    </template>

    <div v-if="result" class="block block--result">
      <el-alert :type="result.created > 0 ? 'success' : 'info'" :closable="false" show-icon>
        <template #title>
          <span>
            新增 {{ result.created }} 条
            <template v-if="result.duplicated">· 重复 {{ result.duplicated }} 条（已忽略）</template>
            <template v-if="result.skipped_by_user">· 跳过 {{ result.skipped_by_user }} 条</template>
            <template v-if="result.skipped">· {{ result.skipped }} 行未导入</template>
          </span>
        </template>
      </el-alert>
      <div v-if="result.error_rows.length" class="rows rows--errors">
        <div v-for="err in result.error_rows" :key="err.row_no" class="rows__row">
          <span class="rows__no">第 {{ err.row_no }} 行</span>
          <span class="rows__reason">{{ err.reason }}</span>
        </div>
        <div v-if="result.error_total > result.error_rows.length" class="rows__more">
          还有 {{ result.error_total - result.error_rows.length }} 行…
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">{{ result ? '关闭' : '取消' }}</el-button>
      <el-button
        v-if="!result"
        type="primary"
        :loading="importing"
        :disabled="!canImport"
        @click="confirmImport"
      >
        确认导入{{ preview && preview.summary.new ? ` (${preview.summary.new} 条)` : '' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { importCSV, previewImportCSV } from '../../api/wealthApi'
import type {
  BillFieldOption, BillImportColumn, BillImportPreview, BillImportResult, BillImportVerdict,
} from '../../types/wealthTypes'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success', count: number): void
}>()

const visible = ref(false)
const fileList = ref<Array<{ name: string }>>([])
const file = ref<File | null>(null)

const loading = ref(false)
const importing = ref(false)

/** 预演结果；`formatError` 与它互斥：整份文件不可用时只有错误和列清单 */
const preview = ref<BillImportPreview | null>(null)
const formatError = ref('')
const formatColumns = ref<BillImportColumn[]>([])
const fieldOptions = ref<BillFieldOption[]>([])

/** 用户改过的列映射：`{源列名: 字段名}`，空串表示「忽略这一列」 */
const mapping = ref<Record<string, string>>({})
/** 用户是否动过映射 —— 动过就必须把整份映射回传，不能让服务端重新猜一遍 */
const mappingTouched = ref(false)

const defaultType = ref<'' | '支出' | '收入'>('')
const result = ref<BillImportResult | null>(null)
/** 列映射默认收起：多数文件一列都不用改，摊开 11 行会把「确认导入」挤出屏幕 */
const mappingOpen = ref(false)

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  },
)

// 指定方向之后样例行里的「类型」才是真值 —— 不重跑预演的话，人看到的是空的
watch(defaultType, () => {
  if (preview.value) runPreview()
})

/** 200 时用 preview.columns；400 时用错误里带回来的列，两处结构一致 */
const columns = computed<BillImportColumn[]>(() =>
  preview.value ? preview.value.columns : formatColumns.value,
)

const canImport = computed(() => {
  if (!preview.value || importing.value || loading.value) return false
  if (preview.value.summary.new <= 0) return false
  if (preview.value.needs_default_type && !defaultType.value) return false
  return true
})

/** 这一列当前认成什么：用户改过就用改的，没改过用后端推断的 */
function effectiveField(col: BillImportColumn): string {
  const picked = mapping.value[col.raw]
  return picked === undefined ? col.mapped : picked
}

const unmappedCount = computed(
  () => columns.value.filter((col) => !effectiveField(col)).length,
)

const mappingStatus = computed(() => {
  const total = columns.value.length
  if (!total) return '还没有列'
  return unmappedCount.value
    ? `已识别 ${total - unmappedCount.value}/${total} 列，${unmappedCount.value} 列未识别`
    : `${total} 列全部识别`
})

function verdictLabel(v: BillImportVerdict) {
  return v === 'new' ? '新增' : v === 'duplicate' ? '重复' : '出错'
}

function verdictTag(v: BillImportVerdict): 'success' | 'info' | 'danger' {
  return v === 'new' ? 'success' : v === 'duplicate' ? 'info' : 'danger'
}

/** 同一个目标字段只能被一列占用 —— 两列都指向金额时后者会被静默丢弃 */
function isTaken(field: string, rawName: string) {
  return Object.entries(mapping.value).some(([raw, f]) => f === field && raw !== rawName)
}

function currentMapping(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const col of columns.value) out[col.raw] = effectiveField(col)
  return out
}

async function runPreview() {
  if (!file.value) return
  loading.value = true
  formatError.value = ''
  try {
    const res = await previewImportCSV(file.value, {
      mapping: mappingTouched.value ? currentMapping() : undefined,
      defaultType: defaultType.value || undefined,
    })
    preview.value = res.data
    fieldOptions.value = res.data.field_options
    // 有「有值但没被认领」的列 ⇒ 直接把列映射摊开：警告挂在折叠区外面，
    // 用户很容易点「确认导入」走人，然后在账单列表上才发现子分类是空的。
    if (res.data.ignored_columns?.length) mappingOpen.value = true
  } catch (e: any) {
    const data = e?.response?.data
    preview.value = null
    formatError.value = data?.error || '这份文件读不了，请确认是 CSV'
    formatColumns.value = data?.columns ?? []
    fieldOptions.value = data?.field_options ?? []
    // 认不出的列先置空，等用户手动指认；但**已经认出来的列要留住**。
    // 🔴 只补「没有过的」列，且用后端已经认出的结果兜底，不能整份置空：
    //    缺列时每指一列都会再拿一次 400，整份置空等于把刚从 400 里带回来的
    //    识别结果也一起冲掉 —— 用户补完日期和金额，分类就永久变成「未识别」。
    const init: Record<string, string> = { ...mapping.value }
    for (const col of formatColumns.value) {
      if (!(col.raw in init)) init[col.raw] = col.mapped ?? ''
    }
    mapping.value = init
    // 这份文件必须手动指认才有救，直接把映射摊开
    mappingOpen.value = true
  } finally {
    loading.value = false
  }
}

function setMapping(rawName: string, field: string) {
  mapping.value = { ...mapping.value, [rawName]: field }
  mappingTouched.value = true
  runPreview()
}

function handleFileChange(uploadFile: { name: string; raw?: File }) {
  if (!uploadFile.raw) return
  file.value = uploadFile.raw
  fileList.value = [{ name: uploadFile.name }]
  resetPreviewState()
  runPreview()
}

function handleRemove() {
  file.value = null
  fileList.value = []
  resetPreviewState()
}

function handleExceed() {
  ElMessage.warning('只能选择一个文件，请先移除已选的')
}

function resetPreviewState() {
  preview.value = null
  formatError.value = ''
  formatColumns.value = []
  mapping.value = {}
  mappingTouched.value = false
  mappingOpen.value = false
  defaultType.value = ''
  result.value = null
}

async function confirmImport() {
  if (!file.value || !preview.value) return
  importing.value = true
  try {
    const res = await importCSV(file.value, {
      // 🔴 始终回传整份映射：服务端不再重新推断，否则「预览说新增 N、实际写入 M」
      mapping: currentMapping(),
      defaultType: defaultType.value || undefined,
    })
    result.value = res.data
    if (res.data.created > 0) {
      ElMessage.success(`成功导入 ${res.data.created} 条`)
      emit('success', res.data.created)
    } else {
      ElMessage.warning('没有新增任何账单')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '导入失败')
  } finally {
    importing.value = false
  }
}

function handleClose() {
  emit('update:modelValue', false)
  file.value = null
  fileList.value = []
  resetPreviewState()
}
</script>

<style lang="scss">
/* 🔴 非 scoped：`class` 会被转发到 el-dialog 自己的 DOM 上，那个节点没有 data-v 作用域属性，
   scoped 里的 `:deep(.el-dialog__body)` 匹配不到（实测 max-height 仍是 none，页脚被挤出屏幕）。
   选择器带 `.bill-import` 前缀，不会波及其它对话框。 */
.bill-import .el-dialog__body {
  max-height: 62vh;
  overflow-y: auto;
}
</style>

<style scoped lang="scss">
.bill-import {
  &__hint {
    padding: 10px 12px;
    margin-bottom: 12px;
    font-size: 12px;
    line-height: 1.7;
    color: var(--el-text-color-secondary);
    background: var(--el-fill-color-light);
    border-radius: 6px;
  }

  &__loading {
    margin-top: 12px;
  }
}

.upload-icon {
  font-size: 40px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.upload-text {
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.upload-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.block {
  margin-top: 14px;

  &--error,
  &--result {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: baseline;
  font-size: 13px;

  &__item {
    color: var(--el-text-color-regular);

    &--new {
      color: var(--el-color-success);
      font-weight: 600;
    }

    &--dup {
      color: var(--el-text-color-secondary);
    }

    &--err {
      color: var(--el-color-danger);
    }
  }

  &__hint {
    flex-basis: 100%;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

.default-type {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 8px 10px;
  background: var(--el-color-warning-light-9);
  border-radius: 6px;

  &__label {
    font-size: 13px;
    color: var(--el-color-warning-dark-2);
  }
}

.ignored {
  margin-top: 10px;

  &__hint {
    font-size: 12px;
    line-height: 1.6;
    color: var(--el-color-warning-dark-2);
  }
}

.mapping {
  margin-top: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;

  &__title {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 8px 12px;
    font-size: 13px;
    background: var(--el-fill-color-light);

    &--clickable {
      cursor: pointer;
      user-select: none;
    }
  }

  &__toggle {
    margin-left: 8px;
    font-size: 12px;
    color: var(--el-color-primary);
  }

  &__hint {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-top: 1px solid var(--el-border-color-lighter);
  }

  &__raw {
    min-width: 96px;
    font-size: 13px;
    color: var(--el-text-color-primary);

    &--bad {
      color: var(--el-color-danger);
    }
  }

  &__arrow {
    color: var(--el-text-color-placeholder);
  }

  &__select {
    width: 170px;
  }

  &__sample {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

.rows {
  margin-top: 12px;
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;

  &__title {
    padding: 6px 12px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    background: var(--el-fill-color-light);
  }

  &__row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 12px;
    font-size: 12px;
    border-top: 1px solid var(--el-border-color-lighter);
  }

  &__no {
    min-width: 62px;
    color: var(--el-text-color-secondary);
  }

  &__date {
    min-width: 140px;
  }

  &__amount {
    min-width: 74px;
    font-variant-numeric: tabular-nums;
  }

  &__cat {
    min-width: 116px;
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;

    &--empty {
      color: var(--el-color-danger);
    }
  }

  &__reason {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--el-text-color-secondary);
  }

  &__more {
    padding: 6px 12px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    border-top: 1px solid var(--el-border-color-lighter);
  }
}
</style>
