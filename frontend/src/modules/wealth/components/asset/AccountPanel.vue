<template>
  <div class="account-panel">
    <div class="panel-header">
      <div class="panel-header__left">
        <h3>资产科目主数据</h3>
        <span class="panel-header__hint">
          科目在这里增删 —— 加「证券账户」「保险现金价值」不用改表结构
        </span>
      </div>
      <div class="panel-header__right">
        <el-dropdown @command="handleSeed">
          <el-button size="small" :loading="saving">
            初始化科目
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="fill">补齐缺失科目（不动已改的）</el-dropdown-item>
              <el-dropdown-item command="overwrite" divided>
                重置为默认值（会覆盖已改的类别与流动性）
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" size="small" @click="openDialog()">
          <el-icon><Plus /></el-icon>
          新增科目
        </el-button>
      </div>
    </div>

    <!-- 结构汇总 -->
    <div v-if="summary" class="summary-strip">
      <div class="summary-strip__item">
        <span class="label">启用科目</span>
        <span class="value">{{ summary.active_count }}</span>
        <span class="sub">共 {{ summary.total }} 个</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">T+0 可取</span>
        <span class="value">{{ summary.liquid_count }}</span>
        <span class="sub">计入应急金分子</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">计入资产负债表</span>
        <span class="value">{{ summary.counted_count }}</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">不计入</span>
        <span class="value">{{ summary.excluded_count }}</span>
        <span class="sub">仍进明细，只是不参与合计</span>
      </div>
    </div>

    <!-- 类别分布 -->
    <div v-if="summary" class="category-strip">
      <el-tag
        v-for="c in summary.by_category"
        :key="c.category"
        size="small"
        effect="plain"
        class="category-tag"
      >
        {{ c.category }} {{ c.count }}
        <span class="category-tag__sub">（计表 {{ c.counted }} · 可取 {{ c.liquid }}）</span>
      </el-tag>
    </div>

    <!--
      🔴 遮罩只在「这张表还没有数据可显示」时挂（v3.62.25）。

        `v-loading` 生成的是 `.el-loading-mask`，它默认 `pointer-events: auto`
        —— **会吃掉点击**。而本表里的「编辑 / 停用」都是**纯前端动作**
        （打开弹窗、切换标记），不依赖这张表的数据新鲜度，
        所以**刷新期间没有任何理由拦住它们**。

        2026-10-16 用户报「点『编辑』没反应，表现成无响应」。实测复现：
        只要后台有请求在跑，遮罩就盖在按钮上，点击被吞**且不会补发**
        （延迟结束后弹窗依然没开，用户必须重点一次）。
        ⇒ 首次加载（表里还没数据）挂遮罩；已有数据时刷新**不挂**。
    -->
    <el-table :data="accounts" v-loading="loading && !accounts.length" stripe size="small" style="width: 100%">
      <el-table-column label="科目名" min-width="130" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.name }}
          <el-tag v-if="!row.is_active" size="small" type="info" class="inline-tag">已停用</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="映射码" width="130" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.code" class="code">{{ row.code }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="类别" width="86" />
      <el-table-column prop="account_kind" label="形态" width="100" />
      <el-table-column label="机构" width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ row.institution || '—' }}</template>
      </el-table-column>
      <el-table-column label="T+0 可取" width="88" align="center">
        <template #default="{ row }">
          <el-icon v-if="row.is_liquid" class="yes"><CircleCheck /></el-icon>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="计入资产" width="88" align="center">
        <template #default="{ row }">
          <el-icon v-if="row.include_in_balance_sheet" class="yes"><CircleCheck /></el-icon>
          <span v-else class="muted" title="只进明细，不参与任何合计">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="sort" label="排序" width="70" align="right" />
      <el-table-column label="被引用" width="90" align="right">
        <template #default="{ row }">
          <span v-if="row.used_snapshot_count > 0">{{ row.used_snapshot_count }} 期</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <div class="action-btns">
            <el-button size="small" @click="openDialog(row, $event)">编辑</el-button>
            <el-button
              v-if="row.used_snapshot_count === 0"
              size="small"
              type="danger"
              @click="handleDelete(row)"
            >删除</el-button>
            <el-button v-else size="small" @click="handleToggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty-hint">
          还没有资产科目。点「初始化科目」按旧表的 9 个科目（含借出款）生成一套，
          或点「新增科目」手工添加。
        </div>
      </template>
    </el-table>

    <!--
      新增/编辑

      🔴 `append-to-body`（v3.62.19 补）：本面板是渲染在「口径配置」抽屉**里面**的，
        而 `el-dialog` 默认就地把节点挂在原地 ⇒ 弹窗的 `.el-overlay` 会成为
        抽屉 `.el-drawer` 的子节点。后果是整个弹窗（含它的 fixed 定位与 z-index）
        被关进抽屉的层叠上下文：
          · 抽屉做开合动画时 `transform` 不为 none ⇒ `position: fixed` 的包含块
            变成抽屉本身，弹窗按抽屉而不是视口居中（实测动画期间就会偏）；
          · 弹窗的 z-index 依赖全局递增分配，一旦某次分配落后于抽屉，弹窗就**被抽屉盖住**
            —— 用户点「编辑」后什么都看不见，表现就是「页面无响应」。
        挂到 body 后这两个问题一起消失，弹窗的层叠只跟页面同级元素比。
    -->
    <el-dialog
      v-model="showDialog"
      :title="form.id ? '编辑科目' : '新增科目'"
      width="620px"
      append-to-body
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="科目名" required>
              <el-input v-model="form.name" placeholder="如 证券账户" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产类别">
              <el-select v-model="form.category" style="width:100%" @change="applyDefaultExclude">
                <el-option v-for="c in ASSET_CATEGORIES" :key="c" :label="c" :value="c" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="账户形态">
              <el-select v-model="form.account_kind" style="width:100%" @change="applyDefaultLiquid">
                <el-option v-for="k in ASSET_ACCOUNT_KINDS" :key="k" :label="k" :value="k" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="机构">
              <el-input v-model="form.institution" placeholder="如 华泰证券" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="映射码">
          <el-input v-model="form.code" placeholder="旧表列名（zplay / jianbank …）；手工新增可留空" />
          <div class="field-hint">
            记录这个科目对应旧表的哪一列 —— 回填历史快照时靠它对应。手工新增的科目留空即可。
          </div>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="T+0 可取">
              <el-switch v-model="form.is_liquid" />
              <div class="field-hint">决定它算不算应急金</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计入资产负债表">
              <el-switch v-model="form.include_in_balance_sheet" />
              <div class="field-hint">自用资产（房/车）建议关掉</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :step="10" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用">
              <el-switch v-model="form.is_active" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="备注">
          <el-input v-model="form.note" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ form.id ? '更新' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, ArrowDown, CircleCheck } from '@element-plus/icons-vue'
