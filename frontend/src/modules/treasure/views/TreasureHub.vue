<!--
  好恶物档案馆（v3.60.32）

  ## 这一版把「记录对象」从「类别」里拆了出来

  过去六个类别是「吃 / 穿 / 用 / 店 / 地方 / 方法」—— 其中
  **吃 / 穿 / 用 / 店 / 地方 回答的是「这东西干嘛用的」**，
  而 **方法回答的是「这东西是不是实物」**。两句话不在同一个维度上，
  于是「方法」必然变成兜底桶（实测 74%，里面装着人、公众号、课程、App 价格）。

  现在分成两根轴：
  - `subject_kind`（实物 / 方法）—— 决定**显示哪些字段**
  - `category`（吃 / 穿 / 用 / 店 / 地方 / 服务）—— 只有实物才有
  - `method_group`（生活 / 工作 / …）—— 只有方法才有，可留空

  ⇒ 「在哪能找到 / 还能找到吗」这两个实物专属字段，不再对着方法空着
     （那 17 条**不是用户懒得填，是问题没有答案**）。

  ## 三条展示纪律

  1. 🔴 **类别文案按侧取**（`store.categoriesFor(record_type)`）——
     好物侧「🏪 好店」、歹物侧「🏪 坑店」。**前端不写第二份 label**：
     写成一份就是「歹物下拉里躺着『好店』」那个 bug 的复现。
  2. ⚠️ **评分已撤下**。23/23 全是默认的 5 分，每张卡片都渲染「5 分」，
     零信息量，且与 👍/👎 + 理由这个维度重复。
  3. ⭐ **「待补理由」必须看得见**。理由允许留空（要求必填人就会攒着不做），
     但留空这件事本身要有出口 —— 否则「允许留空」退化成「永远空着」。
-->

