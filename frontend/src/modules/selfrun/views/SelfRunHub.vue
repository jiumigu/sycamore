<template>
  <div class="selfrun-hub" v-loading="store.loading">
    <!-- ── 页头 ────────────────────────────────────────────── -->
    <div class="page-header">
      <div class="header-left">
        <!-- 🔴 子页面里给一条**回得去**的路（页头最左）。
             v3.64.0 起自我运转不占侧边栏菜单项（入口是页头那个下拉），
             所以这条回程**更要紧**：少了它，点进「KPI 模板库」之后页面上
             再没有任何一处能回到「制定配置」的主视图，看着像「子页丢了」。 -->
        <el-button v-if="isSetupSub" link class="sh-back" @click="goSetupView('kpi')">
          <el-icon><ArrowLeft /></el-icon>制定配置
        </el-button>
        <!-- 🔴 标题**永远跟当前子页走**（与页签、页头入口下拉同字）。
             曾经在没有阶段时回落成模块名「自我运转」，结果是几个入口点下去
             连标题都一样 —— 看着就像「点哪个都一样」。 -->
        <h1 class="page-title">{{ pageTitle }}</h1>
        <!-- ⚠️ 账本页不显示这个状态标签：页头此刻说的是要看的那个**长阶段**，
             而 `stage` 指的是「正在跑的那个小阶段」—— 两者不是一回事，
             并排放在一行会被读成同一个阶段的两个状态。长阶段自己的状态在账本卡里。 -->
        <el-tag v-if="stage && !isLedger" size="small" :type="stageTagType" effect="plain">{{ stage.status_display }}</el-tag>
        <!-- 🔴 区间必须在页头：它下面每一块的数字都落在这一段里
             （「计入 2 周 + 2 残缺」就是阶段起于周中造成的）。
             曾经这里只印 `days_label`，而那时它的未开始分支是「未开始 · 11-01 起」
             —— 整页**只有起点、没有终点**。 -->
        <span v-if="stage && !isLedger" class="sh-sub">
          {{ stage.name }} · {{ stage.range_label }} · {{ stage.days_label }} · {{ stage.metric_count }} 条 KPI
        </span>
      </div>
      <div class="header-actions">
        <el-button v-if="heartbeat?.message && !isLedger" text size="small" @click="doHeartbeat">
          <el-icon><Bell /></el-icon>{{ heartbeat.message }}
        </el-button>
        <!-- 暂停/恢复是对「正在跑的那个阶段」的动作，账本页不提供：那页不碰 KPI，也不碰阶段状态 -->
        <el-button v-if="!isLedger && stage && stage.status === 'active'" size="small" @click="pauseVisible = true">
          暂停阶段
        </el-button>
        <el-button v-else-if="!isLedger && stage && stage.status === 'paused'" size="small" type="success" @click="doResume">
          恢复
        </el-button>
        <el-button size="small" @click="reload">刷新</el-button>
      </div>
    </div>

    <!-- ══ 阶段账本（长阶段详情页）══════════════════════════════════
         整页只讲一件事：钱 / 时间 / 作品 / 它下面的小阶段。
         🔴 它**不是页签里的第六格**：长阶段不产生 `SelfRunPeriod`，所以这一页
            没有「本周 / 本月 / 按期修订 / 归档周期」—— 那四件事一件都做不了，
            摆出页签只会让人点进去看到空。
         ⚠️ 与上面那 8 条路由指向同一个组件，但走的是 `v-if` 的另一支：
            页签整体不渲染（见下方 `<template v-else>`）。 -->
    <StageLedgerPanel v-if="isLedger" ref="ledgerRef" />

    <template v-else>
    <!-- ── 父级面包屑（阶段分两层之后，v3.64.19）───────────────
         🔴 走**显式路由**，禁 `router.back()`：从页头下拉直接进来时没有历史，
            `back()` 会把人送出模块（本项目老坑）。
         ⚠️ 只有在 `parent` 存在时才出现 —— 顶级阶段没有上级，
            印一句「属于：无」比不印更糊涂。 -->
    <div v-if="stage?.parent" class="sh-parent">
      <el-button link size="small" class="sh-parent-back" @click="goParent">
        <el-icon><ArrowLeft /></el-icon>返回「{{ stage.parent_name }}」
      </el-button>
      <span class="sh-parent-hint">这段路属于一个长阶段 —— 钱 / 时间 / 作品在那页汇总，这一页管 KPI</span>
    </div>

    <!-- ── 暂停横幅（休耕不是失败，用中性色）───────────────── -->
    <el-alert
      v-if="stage?.status === 'paused'" type="info" :closable="false" show-icon class="sh-banner"
      :title="`阶段暂停中（${PAUSE_REASON_LABEL[stage.pause_reason ?? 'other']}）`"
      :description="`自 ${stage.paused_since ?? '—'} 起${stage.resume_at ? `，预计 ${stage.resume_at} 恢复` : ''}。周期照常流转，归档时这一期判「休耕」—— 休耕不是失败。`"
    />

    <!-- ── 两把尺子**并列**（只有跑着阶段时才有读数）──────── -->
    <template v-if="stage">
      <div class="sh-rulers">
        <div
          v-for="r in rulers" :key="r.type"
          class="sh-ruler" :class="{ 'is-on': activeTab === r.type }"
          @click="goTab(r.type)"
        >
          <span class="sh-ruler-name">{{ r.label }}</span>
          <span class="sh-ruler-status" :style="{ color: r.color }">{{ r.statusText }}</span>
          <span class="sh-ruler-frac">{{ r.frac }}</span>
          <span class="sh-ruler-key">{{ r.key }}</span>
        </div>
      </div>
      <div class="sh-ruler-note">
        周量「有没有在动」，月量「动出结果没有」—— 两把尺子正交，任何一方掉下去都看得见。
      </div>
    </template>

    <!-- ══ 生命周期页签 ═══════════════════════════════════════
         页签与路由**同源**（`route.name` 的后缀）：从页头入口下拉进来，
         页签自己就停在正确那一格 —— 另存一份 ref 的话迟早分家，
         从下拉点「本月状态」进来却还停在上次点的「本周状态」，看着就像点错了。

         🔴 **每一格都是一个真页面**：没有阶段时，只有「制定配置」渲染向导，
            其余各页各自说清自己为什么空（见 EmptyPane），
            不让几个入口落到同一屏上。
         ⚠️ `lazy`：面板首次被切到才挂载（之后常驻，状态不丢）——
            否则一进页面 6 个面板会把接口全打一遍。
    -->
    <el-tabs v-model="activeTab" class="sh-tabs" @tab-click="onTabClick">
      <!-- ① 制定配置（T1）—— 生命周期的第一段，唯一能「从零开始」的地方。

           🔴 这一页是「配置总台」，**主视图只留一块**（用户 2026-10-13 二轮拍板）：
               正中 = 本阶段 KPI（即时生效）；
               另外三块（KPI 模板库 / 按期修订 / 配置变更留痕）**不再平铺**，
               改为从右侧三个入口点进**各自的子页面** —— 一屏只讲一件事，
               改完 KPI 也不用往下滚很远才找到留痕。
           ⚠️ 搬走的只是入口位置，不是内容：右侧每个入口都写清自己干什么、
              作用域是什么（三个匿名按钮等于没说）；子页页头最左还有返回「制定配置」。
           ⚠️ 「创建阶段」向导与「已收尾的阶段」**留在主视图** —— 它们不是那三块；
              而且没有阶段时，向导就是这一页唯一的出口（收起来 = 把出口藏了）。

           子页面（模板库 / 按期修订 / 配置变更留痕）：
           🔴 与主视图**共用同一个 tab、同一份页头** —— 切进来只换面板，
              页头那两把尺子、阶段状态、暂停按钮都不重建。
           ⚠️ `targets` 子页**无条件渲染**：没有阶段时它自己说明为什么空，
              不由父层替它藏起来（藏起来就变成「点了没反应」）。
           🚨 那三条 `v-else-if` 必须**紧贴**上面的 `<template v-if>`：
              中间不许插注释 —— 生产构建下编译器找不到相邻的 `v-if` 会直接报错。
      -->
      <el-tab-pane label="制定配置" name="setup" lazy>
        <!-- ── 主视图：本阶段 KPI（即时生效）＋ 右侧三个入口 ──────── -->
        <template v-if="setupView === 'kpi'">
          <!-- ① 无阶段时：**为什么空必须留在页面上说**（不许只塞进悬停气泡）——
               页面上没数据时，人不会特意去悬停一个问号找原因。
               这是「每页自陈为什么空」那条铁律在**主视图**的落点。 -->
          <el-alert
            v-if="!stage"
            class="sh-lead"
            type="info" :closable="false" show-icon
            title="还没有进行中的阶段"
            description="「自我运转」是给自己的运转留一份记录：周量「有没有在动」，月量「动出结果没有」。它不考核你 —— 它是仪式。"
          />

          <!-- ② 配置总台说明：**整张卡收进悬停气泡**（用户 2026-10-13 四轮拍板）。
              原来是一整张卡（标题行 + 一段说明 + 5 条作用域 + 一排按钮），竖向吃掉约 200px，
              而它上面有两把尺子、下面还有 KPI 表 —— 挤。

              🔴 锚点文字**不带「正在跑：某阶段」**：那句话页头一行之上已经写着
                 （`阶段名 · 第 N 天 · N 条 KPI`），搬到这一行就是同一条信息叠两遍 ——
                 本轮本来就是在去冗余，不能一边删一边加。
              🔴 **出口按钮不跟着收**：收进气泡等于把它埋了
                 （铁律：出口控件不得关闭自己）。两个按钮留在这一行右侧。
              ⚠️ 锚点必须**自带可悬停的样子**（问号图标 + 虚线下划线 + `cursor: help`）——
                 只把一句话压在光标下而不改样貌，等于没人知道这里能悬停。 -->
          <div class="sh-bar">
            <el-popover placement="bottom-start" :width="430" trigger="hover" :show-after="120">
              <template #reference>
                <span class="sh-bar-anchor">
                  <el-icon class="sh-bar-icon"><QuestionFilled /></el-icon>
                  <span>这一页怎么用</span>
                </span>
              </template>
              <!-- 🔴 正文写 `<b>`，**不许写 markdown 的 `**`** ——
                   它在 HTML 里不是加粗，是会**原样显示成两个星号**（本页原来就是这样）。 -->
              <div class="sh-tip">
                <p class="sh-tip-lead">
                  这一页是配置总台：正中间只留你正在跑的这一阶段 KPI，
                  另外三块（模板库 / 按期修订 / 变更留痕）从右边点进去 —— 三者作用域不同，别混。
                </p>
                <ul>
                  <li><b>本阶段 KPI</b>（本页）：改目标与底线<b>立刻生效、从现在起一直用</b>；退役 / 恢复单条。</li>
                  <li><b>KPI 模板库</b>（右侧）：KPI 的<b>起点库</b>（周 5 + 月 4 起步，可以自己加）—— 挑进阶段时值会被抄走，此后改模板不影响已建阶段。</li>
                  <li><b>按期修订</b>（右侧）：每周 / 每月都可以改<b>下一周、下一月</b>的目标（只改一期，或从这一期起一直用）。</li>
                  <li><b>配置变更留痕</b>（右侧）：谁在什么时候把哪一条改成了什么 —— 包括「哪一期换过尺子」。</li>
                  <li><b>执行 / 复盘</b>：「本周状态」随时看、手工项随时补记；你觉得该收口了就手动归档，<b>归档那刻数字定格</b>。</li>
                </ul>
              </div>
            </el-popover>

            <div class="sh-bar-actions">
              <el-button v-if="!stage" type="primary" size="small" @click="startWizard">开始配置 KPI</el-button>
              <template v-else>
                <el-button size="small" @click="goTab('week')">去看本周状态</el-button>
                <el-button size="small" @click="goTab('summary')">去收尾这个阶段</el-button>
              </template>
            </div>
          </div>

          <!-- 创建阶段：折叠面板。没有阶段时**默认展开**（那是唯一该做的事），
               有阶段时收起（减少干扰，且它此时开不了第二个） -->
          <el-collapse v-model="openPanels" class="sh-collapse">
            <el-collapse-item name="wizard">
              <template #title>
                <div class="sh-collapse-head">
                  <span class="sh-collapse-title">
                    {{ stage ? '开一个新阶段' : '从零开一个新阶段' }}
                  </span>
                  <span v-if="stage" class="sh-hint">
                    同一时间每个长阶段下只能跑一个小阶段 —— 要开下一段，先收尾当前这个
                  </span>
                </div>
              </template>
              <SetupWizard ref="wizardRef" @created="reload" />
            </el-collapse-item>
          </el-collapse>

          <el-card v-if="closedStages.length" shadow="never" class="sh-gap">
            <template #header><span class="sh-card-title">已收尾的阶段</span></template>
              <el-table :data="closedStages" size="small">
                <el-table-column prop="name" label="阶段" min-width="140" />
                <!-- 分层之后这张表里既有顶级阶段也有小阶段 —— 不给上级列就分不出谁是谁 -->
                <el-table-column label="上级阶段" width="140">
                  <template #default="{ row }">{{ row.parent_name ?? '—（顶级）' }}</template>
                </el-table-column>
              <el-table-column label="区间" width="240">
                <template #default="{ row }">{{ row.range_label }}</template>
              </el-table-column>
              <el-table-column label="KPI" width="80">
                <template #default="{ row }">{{ row.metric_count }} 条</template>
              </el-table-column>
              <el-table-column label="操作" width="140">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click="copyFrom(row)">用它开新阶段</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- ── 主区（左）：本阶段 KPI ＋ 三个入口（右）────────── -->
          <div class="sh-setup-grid">
            <div class="sh-setup-main">
              <StageMetricPanel v-if="stage" @changed="onChanged" />
              <el-alert
                v-else
                type="info" :closable="false" show-icon
                title="还没有进行中的阶段 —— 这一块会列出它的 KPI"
                description="先在上面「从零开一个新阶段」里开一个、挑几条 KPI 进来，这块就有内容了。"
              />
            </div>

            <aside class="sh-setup-side">
              <div class="sh-side-title">配置的另外三块</div>
              <div class="sh-side-note">作用域各不相同，别混 —— 点进去各自一页。</div>

              <el-button class="sh-entry" @click="goSetupView('templates')">
                <span class="sh-entry-row">
                  <span class="sh-entry-name">KPI 模板库</span>
                  <span class="sh-entry-badge">{{ store.templates.length }} 条</span>
                </span>
                <span class="sh-entry-desc">起点库：增 / 删 / 改 KPI 模板，都落库</span>
              </el-button>

              <el-button class="sh-entry" @click="goSetupView('targets')">
                <span class="sh-entry-row">
                  <span class="sh-entry-name">按期修订</span>
                </span>
                <span class="sh-entry-desc">改下一周 / 下一月的目标（只改一期，或从这期起一直用）</span>
              </el-button>

              <el-button class="sh-entry" @click="goSetupView('logs')">
                <span class="sh-entry-row">
                  <span class="sh-entry-name">配置变更留痕</span>
                  <span class="sh-entry-badge">{{ store.logs.length }} 条</span>
                </span>
                <span class="sh-entry-desc">每次改动一行，含「哪一期换过尺子」</span>
              </el-button>
            </aside>
          </div>
        </template>

        <TemplateLibrary v-else-if="setupView === 'templates'" />
        <PeriodTargetsPanel v-else-if="setupView === 'targets'" @changed="onChanged" />
        <ConfigChangeLog v-else-if="setupView === 'logs'" />
      </el-tab-pane>

      <!-- ②③ 本周 / 本月（T2）—— 两把正交的尺子，各占一格 -->
      <el-tab-pane label="本周状态" name="week" lazy>
        <PeriodPanel v-if="stage" period-type="weekly" :editable="editable" @changed="onChanged" />
        <EmptyPane v-else :title="empty.week.title" :desc="empty.week.desc" />
      </el-tab-pane>
      <el-tab-pane label="本月状态" name="month" lazy>
        <PeriodPanel v-if="stage" period-type="monthly" :editable="editable" @changed="onChanged" />
        <EmptyPane v-else :title="empty.month.title" :desc="empty.month.desc" />
      </el-tab-pane>

      <!-- ④ 历史复盘（T3）—— 🔴 **不需要阶段**：
           它读的是「已归档的周期」，而归档过的周期跟现在有没有阶段在跑无关
           （上一阶段收尾之后，这里仍然该看得到它留下的那些期）。 -->
      <el-tab-pane label="历史复盘" name="review" lazy>
        <ReviewPanel @changed="onChanged" />
      </el-tab-pane>

      <!-- ⑤ 阶段总结（T4）—— 深层页，不占菜单项 -->
      <el-tab-pane label="阶段总结" name="summary" lazy>
        <StageSummaryPanel v-if="stage" @changed="onChanged" />
        <EmptyPane v-else :title="empty.summary.title" :desc="empty.summary.desc" />
      </el-tab-pane>
    </el-tabs>
    </template>

    <!-- ── 暂停弹窗 ─────────────────────────────────────────── -->
    <el-dialog v-model="pauseVisible" title="暂停整个阶段（休耕）" width="440px">
      <el-form label-width="90px">
        <el-form-item label="为什么停">
          <el-select v-model="pauseForm.reason" style="width: 100%">
            <el-option v-for="(l, k) in PAUSE_REASON_LABEL" :key="k" :label="l" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="预计恢复">
          <el-date-picker v-model="pauseForm.resume_at" type="date" value-format="YYYY-MM-DD" clearable />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="pauseForm.note" maxlength="200" />
        </el-form-item>
      </el-form>
      <el-alert
        type="info" :closable="false" show-icon
        title="暂停只是「先不记账」，不是「放弃」"
        description="周期照常流转，归档时这一期判「休耕」（中性灰，明显区别于「没做到」）。想记的还是能记。"
      />
      <template #footer>
        <el-button @click="pauseVisible = false">取消</el-button>
        <el-button type="primary" :loading="pausing" @click="doPause">暂停</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { TabsPaneContext } from 'element-plus'
