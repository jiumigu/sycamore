<!--
  就地新增物件类别（v3.60.0）

  为什么要有这个小弹窗：真正的痛点是**在填物件时才发现少一个类别**
  （「电饭煲」归家电没问题，可「电动牙刷」算家电还是数码？）。
  那时候跳出当前弹窗去类别维护页，回来还得重填一遍。

  所以这里只问一个字段（名称），建完**自动选中**，编辑器一个字段都不用重填。

  ⚠️ 刻意不做成「下拉里的行内表单」：下拉一点外部就收起，
  在收起过程中提交会把「点了一下」变成「填了一半就没了」（同 `SurvivalUnitQuickAdd`）。

  🔴 那句固定小字是本浮层的**主要职责之一**，不是装饰：
     用户问过「要不要加类别，比如大物件 / 高价值物件 / 小玩意儿」——
     这三个词跨了三把尺子（体积 / 金额 / 语义），硬塞进类别会让它变成一锅乱炖；
     而类别上还挂着「默认年限预填」，混装会把预填变成**软兜底**。
     想要「大」或「贵」，用列表排序 —— 那两件事都不需要落库。
     不在这里说出来，用户下次还是会想建一个「大件」类别。
-->
<template>
  <el-dialog
    v-model="visible"
    title="新增物件类别"
    width="440px"
    :close-on-click-modal="false"
    append-to-body
  >
    <div class="property-quick-cat__hint">
      建完会<b>自动选中</b>，当前正在编辑的物件不用重填。
      <div class="property-quick-cat__rule">
        这里放的是「这东西干嘛用的」。想说「它很大」或「它很贵」，
        用列表排序，不要建类别。
      </div>
    </div>

    <el-form :model="form" label-width="80px" size="small">
      <el-form-item label="类别名称">
        <el-input
          v-model="form.name"
          placeholder="家电 / 家具 / 数码 / 交通 / 家装"
          maxlength="50"
          @keyup.enter="submit"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button size="small" type="primary" :loading="store.saving" @click="submit">
        建好并使用
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { usePropertyStore } from '../../stores/propertyStore'
import type { PropertyCategory } from '../../types/propertyTypes'
import { extractApiMessage } from '../../utils/propertyError'

const visible = defineModel<boolean>('visible', { required: true })

/** 建好之后把新类别交回调用方，由它写进表单并选中 */
const emit = defineEmits<{ created: [category: PropertyCategory] }>()

const store = usePropertyStore()

const form = reactive({ name: '' })

watch(visible, (open) => {
  if (open) form.name = ''
})

async function submit() {
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('类别名称不能为空')
    return
  }
  // 同名类别是重复的 —— 提前拦下，并告诉用户「已经有一个了，直接用」
  // （后端还有一道唯一约束，但等到 400 再说是绕远路）
  const duplicate = store.categories.find((c) => c.name === name)
  if (duplicate) {
    ElMessage.warning(`「${name}」已经存在，直接选它就行`)
    return
  }
  try {
    const created = await store.saveCategory({ name })
    const category = (created as PropertyCategory | undefined)
      // `saveCategory` 不返回行时从刚刷新过的清单里找回来，避免「建好了却没选中」
      ?? store.categories.find((c) => c.name === name)
    if (category) emit('created', category)
    ElMessage.success(`已新增类别「${name}」`)
    visible.value = false
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '新增类别失败'))
  }
}
</script>

<style scoped>
.property-quick-cat__hint {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}
.property-quick-cat__rule {
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
}
</style>