<template>
  <div class="treasure-hub">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">好恶物档案馆</h1>
        <el-tag type="warning" class="module-tag">精神滋养</el-tag>
      </div>
      <div class="header-actions">
        <el-dropdown @command="handleAddNew">
          <el-button type="primary">
            <el-icon><Plus /></el-icon>
            新增记录
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="好">👍 好物</el-dropdown-item>
              <el-dropdown-item command="歹">👎 歹物</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- ⚠️ 口径没取到时显式说出来，**不默默用一份前端默认文案顶上** ——
         后者会让「口径没取到」看起来像「这个模块本来就只有这些类别」。 -->
    <el-alert
      v-if="store.metaUnavailable"
      class="hub-alert"
      type="warning"
      :closable="false"
      show-icon
      title="类别文案没取到（下拉会是空的）—— 点右上角「刷新」重试"
    />

    <!-- 🔴 「取不到」不能说成「没有」：列表空 + 接口挂了 ⇒ 用户会去重复登记一条 -->
    <el-alert
      v-if="store.loadError"
      class="hub-alert"
      type="error"
      :closable="false"
      show-icon
      title="列表没取到（这不是「没有记录」）—— 若刚升级过，先确认数据库迁移已执行；否则点「刷新」重试"
    />

    <!-- ① 类型 + 记录对象 -->
    <el-card class="filter-card">
      <div class="filter-row">
        <el-radio-group v-model="filterType" @change="onTypeChange" class="type-tabs">
          <el-radio-button value="">📋 全部</el-radio-button>
          <el-radio-button value="好">👍 好物</el-radio-button>
          <el-radio-button value="歹">👎 歹物</el-radio-button>
        </el-radio-group>

        <el-divider direction="vertical" />

        <el-radio-group v-model="filterKind" @change="fetchData" class="kind-tabs">
          <el-radio-button value="">全部对象</el-radio-button>
          <el-radio-button v-for="k in kindOptions" :key="k.value" :value="k.value">
            {{ k.label }}
          </el-radio-button>
        </el-radio-group>

        <!-- ⭐ 待补理由出口：点一下筛出「留空」的那批 -->
        <el-button
          v-if="store.pendingCount > 0"
          class="pending-btn"
          :type="filterPending ? 'warning' : 'default'"
          size="small"
          @click="togglePending"
        >
          📝 {{ store.pendingCount }} 条待补理由
        </el-button>
      </div>
    </el-card>

    <!--
      ② 类别筛选 —— 文案按**当前侧**取。
      ⚠️ 「全部」类型下用「好物」侧文案（默认视角）；切到「歹物」时整条自动换成
         歹物侧文案 —— 这正是「按侧取 label」的意义所在。
    -->
    <el-card class="filter-card">
      <el-radio-group v-model="filterCategory" @change="fetchData" class="category-tabs">
        <el-radio-button value="">全类别</el-radio-button>
        <el-radio-button v-for="c in categoryOptions" :key="c.value" :value="c.value">
          {{ c.label }}
        </el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- 歹物防遗忘提示 -->
    <el-card v-if="showBadReminder" class="reminder-card">
      <el-alert
        title="👀 你有歹物记录，看看之前踩过的坑！"
        type="warning"
        :closable="true"
        show-icon
        @close="showBadReminder = false"
      />
    </el-card>

    <!-- 卡片网格 -->
    <div v-loading="store.loading" class="card-grid">
      <TreasureCard
        v-for="thing in store.thingList" :key="thing.id"
        :thing="thing"
        :keep-ready="keepReady"
        :keep-state="keepStateOf(thing.id)"
        :keep-work-name="keepEntryOf(thing.id)?.work_name ?? null"
        :keep-busy="keepBusy.has(thing.id)"
        @edit="openEdit"
        @delete="handleDelete"
        @click-card="openDetail"
        @fill-reason="openEdit"
        @toggle-keep="keepThing"
      />
      <el-empty
        v-if="!store.thingList.length && !store.loading"
        :description="emptyText"
        :image-size="120"
      />
    </div>

    <!-- ─── 新增 / 编辑弹窗 ─── -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="580px" destroy-on-close>
      <!--
        🔴 `:validate-on-rule-change="false"` 是**必需**的，不是优化。
        `formRules` 是 computed（「类别」必填与否跟着 `isPhysical` 走），
        而 el-form 默认 `validateOnRuleChange: true` —— 它对 `rules` 挂了
        `watch(..., { deep: true })`，一变就 `validate()` 整张表。
        ⇒ 用户刚打开弹窗、只是戳了一下「记录对象」，空表单立刻满屏飘红
          （「请输入名称 / 请描述为什么好」），像是自己填错了什么。
        ⚠️ 关掉它**不影响提交校验**：`handleSubmit` 里是显式 `formRef.validate()`。
      -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        :validate-on-rule-change="false"
        label-width="100px"
      >
        <!--
          ⭐ 入口 3：名称**输入即搜实物**（把联动的入口放在用户正在打字的那一瞬，零额外成本）。
          🔴 只做「输入即搜 + 用户显式点选」，**绝不按名称自动写入** ——
             物件叫「小米扫地机」、档案里写「扫地机器人」，自动匹配会把两条
             不相干的东西绑在一起，而界面上看起来完全正常。
        -->
        <el-form-item label="名称" prop="name">
          <el-select
            v-model="form.name"
            filterable
            remote
            allow-create
            default-first-option
            reserve-keyword
            :remote-method="searchCandidates"
            :loading="candidateLoading"
            placeholder="叫什么名字？也可搜已有实物直接关联"
            style="width:100%"
            @change="onNameChanged"
          >
            <el-option
              v-for="c in candidates"
              :key="`${c.kind}-${c.id}`"
              :label="`${c.source_label} · ${c.name}`"
              :value="c.name"
            />
            <template v-if="candidateTotal > candidates.length" #footer>
              <span class="candidate-more">
                还有 {{ candidateTotal - candidates.length }} 条没显示 —— 把关键词写细一点
              </span>
            </template>
          </el-select>
          <div v-if="linkedPreview" class="linked-preview">
            已关联：🔗 {{ linkedPreview }}
          </div>
        </el-form-item>

        <!-- 记录对象：它决定下面显示哪些字段 -->
        <el-form-item label="记录对象">
          <el-radio-group v-model="form.subject_kind" @change="onSubjectKindChange">
            <el-radio-button
              v-for="k in kindOptions" :key="k.value" :value="k.value"
            >
              {{ k.label }}
            </el-radio-button>
          </el-radio-group>
          <div class="kind-hint">{{ kindHint }}</div>
        </el-form-item>

        <!-- 实物 ⇒ 类别；方法 ⇒ 方法归类 -->
        <el-form-item v-if="isPhysical" label="类别" prop="category">
          <el-select v-model="form.category" placeholder="它干嘛用的？" style="width:100%">
            <el-option v-for="c in formCategoryOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="方法归类">
          <el-select v-model="form.method_group" clearable placeholder="属于哪方面？（可留空）" style="width:100%">
            <el-option
              v-for="g in store.meta?.method_group_options ?? []"
              :key="g.value" :label="g.label" :value="g.value"
            />
          </el-select>
        </el-form-item>

        <!-- 好物字段 -->
        <template v-if="form.record_type === '好'">
          <el-form-item label="为什么好" prop="why_good">
            <el-input v-model="form.why_good" type="textarea" :rows="3" placeholder="它好在哪？你的真实感受…" maxlength="1000" />
          </el-form-item>
        </template>

        <!-- 歹物字段 -->
        <template v-else>
          <el-form-item label="踩坑原因" prop="avoid_reason">
            <el-input v-model="form.avoid_reason" type="textarea" :rows="2" placeholder="为什么踩坑？" maxlength="1000" />
          </el-form-item>
          <el-form-item label="实际后果">
            <el-input v-model="form.consequence" type="textarea" :rows="2" placeholder="造成了什么后果？" maxlength="1000" />
          </el-form-item>
        </template>

        <!-- 记录类型**建议**：物件状况坏了 ⇒ 提示一句，**绝不自动改** -->
        <el-alert
          v-if="brokenHint"
          class="hub-alert"
          type="warning"
          :closable="false"
          show-icon
          title="关联的物件状况是「坏了」—— 要不要改记成 👎 歹物？（好坏是你说了算，系统不替你改）"
        />

        <el-form-item label="场景">
          <el-input v-model="form.scene" placeholder="在什么场景下遇到的？" maxlength="200" />
        </el-form-item>

        <!-- 实物专属：方法型**根本不显示这两个**（问不出答案的问题不该问） -->
        <template v-if="isPhysical">
          <el-form-item label="还能找到吗">
            <el-switch v-model="form.still_available" active-text="能" inactive-text="不能" />
          </el-form-item>
          <el-form-item label="在哪能找到">
            <el-input v-model="form.where_to_find" placeholder="店铺、地点、链接…" maxlength="200" :disabled="!form.still_available" />
          </el-form-item>
        </template>

        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="多个标签用逗号分隔" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- ─── 详情弹窗 ─── -->
    <el-dialog
      v-model="showDetailDialog"
      title="详情"
      width="700px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <template v-if="viewingItem">
        <div class="detail-meta">
          <el-tag :type="viewingItem.record_type === '歹' ? 'danger' : 'success'" size="small">
            {{ viewingItem.record_type === '歹' ? '👎 歹物' : '👍 好物' }}
          </el-tag>
          <el-tag size="small" effect="plain">{{ viewingItem.subject_kind_display || viewingItem.subject_kind }}</el-tag>
          <span class="detail-category">{{ detailCategory }}</span>
        </div>

        <!-- ⭐ 入口 5：关联实物后直接摆出它的事实 —— 回头看一条评价时不必再翻另一个模块 -->
        <div v-if="viewingItem.linked_name" class="detail-linked">
          🔗 {{ viewingItem.linked_kind === 'property' ? '物件资产' : '物品清单' }} ·
          <b>{{ maskText(viewingItem.linked_name) }}</b>
          <span v-if="linkedFactLine" class="detail-linked__facts">{{ linkedFactLine }}</span>
        </div>

        <!--
          🔴 长自由文本一律走 `MarkdownText`（默认 mode="auto"）：摘录常常是直接
             拷来的 .md（`##` 小标题 / `**` 加粗 / 列表 / `---` / 引用），
             原样吐出来就是一屏裸符号。判据在 `containsMarkdown()` 里只判一次，
             纯手记（实测 41 条）仍按纯文本原样显示，观感一条都不变。
        -->
        <div v-if="viewingItem.record_type === '好'" class="detail-section">
          <div class="detail-label">👍 为什么好</div>
          <MarkdownText
            class="detail-text"
            :text="maskFreeText(viewingItem.why_good) || '（还没写理由）'"
          />
        </div>

        <template v-if="viewingItem.record_type === '歹'">
          <div class="detail-section">
            <div class="detail-label bad">👎 踩坑原因</div>
            <MarkdownText
              class="detail-text"
              :text="maskFreeText(viewingItem.avoid_reason) || '（还没写理由）'"
            />
          </div>
          <div v-if="viewingItem.consequence" class="detail-section">
            <div class="detail-label bad">😵 实际后果</div>
            <MarkdownText class="detail-text" :text="maskFreeText(viewingItem.consequence)" />
          </div>
        </template>

        <!--
          ⚠️ 这两个是**短指路字段**（「📍 在哪能找到」填的是渠道名），
             强制 mode="plain"：一句「3 * 5 = 15」或文件名里的下划线
             不该被 Markdown 读成斜体 —— 判据同 QuoteDetailDialog 的「短句型不渲染」。
        -->
        <div v-if="viewingItem.scene" class="detail-section">
          <div class="detail-label">📍 场景</div>
          <MarkdownText class="detail-text" mode="plain" :text="maskText(viewingItem.scene)" />
        </div>

        <div v-if="viewingItem.where_to_find" class="detail-section">
          <div class="detail-label">📍 在哪能找到</div>
          <MarkdownText class="detail-text" mode="plain" :text="maskText(viewingItem.where_to_find)" />
        </div>

        <div v-if="viewingItem.tags" class="detail-tags">
          <el-tag
            v-for="tag in (isActive ? [MASK_TEXT] : getTags(viewingItem.tags))"
            :key="tag" size="small" type="info"
          >{{ tag }}</el-tag>
        </div>

        <div class="detail-footer">
          <span class="detail-footer__left">
            <!--
              ⭐ 「值得留」（v3.62.12）—— 与卡片上那一个是**同一个实例**的同一个状态。
              ⚠️ 详情是「回头看一条评价」的主要位置，出口必须也在这里有一份：
                 卡片只有 3 行截断，读完理由决定「这条值得留」时人就停在这一屏。
            -->
            <KeepMark
              v-if="keepReady"
              :state="keepStateOf(viewingItem.id)"
              :work-name="keepEntryOf(viewingItem.id)?.work_name ?? null"
              :busy="keepBusy.has(viewingItem.id)"
              @toggle="keepThing(viewingItem)"
            />
            <!-- ⚠️ 「✅ 还能找到」已撤下（19/19 全是「能」，是默认态噪声）；「找不到」才算信息 -->
            <el-tag v-if="!viewingItem.still_available && viewingItem.subject_kind !== SUBJECT_KIND_METHOD" size="small" type="danger">
              ❌ 已找不到
            </el-tag>
            <el-button
              v-if="!viewingItem.has_reason"
              link type="warning" size="small" @click="editFromDetail"
            >
              📝 这条还没写理由 · 去补
            </el-button>
          </span>
          <span class="detail-time">{{ viewingItem.created_at }}</span>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, ArrowDown } from '@element-plus/icons-vue'