import { ArrowLeft, Bell, QuestionFilled } from '@element-plus/icons-vue'
import PeriodPanel from './PeriodPanel.vue'
import PeriodTargetsPanel from './PeriodTargetsPanel.vue'
import ReviewPanel from './ReviewPanel.vue'
import StageSummaryPanel from './StageSummaryPanel.vue'
import StageLedgerPanel from './StageLedgerPanel.vue'
import SetupWizard from './SetupWizard.vue'
import ConfigChangeLog from '../components/ConfigChangeLog.vue'
import EmptyPane from '../components/EmptyPane.vue'
import StageMetricPanel from '../components/StageMetricPanel.vue'
import TemplateLibrary from '../components/TemplateLibrary.vue'
import * as api from '../api/selfrunApi'
import { useSelfRunStore } from '../stores/selfrunStore'
import {
  FALLBACK_COLOR, MONTHLY_QUESTION_COUNT, PAUSE_REASON_LABEL, periodStatusLabel,
} from '../types/selfrunTypes'
import type { SelfRunStage } from '../types/selfrunTypes'

const store = useSelfRunStore()
const route = useRoute()
const router = useRouter()

/** 「制定配置」这一格里的四种面孔：主视图 + 三个页内子页面 */
type SetupView = 'kpi' | 'templates' | 'targets' | 'logs'