import { useAssetStore } from '../../stores/assetStore'
import { apiErrorText } from '@/shared/utils/apiError'
import {
  ASSET_CATEGORIES, ASSET_ACCOUNT_KINDS, ASSET_DEFAULT_EXCLUDE_CATEGORIES,
  ASSET_NON_LIQUID_KINDS,
} from '../../types/wealthTypes'
import type { AssetAccountItem, AssetAccountFormData } from '../../types/wealthTypes'

/**
 * 科目主数据面板。
 *
 * 这里**不接脱敏** —— 科目名（支付宝/建行）与机构名都不是隐私项，
 * 而金额根本不在主数据里（金额住在快照明细行）。别顺手加一层掩码。
 */
const store = useAssetStore()

const accounts = computed(() => store.accounts)
const summary = computed(() => store.accountSummary)
const loading = computed(() => store.accountsLoading)
const saving = computed(() => store.saving)

const showDialog = ref(false)

/** 新建科目时的默认形态 —— 「T+0 可取」的默认值由它推出，别各自写死一份 */
const DEFAULT_ACCOUNT_KIND = '储蓄卡'

function blankForm(): AssetAccountFormData {
  return {
    name: '', code: '', category: '流动性', account_kind: DEFAULT_ACCOUNT_KIND, institution: '',
    // 🔴 由**形态**推出，不写死 true。
    //    这里曾硬编码 `is_liquid: true`：用户新建「公积金福建」时改了形态却
    //    忘了关这个开关（它决定**算不算应急金**），于是库里留下列
    //    `account_kind='公积金' AND is_liquid=1` 的组合 —— 一旦录金额，
    //    应急金月数会往上虚高，而界面上完全看不出（勾是开着的）。
    is_liquid: !ASSET_NON_LIQUID_KINDS.includes(DEFAULT_ACCOUNT_KIND),
    include_in_balance_sheet: true, sort: 0, is_active: true, note: '',
  }
}

const form = reactive<AssetAccountFormData>(blankForm())