import { useTreasureStore } from '../stores/treasureStore'
import { SUBJECT_KIND_METHOD, SUBJECT_KIND_PHYSICAL } from '../types/treasureTypes'
import type { GoodThing, LinkCandidate } from '../types/treasureTypes'
import * as treasureApi from '../api/treasureApi'
import TreasureCard from '../components/TreasureCard.vue'
import MarkdownText from '@/shared/components/MarkdownText.vue'
// ⭐ 「值得留」（第七个入口）：勾本身与它的三态状态机都在 works 模块里，
//    这里只**消费** —— 档案馆不自己加「值得留」字段。
//    自加字段 = 第二个录入口 + 第二把尺子，而且两份对不上时不报错。
import KeepMark from '@/modules/works/components/KeepMark.vue'
import { useWorkKeep } from '@/modules/works/composables/useWorkKeep'
import type { KeepState } from '@/modules/works/types/workTypes'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import { MASK_TEXT } from '@/shared/utils/privacy'
import { apiErrorText } from '@/shared/utils/apiError'

const store = useTreasureStore()
const route = useRoute()
const { isActive, maskText, maskFreeText } = usePrivacyMask()

// ─── ⭐ 「值得留」—— 第七个入口（v3.62.12）───
//
// 🔴 这一勾**不是新东西**：它就是作品页那批「待提炼」，与里程碑 / 收件箱 /
//    读书 / 日记 / 摘录 / AI 问答走的是同一张 `WorkCapture`
//    （**同一个勾，同一个含义**）。所以这里没有新表、没有新字段、没有新接口
//    —— 只是把档案馆本来就该有的那个出口接上。
//
// 🔴 为什么不给 `GoodThing` 加一个 `is_worth_keeping` 字段：
//    那会把一个勾抄成第二份（两份对不上时不报错），更要紧的是它会成为
//    **第二个录入口** —— 收口台之外还有一处能标记，收口台就不再是收口台。
//
// ⚠️ `ready` 为假（作品库读不到）时**整个标记不渲染**：读不到 ≠ 没勾过，
//    画成「值得留」是在说谎；而解释只发生在主视图（作品页），
//    不该在七个列表页上各喊一遍「我坏了」。
const {
  ready: keepReady,
  busy: keepBusy,
  entryOf: keepEntryOf,
  load: loadKeeps,
  toggle: toggleKeep,
} = useWorkKeep('treasure')