/** 路由名 → 页签名。8 条子路由指向**同一个组件**，
 *  所以「现在在哪一页」只有一个真源：路由。
 *  ⚠️ 原来自带第 6 条「设置」（与本页的「本阶段 KPI」完全重复）—— 已删。
 *  ⚠️ 「制定配置」的三个页内子页面也映射回 `setup` ——
 *     点进去时页签仍亮「制定配置」（那是它们的父页）。 */
const TAB_OF_ROUTE: Record<string, string> = {
  'selfrun-setup': 'setup',
  'selfrun-setup-templates': 'setup',
  'selfrun-setup-targets': 'setup',
  'selfrun-setup-logs': 'setup',
  'selfrun-week': 'week',
  'selfrun-month': 'month',
  'selfrun-review': 'review',
  'selfrun-summary': 'summary',
}

/** 路由名 → 「制定配置」里的哪一种面孔（主视图 / 三块之一） */
const SETUP_VIEW_OF_ROUTE: Record<string, SetupView> = {
  'selfrun-setup': 'kpi',
  'selfrun-setup-templates': 'templates',
  'selfrun-setup-targets': 'targets',
  'selfrun-setup-logs': 'logs',
}

/** 反查表：按钮点下去推哪个路由名。走**路由名**不走路径字面量（路径改了不用跟着改） */
const ROUTE_OF_SETUP_VIEW: Record<SetupView, string> = {
  kpi: 'selfrun-setup',
  templates: 'selfrun-setup-templates',
  targets: 'selfrun-setup-targets',
  logs: 'selfrun-setup-logs',
}