/**
 * 「点了没反应」自证体检（v3.62.26 · 临时；定位完成后这一段可整体删掉）。
 *
 * 起因：用户连续两轮报「点公积金福建的编辑按钮无响应」。而自动化 4 轮 ≈20 个场景全绿、
 * dev server 提供的也确实是当前代码 —— 现场状态与我这边不同，**再靠猜没有意义**。
 * 按 §103 的判据：只要出现「点了没反应」，**先做一次命中探针**，
 * 让代码自己交代是哪种「无响应」，而不是让人再猜一轮、再试一轮。
 *
 * 两条判据各回答一种「无响应」，互不重叠：
 *   ① 事件**根本没送到按钮上**（有东西盖着）⇒ 坐标落在按钮矩形内、target 却不是它；
 *   ② 事件送到了、处理器也跑了、**弹窗却没出来** ⇒ 350ms 后仍查不到可见弹窗。
 * 命中任一条：控制台打体检报告 + 界面给一句话。**绝不静默**（§2 静默失败是头号敌人）。
 *
 * ⚠️ ① 必须挂在 `document` 的**捕获期**：遮罩若在 panel 之外，事件压根不会冒泡进本组件，
 *    挂在 panel 上就永远收不到那一次点击。
 */
function hitReport(x: number, y: number) {
  const chain: string[] = []
  let node: Element | null = document.elementFromPoint(x, y)
  while (node && chain.length < 6) {
    const cls = String(node.className || '').split(' ').filter(Boolean).slice(0, 2).join('.')
    chain.push(node.tagName + (cls ? '.' + cls : ''))
    node = node.parentElement
  }
  return {
    命中: chain[0] ?? '(空)',
    命中链: chain,
    页面浮层: Array.from(document.querySelectorAll('.el-overlay, .el-loading-mask'))
      .map((o) => `${String(o.className).split(' ').slice(0, 2).join('.')}(z=${getComputedStyle(o).zIndex})`),
    弹窗在DOM: !!document.querySelector('.el-dialog'),
  }
}

function onDocClickCapture(ev: MouseEvent) {
  const t = ev.target as Element | null
  if (t?.closest('.action-btns')) return           // 正常：点到的就是操作列
  const btns = document.querySelectorAll<HTMLElement>('.account-panel .action-btns .el-button')
  for (const b of btns) {
    const r = b.getBoundingClientRect()
    if (ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom) continue
    const label = (b.innerText || '').trim()
    const rep = hitReport(ev.clientX, ev.clientY)
    console.error('[资产科目] 这次点击没送到按钮上 —— 体检报告',
      { 想点: label, 点击坐标: [ev.clientX, ev.clientY], ...rep })
    ElMessage.error(`「${label}」点不到：有元素盖在上面（${rep.命中}）—— 控制台有体检报告`)
    return
  }
}

onMounted(() => { document.addEventListener('click', onDocClickCapture, true) })
onUnmounted(() => { document.removeEventListener('click', onDocClickCapture, true) })

function openDialog(row?: AssetAccountItem, ev?: MouseEvent) {
  // 🔴 弹窗**可能已经开着**（上一次没关，或用户不确定关没关）。
  //    此时若只写 `showDialog.value = true`，值根本没变 ⇒ Vue 什么都不会做
  //    ⇒ 用户点了「编辑」却**毫无反馈**，表现就是「页面无响应」。
  //    故：已开着时先关，下一帧再开 —— 每次点击都有一次可见的打开动作。
  const alreadyOpen = showDialog.value
  if (alreadyOpen) showDialog.value = false

  try {
    Object.assign(form, blankForm())
    if (row) {
      Object.assign(form, {
        id: row.id, code: row.code || '', name: row.name, category: row.category,
        account_kind: row.account_kind, institution: row.institution,
        is_liquid: row.is_liquid, include_in_balance_sheet: row.include_in_balance_sheet,
        sort: row.sort, is_active: row.is_active, note: row.note,
      })
    } else {
      // 新建：把两个「建议默认值」都过一遍。判据只写在 applyDefault* 一处 ——
      // 将来改默认形态 / 默认类别，这里不必跟着改。
      // ⚠️ 编辑路径**不走**这两个函数：那里是回显用户已存的显式选择，不该被建议覆盖。
      applyDefaultExclude()
      applyDefaultLiquid()
    }
  } catch (e) {
    // 回填抛错 ⇒ 弹窗永远打不开，界面上却是「点了没反应」—— 静默失败的典型形态。
    console.error('[资产科目] 回填表单失败', e)
    ElMessage.error(`打开弹窗失败：${(e as Error)?.message || e}`)
    return
  }

  if (alreadyOpen) {
    nextTick(() => { showDialog.value = true })
  } else {
    showDialog.value = true
  }

  // 判据②：处理器跑完了，那就必须**看得见**弹窗 —— 没看见就说清，别让用户对着屏幕猜。
  window.setTimeout(() => {
    const el = document.querySelector('.el-dialog')
    const r = el?.getBoundingClientRect()
    const visible = !!r && r.width > 0 && r.height > 0
      && r.bottom > 0 && r.top < window.innerHeight
      && r.right > 0 && r.left < window.innerWidth
    if (visible) return
    console.error('[资产科目] 弹窗没能显示出来 —— 体检报告', {
      行: row ? `${row.id} ${row.name}` : '新增',
      弹窗矩形: r ? [r.x, r.y, r.width, r.height].map((v) => Math.round(v)) : null,
      视口: [window.innerWidth, window.innerHeight],
      ...(ev ? hitReport(ev.clientX, ev.clientY) : {}),
    })
    ElMessage.error('编辑弹窗没能显示出来 —— 请把控制台里 [资产科目] 那段发给我')
  }, 350)
}