/** 一条档案的三态。
 *  ⚠️ 每个 `useWorkKeep()` 实例各持一份 rows ⇒ 不能与 QuoteManager 共用
 *     同一个函数（那边取的是那边的实例）。同页多处引用**必须共用本实例**，
 *     否则卡片与详情弹窗会一个已勾、一个还写着「值得留」。 */
function keepStateOf(id: number): KeepState {
  const row = keepEntryOf(id)
  if (!row) return 'none'
  return row.status === 'used' ? 'used' : 'pending'
}

/**
 * 打勾 —— 标题与摘要都取自档案**自己的**字段，不让用户再写一遍。
 *
 * 🔴 好物看 `why_good`、歹物看 `avoid_reason`：与 `has_reason` 同源
 *    （「这条有没有理由」正是「这条有没有内容可留」）。恒取 `why_good`
 *    的话，歹物勾过去就是一条空摘要。
 * ⚠️ 换行归一 + 截 300：与摘录那次打勾同一处理（`CaptureInputSerializer`
 *    的 `excerpt` 上限也是 300）—— 静默超长比显式截断更糟。
 */
function keepThing(t: GoodThing) {
  const text = t.record_type === '歹' ? t.avoid_reason : t.why_good
  return toggleKeep(
    t.id,
    t.name,
    (text || '').replace(/\s+/g, ' ').trim().slice(0, 300),
  )
}