/**
 * 页签与路由**共用同一个真源**。
 *
 * 🔴 刻意不另存一个 `ref` —— 两份状态迟早分家：从侧边栏点「本月状态」进来，
 *    页签却还停在上一次点的「本周状态」，看着就像点错了。
 * ⚠️ 路由名不在表里时（例如直接敲 `/selfrun`，会被重定向到 `selfrun-week`）回落到「本周状态」。
 */
const activeTab = computed({
  get: () => TAB_OF_ROUTE[String(route.name ?? '')] ?? 'week',
  set: (v: string) => goTab(v),
})

/** 「制定配置」里当前是哪一种面孔 —— 同样只读路由，不另存 ref */
const setupView = computed<SetupView>(
  () => SETUP_VIEW_OF_ROUTE[String(route.name ?? '')] ?? 'kpi',
)
/** 正处在三个子页面之一（页头据此给出「回制定配置」的路） */
const isSetupSub = computed(() => setupView.value !== 'kpi')

/**
 * 现在在「阶段账本」那一页（长阶段详情）。
 *
 * 🔴 这一页与其余 8 条路由**不是同一类**：它不渲染页签、不出两把尺子。
 *    判据只读路由名 —— 另存一个 ref 就会和地址栏分家（从下拉点进来还停在上次的页）。
 */
