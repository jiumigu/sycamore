<!--
  身上之物 · 部位维护（v3.62.4）

  部位是**轻量主数据**：眼 / 耳 / 鼻 / 口 / 脸 / 头发 / 手 / 指甲 / 身体四肢 / 脚 / 私处，
  随时可以自己增删改。

  🔴 为什么它不是写死的一个下拉框：你列的那六项里，「指甲」是「手」的一部分 ——
     一个互斥枚举一旦混进不同质的成员，它必然变成**兜底桶**
     （好恶物档案馆已付过一次学费：「方法」类占了 74%）。
     写死六个值的话，「口腔」「耳朵」「私处」「头发」就没有地方放。

  🔴 「删除」是本模块**唯一**会失败的操作，而且失败是**正常的**：
     其下还有位时后端返回 400 + 「「眼」下还有 2 条…不能直接删除」。
     ⇒ 那句 `detail` 必须原样弹出来，换成一句「删除失败」就把
       「下一步该干什么」也一起丢掉了。
     ⇒ **绝不级联删除**：删掉一个建错的空部位，与删掉整个部位下的所有条目，
       不该走同一个按钮 —— 代价完全不对称且不可逆。

  ⚠️ 表里那一列「条目数」不是装饰：它就是「为什么这个部位删得掉 / 删不掉」的答案。
     没有它，用户只会看到一个时灵时不灵的删除按钮。

  ⚠️ 这里**只管部位**。眼镜 / 护手霜 / 指甲剪那些是「位」，在清单里加 ——
     这行小字必须在用户动手的那一刻摆出来，否则他会把需求建到部位上。
-->

<template>
  <el-dialog v-model="visible" title="部位" width="640px" :close-on-click-modal="false">
    <div class="body-parts__head">
      <span class="body-parts__hint">
        这里管的是<b>身体的部位</b>；眼镜、护手霜、指甲剪那些是<b>位</b>，在清单里加
      </span>
      <div class="body-parts__actions">
        <el-button size="small" :loading="store.saving" @click="onSeed">
          初始化默认部位
        </el-button>
        <el-button size="small" type="primary" plain @click="startCreate">
          <el-icon><Plus /></el-icon>新增部位
        </el-button>
      </div>
    </div>

    <!-- 就地新增 / 编辑 —— 只有两个字段，开二级弹窗比这个更绕 -->
    <div v-if="editing" class="body-parts__form">
      <el-input
        v-model="draft.name"
        size="small"
        maxlength="30"
        placeholder="部位名称，比如「指甲」"
        class="body-parts__form-name"
      />
      <el-input
        v-model="draft.note"
        size="small"
        maxlength="200"
        placeholder="说明（可选）—— 比如「指甲剪 / 锉刀」"
        class="body-parts__form-note"
      />
      <el-button size="small" type="primary" :loading="store.saving" @click="submit">
        保存
      </el-button>
      <el-button size="small" @click="editing = false">取消</el-button>
    </div>

    <el-empty
      v-if="!store.parts.length"
      description="还没有任何部位 —— 点「初始化默认部位」一次补齐十一个，或自己建"
      :image-size="60"
    />

    <el-table v-else :data="store.parts" size="small" row-key="id">
      <el-table-column prop="name" label="部位" min-width="120">
        <template #default="{ row }">
          <span class="body-parts__name">{{ row.name }}</span>
        </template>
      </el-table-column>

      <el-table-column label="说明" min-width="200">
        <template #default="{ row }">
          <span v-if="row.note">{{ row.note }}</span>
          <span v-else class="body-parts__muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="条目数" width="90" align="right">
        <template #default="{ row }">
          <span :class="{ 'body-parts__muted': !row.need_count }">
            {{ row.need_count }} 条
          </span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link size="small" @click="startEdit(row)">编辑</el-button>
          <el-button link size="small" type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="body-parts__foot">
      ⚠️ 「初始化默认部位」只补缺的；已有部位可覆盖**说明与排序**，
      <b>不会碰你建的任何一条位</b>。
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useBodyStore } from '../../stores/bodyStore'
import { extractApiMessage } from '../../utils/propertyError'
import type { BodyPart } from '../../types/bodyTypes'

const visible = defineModel<boolean>('visible', { default: false })

const store = useBodyStore()

/** 正在编辑哪一条；null = 没在编辑；`{ id: null }` = 正在新增 */
const editing = ref(false)
const editingId = ref<number | null>(null)
const draft = ref({ name: '', note: '' })

function startCreate() {
  editingId.value = null
  draft.value = { name: '', note: '' }
  editing.value = true
}

function startEdit(row: BodyPart) {
  editingId.value = row.id
  draft.value = { name: row.name, note: row.note }
  editing.value = true
}

async function submit() {
  if (!draft.value.name.trim()) {
    ElMessage.warning('部位名称不能为空')
    return
  }
  try {
    await store.savePart(
      { name: draft.value.name.trim(), note: draft.value.note },
      editingId.value ?? undefined,
    )
    ElMessage.success(editingId.value ? '已更新' : '已新增')
    editing.value = false
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '保存失败'))
  }
}

async function onDelete(row: BodyPart) {
  try {
    await ElMessageBox.confirm(
      `确认删除部位「${row.name}」？`
      + (row.need_count
        ? `它下面还有 ${row.need_count} 条，会被后端拦下 —— `
          + '请先把这些改到别的部位，或逐条删除。'
        : '这个部位下没有任何条目，可以安全删除。'),
      '删除部位',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removePart(row.id)
    ElMessage.success(`已删除部位「${row.name}」`)
  } catch (e: unknown) {
    // 🔴 400 里那句话带着「还有 N 条、该怎么办」，原样弹出来
    ElMessage.error(extractApiMessage(e, '删除失败'))
  }
}

/**
 * 初始化默认部位（幂等，**不预设任何位**）。
 *
 * 两段式：先跑一次只补缺的；如果十一个都已在（`created === 0`），
 * 再问一次要不要把说明与排序覆盖成当前默认值。
 * ⚠️ 「已有部位可覆盖说明与排序」这句暗示不发出来，它就看起来像一次无害的补齐。
 */
async function onSeed() {
  let created = 0
  try {
    const result = await store.seedParts() as { created?: number } | undefined
    created = result?.created ?? 0
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '初始化失败'))
    return
  }
  if (created) {
    ElMessage.success(`已建好 ${created} 个默认部位`)
    return
  }
  try {
    await ElMessageBox.confirm(
      '默认部位都已存在，刚才只补齐了缺的。'
      + '要把已有部位的说明与排序恢复成默认值吗？'
      + '（会冲掉你改过的说明；不会碰你建的任何一条位）',
      '覆盖部位说明与排序',
      { type: 'warning', confirmButtonText: '覆盖', cancelButtonText: '保持现状' },
    )
  } catch {
    return
  }
  try {
    const result = await store.seedParts(true) as { updated?: number } | undefined
    ElMessage.success(`已覆盖 ${result?.updated ?? 0} 个部位的说明与排序`)
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '覆盖失败'))
  }
}
</script>

<style scoped>
.body-parts__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.body-parts__hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.body-parts__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.body-parts__form {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.body-parts__form-name {
  width: 160px;
}
.body-parts__form-note {
  flex: 1;
}
.body-parts__name {
  font-weight: 600;
}
.body-parts__muted {
  color: var(--el-text-color-placeholder);
}
.body-parts__foot {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}
</style>