const filterType = ref('')
const filterKind = ref('')
const filterCategory = ref('')
const filterPending = ref(false)
const showBadReminder = ref(true)
const dialogVisible = ref(false)
const showDetailDialog = ref(false)
const viewingItem = ref<GoodThing | null>(null)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()

// ─── 名称检索（入口 3）───
const candidates = ref<LinkCandidate[]>([])
const candidateTotal = ref(0)
const candidateLoading = ref(false)
/** 物件状况坏了 ⇒ 给一句「要不要记成歹物？」的**提示**（绝不自动改） */
const brokenHint = ref(false)

const form = reactive({
  record_type: '好',
  subject_kind: SUBJECT_KIND_PHYSICAL,
  name: '',
  category: '',
  method_group: '',
  why_good: '',
  scene: '',
  still_available: true,
  where_to_find: '',
  avoid_reason: '',
  consequence: '',
  tags: '',
  property: null as number | null,
  survival_item: null as number | null,
})

// ─── 口径（全部来自后端 meta）───

const kindOptions = computed(() => store.meta?.subject_kind_options ?? [])

/** 筛选栏的类别文案：取**当前类型**那一侧；「全部」时按好物侧（默认视角） */
const categoryOptions = computed(
  () => store.categoriesFor(filterType.value === '歹' ? '歹' : '好'),
)

/** 表单里的类别文案：严格按**表单自己的** record_type 取 */
const formCategoryOptions = computed(() => store.categoriesFor(form.record_type))

const isPhysical = computed(() => form.subject_kind === SUBJECT_KIND_PHYSICAL)

const kindHint = computed(
  () => kindOptions.value.find((k) => k.value === form.subject_kind)?.hint ?? '',
)