const isLedger = computed(() => route.name === 'selfrun-stage')

/** 账本面板的刷新入口（页头那个「刷新」按钮转给它，两处各刷各的必然有一半是旧的） */
const ledgerRef = ref<InstanceType<typeof StageLedgerPanel> | null>(null)

const closedStages = ref<SelfRunStage[]>([])
const wizardRef = ref<InstanceType<typeof SetupWizard> | null>(null)
const pauseVisible = ref(false)
const pausing = ref(false)
const pauseForm = ref({ reason: 'fallow', resume_at: '', note: '' })

/**
 * 「创建阶段」折叠面板的展开态。
 *
 * 🔴 **没有阶段时默认展开** —— 那时「开一个阶段」是唯一该做的事，
 *    收起来等于把唯一的入口藏了（页面上就只剩模板库，读起来像「功能没做」）。
 *
 * 🚨 初值**不能在这里取** —— 组件创建时 `store.stage` 还是 `null`（阶段是
 *    `reload()` 异步拉回来的），写成 `ref(store.stage ? [] : ['wizard'])`
 *    会让有阶段时也**永远展开**（初值算错了，之后再没人纠正它）。
 *    所以：先空着，等首次拿到阶段后在 `reload()` 里定一次；定过就不再插手
 *    （用户自己点开/收起，别去覆盖他）。
 */
const openPanels = ref<string[]>([])
let panelSeeded = false
/** 「从账本跳过来开小阶段」只自动展开一次 —— 之后用户自己收起，不再覆盖他 */
let fromLedgerHandled = false

const stage = computed(() => store.stage)
const heartbeat = computed(() => store.heartbeatInfo)
/** 归档后的周期一律只读（补记、跳过都不给） */
const editable = computed(() => !!stage.value && stage.value.status !== 'closed')

/**
 * 标题**永远**跟当前子页走 —— 与侧边栏菜单项同字。
 * ⚠️ 不许再按「有没有阶段」回落成模块名：那会让没有阶段时的三页
 *    连标题都一样（用户报的「点三个菜单跳的都是同一个页面」）。
 * ⚠️ 子页面（模板库 / 按期修订 / 变更留痕）的标题也走这里 ——
 *    于是页头天然读成「制定配置 › KPI 模板库」（左边那个回退按钮就是「›」）。
 */
const pageTitle = computed(() => (route.meta.title as string | undefined) || '自我运转')

/** 切子页 = 走路由（不另存状态）。页签、页头两把尺子、空态里的按钮都走这一条。 */
function goTab(tab: string) {
  const name = `selfrun-${tab}`
  if (route.name !== name) router.push({ name })
}

/** 进「制定配置」的某一种面孔（主视图 / 三块之一） —— 右侧入口与页头返回都走这一条 */
function goSetupView(v: SetupView) {
  const name = ROUTE_OF_SETUP_VIEW[v]
  if (route.name !== name) router.push({ name })
}