/** 类别切换时联动「计入资产」的默认值 —— 仅在新填时给建议，不覆盖用户的显式选择 */
function applyDefaultExclude() {
  if (ASSET_DEFAULT_EXCLUDE_CATEGORIES.includes(form.category!)) {
    form.include_in_balance_sheet = false
  }
}

/**
 * 形态切换时联动「T+0 可取」—— 同样只给建议。
 *
 * ⚠️ **单向**：命中非流动形态就关掉，**不反向打开**。
 *    反向打开会把用户显式关过的科目重新塞进应急金分子（乐观方向错误）；
 *    真想要 T+0 自己打开开关即可。
 * 与 `applyDefaultExclude` 同构，两个联动在界面上是并排的两个开关。
 */
function applyDefaultLiquid() {
  if (ASSET_NON_LIQUID_KINDS.includes(form.account_kind!)) {
    form.is_liquid = false
  }
}

async function handleSave() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写科目名')
    return
  }
  try {
    await store.saveAccount({ ...form, code: form.code || null })
    showDialog.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(apiErrorText(e, '保存失败'))
  }
}

async function handleDelete(row: AssetAccountItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除科目「${row.name}」？`, '删除科目', { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await store.removeAccount(row.id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(apiErrorText(e, '删除失败'))
  }
}

async function handleToggleActive(row: AssetAccountItem) {
  const next = !row.is_active
  try {
    await store.saveAccount({ id: row.id, name: row.name, is_active: next })
    ElMessage.success(next ? '已启用' : '已停用（历史快照不受影响）')
  } catch (e) {
    ElMessage.error(apiErrorText(e, '操作失败'))
  }
}

async function handleSeed(command: string) {
  const overwrite = command === 'overwrite'
  if (overwrite) {
    try {
      await ElMessageBox.confirm(
        '重置会把已有科目的类别、T+0 标记、机构等改回种子默认值。'
        + '你自己改过的设置会丢失。确认继续？',
        '重置为默认值',
        { type: 'warning', confirmButtonText: '确认重置' },
      )
    } catch {
      return
    }
  }
  try {
    const result = await store.seedAccounts(overwrite) as {
      created: number; kept: number; updated: number
    }
    ElMessage.success(
      overwrite
        ? `已重置：${result.updated} 个科目`
        : `补齐完成：新建 ${result.created} 个，保留 ${result.kept} 个`,
    )
  } catch (e) {
    ElMessage.error(apiErrorText(e, '初始化失败'))
  }
}

</script>

<style scoped>
.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; margin-bottom: 12px; flex-wrap: wrap;
}
.panel-header__left { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.panel-header__left h3 { margin: 0; font-size: 16px; font-weight: 600; }
.panel-header__hint { font-size: 12px; color: var(--el-text-color-secondary); }
.panel-header__right { display: flex; align-items: center; gap: 8px; }

.summary-strip {
  display: flex; flex-wrap: wrap; gap: 24px;
  padding: 12px 16px; margin-bottom: 10px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.summary-strip__item { display: flex; flex-direction: column; gap: 2px; }
.summary-strip__item .label { font-size: 12px; color: var(--el-text-color-secondary); }
.summary-strip__item .value { font-size: 17px; font-weight: 600; font-variant-numeric: tabular-nums; }
.summary-strip__item .sub { font-size: 11px; color: var(--el-text-color-placeholder); }

.category-strip {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;
}
.category-tag__sub { color: var(--el-text-color-secondary); font-size: 11px; }

.inline-tag { margin-left: 6px; }
.code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px; color: var(--el-text-color-regular);
}
.muted { color: var(--el-text-color-placeholder); }
.yes { color: var(--el-color-success); }

.field-hint { font-size: 11px; color: var(--el-text-color-placeholder); line-height: 1.4; }

.empty-hint { padding: 20px 0; font-size: 13px; color: var(--el-text-color-secondary); }

.action-btns {
  display: flex; gap: 4px; flex-wrap: nowrap; white-space: nowrap;
  :deep(.el-button) { padding: 4px 8px; font-size: 12px; flex-shrink: 0; }
}
</style>