const linkedPreview = computed(() => {
  if (form.property) return `物件资产 · ${form.name}`
  if (form.survival_item) return `物品清单 · ${form.name}`
  return ''
})

const emptyText = computed(() => {
  // ⚠️ 顺序有意义：先问「是不是没取到」，再问「是不是真的没有」
  if (store.loadError) return '列表没取到 —— 先看上面那条红字，别急着登记新记录'
  if (filterPending.value) return '没有待补理由的记录 —— 都写完了'
  return '还没有记录，快添加一个吧'
})

const dialogTitle = computed(() => {
  const t = form.record_type === '歹' ? '歹物' : '好物'
  return editingId.value ? `编辑${t}` : `新增${t}`
})

const detailCategory = computed(() => {
  const item = viewingItem.value
  if (!item) return ''
  if (item.subject_kind === SUBJECT_KIND_METHOD) {
    return item.method_group ? `💡 方法 · ${item.method_group}` : '💡 方法'
  }
  return item.category_display || item.category
})

/** 关联事实那一行 —— 只做**展示**拼接，不算任何口径（数值全部来自后端） */
const linkedFactLine = computed(() => {
  const facts = viewingItem.value?.linked_facts
  if (!facts) return ''
  const parts: string[] = []
  if (facts.category_name) parts.push(facts.category_name)
  if (facts.purchase_date) parts.push(`${facts.purchase_date} 购入`)
  if (facts.purchase_amount !== null) parts.push(`¥${facts.purchase_amount}`)
  if (facts.age_months !== null) {
    // 月 → 「N 年 M 月」只是换个说法，不是算新口径
    const years = Math.floor(facts.age_months / 12)
    const months = facts.age_months % 12
    parts.push(years > 0 ? `已用 ${years} 年 ${months} 月` : `已用 ${months} 月`)
  }
  if (facts.quantity !== null) {
    parts.push(`库存 ${facts.quantity}${facts.unit_name || ''}`)
  }
  return parts.join(' · ')
})

const formRules = computed(() => ({
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  // ⚠️ 类别必填与否**跟着记录对象走**：方法型没有类别，仍要求选就会卡死保存
  category: isPhysical.value
    ? [{ required: true, message: '请选择类别', trigger: 'change' }]
    : [],
  why_good: form.record_type === '好'
    ? [{ required: true, message: '请描述为什么好', trigger: 'blur' }]
    : [],
  avoid_reason: form.record_type === '歹'
    ? [{ required: true, message: '请描述踩坑原因', trigger: 'blur' }]
    : [],
}))

// ─── 取数 ───

/**
 * 🔴 必须**返回**这个 Promise，供「等列表到位再按 id 找那一条」的调用方 await
 *    （深链 `?focus=<id>`）。原先这里是 turn-and-forget，`onMounted` 紧接着读
 *    `store.thingList` 时它**恒为空数组** ⇒ 那条入口从来没打开过详情弹窗。
 *    这是「依赖异步数据的组件别指望 onMounted 那一次」的又一例：不是代码没写，
 *    是写了之后**没人等它**。改成 @change 之类的调用方不受影响（忽略返回值即可）。
 */
function fetchData() {
  const params: Record<string, unknown> = {}
  if (filterType.value) params.record_type = filterType.value
  if (filterKind.value) params.subject_kind = filterKind.value
  if (filterCategory.value) params.category = filterCategory.value
  if (filterPending.value) params.pending_reason = 1
  return Promise.all([
    store.fetchThingList(params),
    store.fetchPendingCount(),
  ])
}

function refreshData() {
  store.fetchMeta()
  fetchData()
}

function onTypeChange() {
  // 切类型 ⇒ 类别那一条的**文案整套换掉**，选中的值若两侧都有就留着
  if (filterCategory.value) filterCategory.value = ''
  fetchData()
}

function togglePending() {
  filterPending.value = !filterPending.value
  fetchData()
}

// ─── 名称检索 ───

async function searchCandidates(keyword: string) {
  const text = (keyword || '').trim()
  if (!text) {
    candidates.value = []
    candidateTotal.value = 0
    return
  }
  candidateLoading.value = true
  try {
    const res = await treasureApi.getLinkCandidates({ search: text })
    candidates.value = res.data.rows
    candidateTotal.value = res.data.total
  } catch {
    candidates.value = []
    candidateTotal.value = 0
  } finally {
    candidateLoading.value = false
  }
}