/**
 * 回上级阶段（长阶段）的账本页。
 *
 * 🔴 显式带 `id`：账本页不带 id 时会取「正在跑的那个长阶段」，
 *    而一个已收尾的长阶段**不是**「正在跑的」—— 不带 id 的返回会跳到另一段路上。
 */
function goParent() {
  const pid = stage.value?.parent
  if (!pid) return
  router.push({ name: 'selfrun-stage', params: { id: String(pid) } })
}

/**
 * 🔴 已经在子页面里，再点「制定配置」页签 = **退回主视图**。
 *
 * 少了这一步就是「点了没反应」：那三个子页面的路由也映射到 `setup`，
 * 所以「制定配置」这个页签**本来就是点亮的** —— `v-model` 收不到 set，
 * 于是一个字都不会变。用户唯一能出去的路只剩侧边栏（还得先跳到别处再跳回来）。
 */
function onTabClick(pane: TabsPaneContext) {
  if (String(pane.paneName) === 'setup' && isSetupSub.value) goSetupView('kpi')
}

/**
 * 各页「为什么还是空的」。**每页一句不同的话** ——
 * 说清这一页要等什么才有内容（周/月还各自带上「当期是哪一期」）。
 * 🔴 当期标识来自后端（`store.weekly.key`），前端不自己算 ISO 周。
 */
const empty = computed(() => {
  const w = store.weekly
  const m = store.monthly
  const wLabel = w.key ? `（${w.key}${w.start ? ` · 自 ${w.start} 起` : ''}）` : ''
  const mLabel = m.key ? `（${m.key}${m.start ? ` · 自 ${m.start} 起` : ''}）` : ''
  return {
    week: {
      title: `本周${wLabel}还没有可量的东西`,
      desc: '要看到读数，先开一个阶段、挑几条 KPI —— 开通之后这一页自动有内容，不用再回来点。',
    },
    month: {
      title: `本月${mLabel}还没有可量的东西`,
      desc: '月这把尺量的是「动出结果没有」（收入验证、内容输出、资产盘点），与「本周」那把正交，各看各的。',
    },
    summary: {
      title: '还没有可以总结的阶段',
      desc: '阶段总结读的是归档时冻住的结论，所以要等一个阶段收尾之后才有内容 —— 它不会替你写，只把你写的与数字摆在一起。',
    },
  }
})

/**
 * 空态卡片上那个显式入口：**先展开折叠面板**，再滚到向导、把光标放进「阶段名称」。
 * ⚠️ 少了「展开」这一步就是「点了没反应」—— 面板收着的时候里面根本没有 DOM。
 */
function startWizard() {
  openPanels.value = ['wizard']
  panelSeeded = true          // 用户已经手动开过 ⇒ 之后不再由 `reload` 改它
  nextTick(() => wizardRef.value?.focusStart())
}

const stageTagType = computed(() => {
  const s = stage.value
  if (!s) return 'info'
  if (s.status === 'paused') return 'warning'
  // 🔴 `active` 但还没到起点 ⇒ 中性色：此时文案是「未开始」，
  //    上绿色会被读成「已经在跑了」。
  if (s.status === 'active') return s.elapsed_days > 0 ? 'success' : 'info'
  return 'info'
})

/** 月度这格的分数：三问几比几（**不显示 KPI 达标数** —— 那不是判定依据） */
const monthlyFrac = computed(() => {
  const ex = store.monthly.explain
  if (!ex) return '—'
  const total = ex.monthly_question_count ?? MONTHLY_QUESTION_COUNT
  if (ex.awaiting_answers) return `三问 0/${total} 未答`
  return `三问 ${ex.yes ?? 0}/${total}`
})

/** 两把尺子**并列**显示在页头（不是藏在 tab 里 —— 藏起来就会只看一边）
 *
 * 🔴 每格的分母**必须与本格档位同源**（v3.64.6）：
 *    周 = `达标 ok / 计入 counted`（KPI 尺子）；
 *    月 = `三问 yes / 3`（三问尺子）。
 *    原来月度也写 `达标 4/4`，而档位来自三问 2/3 —— 同一格里 100% 配「合格」，
 *    读起来就是「4/4 才合格」。两把尺子的数不许并排放。
 */
const rulers = computed(() => [
  {
    type: 'week',
    label: '本周',
    statusText: store.weekly.explain?.label_text
      || viewStatusText(store.weekly.explain?.value, 'weekly'),
    frac: store.weekly.explain ? `达标 ${store.weekly.explain.ok}/${store.weekly.explain.counted}` : '—',
    key: store.weekly.period?.period_key || store.weekly.key || '—',
    color: store.colors.period[store.weekly.explain?.value ?? ''] ?? FALLBACK_COLOR,
  },
  {
    type: 'month',
    label: '本月',
    statusText: store.monthly.explain?.label_text
      || viewStatusText(store.monthly.explain?.value, 'monthly'),
    frac: monthlyFrac.value,
    key: store.monthly.period?.period_key || store.monthly.key || '—',
    color: store.colors.period[store.monthly.explain?.value ?? ''] ?? FALLBACK_COLOR,
  },
])

function viewStatusText(v?: string, periodType?: string) {
  if (!v) return '—'
  return periodStatusLabel(v, periodType)
}

async function reload() {
  await store.bootstrap()
  // 首次拿到阶段之后，才定折叠面板的初值（见 `openPanels` 上的说明）
  if (!panelSeeded) {
    openPanels.value = store.stage ? [] : ['wizard']
    panelSeeded = true
  }
  // 从长阶段账本「+ 开下一个小阶段」进来（带 `?parent=`）：
  // 🔴 必须把向导**展开并滚过去** —— 折叠面板在有阶段时默认收起，
  //    不展开的话跳过来只看到一片主视图，读起来就是「那个按钮没反应」。
  if (!fromLedgerHandled && route.query.parent) {
    fromLedgerHandled = true
    startWizard()
  }
  // 账本页：只刷账本，**不做握手** —— 握手是「我回来看这一周了」的仪式，
  // 而账本讲的是这段路，不是这一周。
  // ⚠️ 但 `bootstrap()` / 模板库 / 已收尾阶段这三样照拉：页签随时可能被切走，
  //    只拉一半的话切过去就是「没有阶段」「模板 0 条」——静默的空。
  if (isLedger.value) {
    await ledgerRef.value?.refresh()
  } else {
    // 回访即握手（**不判好坏、不改任何 KPI**，同一天最多写一次）
    try {
      await api.heartbeat(true)
      await store.loadPeriod('weekly')
    } catch {
      // 握手失败不该影响页面
    }
  }
  // 模板库：**每页都要有一份**（向导第 2 步、模板库子页、
  // 主视图右侧那个「N 条」角标共用同一份）
  try {
    await store.loadTemplates()
  } catch {
    // 拉不到模板不该把整页带崩：子页会显示空表 + 新建入口
  }
  try {
    const res = await api.listStages({ status: 'closed' })
    closedStages.value = res.data
  } catch {
    closedStages.value = []
  }
}

function onChanged() {
  reload()
}

async function doPause() {
  pausing.value = true
  try {
    await store.pause({
      reason: pauseForm.value.reason,
      resume_at: pauseForm.value.resume_at || undefined,
      note: pauseForm.value.note || undefined,
    })
    pauseVisible.value = false
    ElMessage.success('已暂停 —— 周期照常流转')
    onChanged()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '暂停失败')
  } finally {
    pausing.value = false
  }
}

async function doResume() {
  try {
    await store.resume()
    ElMessage.success('已恢复')
    onChanged()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '恢复失败')
  }
}

async function doHeartbeat() {
  try {
    await api.heartbeat(true)
    await store.loadPeriod('weekly')
  } catch {
    // 忽略
  }
}

/**
 * 拿已收尾阶段的配置开新阶段。
 *
 * 🔴 后端只会「复制 config」，历史 `Period` / `Checkin` **一律不复制**，
 *    指纹也必然不同（算入了 `stage.id`）—— 必须在界面上说清「目标值还是上一阶段的」，
 *    否则你改了目标之后会以为「我变差了」，实际是尺子换了。
 */
async function copyFrom(s: SelfRunStage) {
  let name = ''
  try {
    const r = await ElMessageBox.prompt(
      `会复制「${s.name}」的 KPI 清单、口径与双档 —— 但目标值仍然是上一阶段的，请逐条重设。\n历史结论不会复制（它永远跟着原阶段）。`,
      '用什么名字开新阶段？',
      {
        confirmButtonText: '复制并生效', cancelButtonText: '算了', type: 'warning',
        inputValue: `${s.name}（新）`,
        inputValidator: (v: string) => (!!v && !!v.trim()) || '名称不能为空',
      },
    )
    name = r.value
  } catch {
    return
  }
  try {
    const res = await api.copyStage({ from_stage_id: s.id, name: name.trim() })
    ElMessage.success(res.data.note || '已开新阶段')
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '复制失败')
  }
}

onMounted(reload)
</script>

<style scoped>
.selfrun-hub { padding: 20px; }

.page-header {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; flex-wrap: wrap; margin-bottom: 16px;
}
.header-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.page-title { margin: 0; font-size: 24px; font-weight: 600; }
.sh-sub { font-size: 13px; color: var(--el-text-color-secondary); }
.header-actions { display: flex; align-items: center; gap: 8px; }
.sh-banner { margin-bottom: 12px; }

/* 子页面页头最左那条「回制定配置」—— 做小、压暗，别跟标题抢 */
.sh-back { font-size: 13px; color: var(--el-text-color-secondary); }
.sh-back:hover { color: var(--el-color-primary); }

/* 父级面包屑：一行「返回上级」+ 一句它为什么在这
   ⚠️ 与 `.sh-back` 同一档视觉（小、压暗）：这是**回程**，不是主操作。 */
.sh-parent {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin-bottom: 10px;
}
.sh-parent-back { font-size: 13px; color: var(--el-text-color-secondary); }
.sh-parent-back:hover { color: var(--el-color-primary); }
.sh-parent-hint { font-size: 12px; color: var(--el-text-color-placeholder); }

/* 无阶段时那条「为什么空」—— 它留在页面上，不进气泡 */
.sh-lead { margin: 14px 0 0; }
.sh-gap { margin-top: 14px; }