/**
 * 名称这一格变了。
 *
 * 🔴 两种来路必须分开处理：
 *   - 从候选里选中 ⇒ 建立关联（并带出类别建议、给状况提示）
 *   - 手工敲进来的 ⇒ **清掉旧关联**。留着它就会出现「档案名是手工写的、
 *     却关联着另一件东西」—— 界面看起来完全正常，而那时关联已经不成立了。
 *     ⚠️ 不做任何「按名字猜着关联」的兜底：那正是静默错值的经典来源。
 */
function onNameChanged(name: string) {
  const hit = candidates.value.find((c) => c.name === name)
  if (!hit) {
    form.property = null
    form.survival_item = null
    brokenHint.value = false
    return
  }
  if (hit.kind === 'property') {
    form.property = hit.id
    form.survival_item = null
  } else {
    form.survival_item = hit.id
    form.property = null
  }
  // 关联的必然是实物
  form.subject_kind = SUBJECT_KIND_PHYSICAL
  form.method_group = ''
  if (hit.suggest_category && !form.category) form.category = hit.suggest_category
  brokenHint.value = hit.condition === 'broken'
}

// ─── 表单 ───

function resetForm(type = '好') {
  form.record_type = type
  form.subject_kind = SUBJECT_KIND_PHYSICAL
  form.name = ''
  form.category = ''
  form.method_group = ''
  form.why_good = ''
  form.scene = ''
  form.still_available = true
  form.where_to_find = ''
  form.avoid_reason = ''
  form.consequence = ''
  form.tags = ''
  form.property = null
  form.survival_item = null
  candidates.value = []
  candidateTotal.value = 0
  brokenHint.value = false
}

function handleAddNew(type: string) {
  editingId.value = null
  resetForm(type)
  dialogVisible.value = true
}

/**
 * 切换记录对象 ⇒ 把**另一个维度的值清掉**（客户端先清一次）。
 *
 * ⚠️ 服务端还会再清一次（不指望客户端记得送空串）—— 两处都要写：
 *    服务端兜的是脚本调用与表单残留，客户端兜的是「折叠起来的那一格
 *    留着旧值，用户改完再展开会看到自相矛盾」。
 */
function onSubjectKindChange(kind: string) {
  if (kind === SUBJECT_KIND_METHOD) {
    form.category = ''
  } else {
    form.method_group = ''
  }
}

function openDetail(thing: GoodThing) {
  viewingItem.value = thing
  showDetailDialog.value = true
  // 关联事实只在详情接口下发（列表里对每条都算一次折旧是 N+1）
  treasureApi.getThingDetail(thing.id).then((res) => {
    if (viewingItem.value?.id === thing.id) viewingItem.value = res.data
  }).catch(() => { /* 取不到就保留列表里那份 */ })
}

function fillForm(thing: GoodThing) {
  editingId.value = thing.id
  form.record_type = thing.record_type
  form.subject_kind = thing.subject_kind || SUBJECT_KIND_PHYSICAL
  form.name = thing.name
  form.category = thing.category
  form.method_group = thing.method_group
  form.why_good = thing.why_good
  form.scene = thing.scene
  form.still_available = thing.still_available
  form.where_to_find = thing.where_to_find
  form.avoid_reason = thing.avoid_reason
  form.consequence = thing.consequence
  form.tags = thing.tags
  form.property = thing.property
  form.survival_item = thing.survival_item
  candidates.value = []
  candidateTotal.value = 0
  brokenHint.value = false
}

function openEdit(thing: GoodThing) {
  fillForm(thing)
  showDetailDialog.value = false
  dialogVisible.value = true
}

function editFromDetail() {
  const item = viewingItem.value
  if (item) openEdit(item)
}

async function handleSubmit() {
  if (!formRef.value) return
  // ⚠️ 类别那一条规则是**按记录对象动态生成**的，校验前先让它重算 ——
  //    否则「刚从方法切回实物」时还带着旧规则，会放过一个空类别
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const data: Record<string, unknown> = {
      record_type: form.record_type,
      subject_kind: form.subject_kind,
      name: form.name.trim(),
      method_group: form.method_group,
      scene: form.scene.trim(),
      tags: form.tags.trim(),
      property: form.property,
      survival_item: form.survival_item,
    }
    if (isPhysical.value) {
      data.category = form.category
    }
    if (form.record_type === '好') {
      data.why_good = form.why_good.trim()
    } else {
      data.avoid_reason = form.avoid_reason.trim()
      data.consequence = form.consequence.trim()
    }
    if (isPhysical.value) {
      data.still_available = form.still_available
      data.where_to_find = form.where_to_find.trim()
    }

    if (editingId.value) {
      await store.updateThing(editingId.value, data)
      ElMessage.success('已更新')
    } else {
      await store.createThing(data)
      ElMessage.success('已记录')
    }
    dialogVisible.value = false
    fetchData()
  } catch (err) {
    // 4xx 原样透出：「这件实物已经有一条评价了」这类是可行动的
    ElMessage.error(apiErrorText(err, '保存失败'))
  } finally {
    submitting.value = false
  }
}

async function handleDelete(thing: GoodThing) {
  try {
    await ElMessageBox.confirm(`确定删除"${maskText(thing.name)}"？`, '提示', { type: 'warning' })
    await store.deleteThing(thing.id)
    ElMessage.success('已删除')
    fetchData()
  } catch { /* cancelled */ }
}

function getTags(tags: string) {
  return tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : []
}

onMounted(async () => {
  await store.fetchMeta()
  // ⚠️ 必须 await：下面按 id 从 thingList 里找目标，列表没到位就永远找不到
  await fetchData()
  // ⭐ 「值得留」的现状：**不 await**（也不该挡住上面两件正事）——
  //     `useWorkKeep.load()` 内部已把失败吞成 `ready = false`（整个标记不渲染），
  //     它失败不该让列表页面跟着白屏。
  void loadKeeps()
  // 从物件资产的徽标跳过来（`?focus=<档案 id>`）⇒ 直接打开那一条去补理由
  const focus = route.query.focus
  if (focus) {
    const target = store.thingList.find((t) => t.id === Number(focus))
    if (target) openDetail(target)
  }
})
</script>

<style scoped lang="scss">
.treasure-hub {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .header-left { display: flex; align-items: center; gap: 12px;
    .page-title { margin: 0; font-size: 24px; font-weight: 600; }
  }
  .header-actions { display: flex; gap: 8px; }
}

.hub-alert { margin-bottom: 12px; }

.filter-card { margin-bottom: 12px;
  :deep(.el-card__body) { padding: 12px 16px; }
  .type-tabs, .category-tabs, .kind-tabs { display: flex; flex-wrap: wrap; gap: 4px; }
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.pending-btn { margin-left: auto; }

.reminder-card { margin-bottom: 12px;
  :deep(.el-card__body) { padding: 8px 12px; }
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.candidate-more {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.linked-preview {
  font-size: 12px;
  color: var(--el-color-success);
  line-height: 1.6;
}

.kind-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  width: 100%;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.detail-category { font-size: 14px; color: var(--el-text-color-secondary); }

.detail-linked {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 16px;

  .detail-linked__facts { margin-left: 8px; }
}

.detail-section { margin-bottom: 16px; }

.detail-label {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
  margin-bottom: 6px;

  &.bad { color: #cf1322; }
}

/*
 * 详情框只负责**盒子**（背景 / 内边距 / 左侧色条 / 基准字号），
 * 文本排版交给 `MarkdownText` —— 那里按「渲染 / 纯文本」分流。
 *
 * ⚠️ 这里的 `white-space: pre-wrap` 已撤：它属于「纯文本怎么显示」，
 *    是 `MarkdownText` 的 `--plain` 变体管的。留在这儿会让 Markdown 渲染出的
 *    HTML 也保留源码里的空白，段落之间凭空多出空行。
 * ⚠️ 也不写 markdown 的 `:deep()` 样式：那是第 2 份排版口径。
 */
.detail-text {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 6px;
  border-left: 3px solid var(--el-color-primary);
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.detail-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

/* ⚠️ 左侧这一组是**三个不同性质的东西**（值得留的勾 / 事实标签 / 待补出口），
   靠模板换行给的那一个空格不稳 ⇒ 显式 gap。 */
.detail-footer__left {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-time { font-size: 12px; color: var(--el-text-color-placeholder); }
</style>