/* ── 配置总台的一条压扁说明（正文在悬停气泡里）─────────────────
   原来是一整张卡（竖向约 200px），现在一行 ≈ 40px。 */
.sh-bar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap;
  margin-top: 14px; padding: 8px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px; background: var(--el-bg-color);
}
/* 🔴 锚点要**看得出来能悬停**：问号图标 + 虚线下划线 + `cursor: help`。
   只把一句话压在光标下而不改样貌，等于没人知道这里能悬停。 */
.sh-bar-anchor {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--el-text-color-regular);
  cursor: help;
  border-bottom: 1px dashed var(--el-border-color);
}
.sh-bar-anchor:hover { color: var(--el-color-primary); border-bottom-color: var(--el-color-primary); }
.sh-bar-icon { color: var(--el-text-color-placeholder); }
.sh-bar-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

/* 气泡里的正文。
   ⚠️ 它在 `el-popover` 的默认插槽里、会被 teleport 到 `body` —— 但元素是在**本组件**
      的模板里编译的，仍带本组件的 scope id ⇒ scoped 样式照常命中。
   ⚠️ 气泡**外壳**（`.el-popper`）是 EP 自己的元素、没有 scope id ⇒
      宽度只能靠 popover 的 `:width` 给，不要在这里写。 */
.sh-tip { font-size: 12px; line-height: 1.85; color: var(--el-text-color-regular); }
.sh-tip-lead { margin: 0 0 6px; color: var(--el-text-color-secondary); }
.sh-tip ul { margin: 0; padding-left: 18px; }
.sh-tip li + li { margin-top: 4px; }
.sh-tip b { color: var(--el-text-color-primary); }

.sh-rulers { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.sh-ruler {
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
  padding: 12px 16px; border-radius: 10px; cursor: pointer;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  transition: border-color .15s, background .15s;
}
.sh-ruler.is-on { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.sh-ruler-name { font-size: 13px; color: var(--el-text-color-secondary); }
.sh-ruler-status { font-size: 18px; font-weight: 700; }
.sh-ruler-frac { font-size: 12px; color: var(--el-text-color-regular); }
.sh-ruler-key { margin-left: auto; font-size: 12px; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.sh-ruler-note { font-size: 12px; color: var(--el-text-color-secondary); margin: 8px 0 4px; }

.sh-tabs { margin-top: 4px; }
.sh-card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.sh-card-title { font-weight: 600; }
.sh-hint { font-size: 12px; color: var(--el-text-color-secondary); }

/* 「创建阶段」折叠面板：它自己就是一张卡（里面装着向导），别让它裸躺在页面上 */
.sh-collapse {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 0 14px;
  background: var(--el-bg-color);
}
.sh-collapse :deep(.el-collapse-item__content) { padding-bottom: 14px; }
.sh-collapse-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sh-collapse-title { font-weight: 600; }

/* ── 主视图：主区（本阶段 KPI）＋ 右侧三个入口 ───────────── */
.sh-setup-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 14px; align-items: start;
  margin-top: 14px;
}
.sh-setup-main { min-width: 0; }
.sh-setup-side { display: flex; flex-direction: column; gap: 8px; }
.sh-side-title { font-weight: 600; font-size: 13px; }
.sh-side-note { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }

/* 🔴 入口做成**两行**（名字 + 干什么）：只有一个名字的话，
   三个按钮等于三个需要自己猜的词。
   🚨 Element Plus 的按钮会把 slot 再包进**它自己的一个 `<span>`**，而那层 span 是
      `inline-flex` 横排 —— 所以 `flex-direction: column` 只加在按钮上**不生效**
      （按钮只有一个孩子，就是那层包装 span），结果是「名字」和「说明」挤在一行、
      名字被压得折成两行（实测：「KPI 模板库」断成「KPI 模板 / 库」）。
      必须把那层包装 span 一起掰成竖排。
   ⚠️ 那层 span 由 EP 渲染、**没有本组件的 scope id** ⇒ 只能走 `:deep(> span)`。 */
.sh-entry {
  display: flex; flex-direction: column; align-items: stretch;
  gap: 2px; width: 100%; height: auto;
  padding: 10px 12px; text-align: left;
  white-space: normal; line-height: 1.5;
}
.sh-entry :deep(> span) {
  display: flex; flex-direction: column; align-items: stretch;
  gap: 2px; width: 100%; white-space: normal; text-align: left;
}
/* ⚠️ Element Plus 给相邻按钮加了 `margin-left` —— 这里是竖排，得清掉 */
.sh-setup-side .sh-entry + .sh-entry { margin-left: 0; }
.sh-entry-row { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.sh-entry-name { font-weight: 600; white-space: nowrap; }
.sh-entry-badge { font-size: 12px; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.sh-entry-desc { display: block; font-size: 12px; color: var(--el-text-color-secondary); }

@media (max-width: 900px) {
  .sh-rulers { grid-template-columns: 1fr; }
}
@media (max-width: 1100px) {
  /* 窄屏：右侧入口落到下方（仍然是一列按钮，不是平铺的三张卡） */
  .sh-setup-grid { grid-template-columns: 1fr; }
  .sh-setup-side { order: 2; }
}
</style>
