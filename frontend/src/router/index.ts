import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import Dashboard from '@/core/dashboard/views/Dashboard.vue'
import BookView from '@/modules/book/views/BookView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },

  // 仪表盘
  { path: '/dashboard', name: 'dashboard', component: Dashboard, meta: { title: '仪表盘' } },
  { path: '/summary', name: 'summary', component: () => import('@/modules/summary/views/SummaryDashboard.vue'), meta: { title: '汇总总览' } },
  { path: '/summary/profile', name: 'summary-profile', component: () => import('@/modules/summary/views/PersonalProfile.vue'), meta: { title: '个人画像' } },

  // 收件箱
  { path: '/inbox', name: 'inbox', component: () => import('@/modules/inbox/views/InboxDashboard.vue'), meta: { title: '收件箱' } },

  // 作品（v3.62.0）：一件从经历里长出来、以后还能再用的东西。
  // ⚠️ 挂在**总览**组而不是新开顶级分组 —— 它是「你留下了什么」的结果页，
  //    与「汇总总览」量的是同一件事的两面（那边量做了多少，这边量留下什么）。
  // ⚠️ 它和「自我运转」的接合点只有一处：KPI「留下件数」的取数器读它。
  //    打勾的七个入口（里程碑 / 收件箱 / 读书 / 日记 / 摘录 / AI 问答 / 档案馆）
  //    都在**各自**的页面里 —— 本页只做收口（`WorkCapture` 是那个唯一的勾）。
  { path: '/works', name: 'works', component: () => import('@/modules/works/views/WorkView.vue'), meta: { title: '作品' } },

  // 时间感知
  {
    path: '/temporal/daily',
    name: 'temporal-daily',
    component: () => import('@/modules/temporal/views/TemporalView.vue'),
    meta: { title: '日记流' },
  },
  {
    path: '/temporal',
    name: 'temporal-stats',
    component: () => import('@/modules/temporal/views/TimeStatsView.vue'),
    meta: { title: '时间统计' },
  },
  {
    path: '/temporal/schedule',
    name: 'schedule',
    component: () => import('@/modules/temporal/views/ScheduleView.vue'),
    meta: { title: '日程视图' },
  },
  {
    path: '/temporal/mapping',
    name: 'temporal-mapping',
    component: () => import('@/modules/temporal/components/MappingEditor.vue'),
    meta: { title: '映射编辑器' },
  },
  {
    path: '/temporal/tasks',
    name: 'temporal-tasks',
    component: () => import('@/modules/temporal/views/TaskListView.vue'),
    meta: { title: '时间任务清单' },
  },

  // 目标与项目
  { path: '/temporal/contrib', name: 'temporal-contrib', component: () => import('@/modules/temporal/views/contrib/TemporalContribView.vue'), meta: { title: '时间贡献图' } },
  { path: '/temporal/oneday/contrib', name: 'oneday-contrib', component: () => import('@/modules/temporal/views/contrib/OnedayContribView.vue'), meta: { title: '日记流贡献图' } },
  { path: '/goals', name: 'goals', component: () => import('@/modules/goals/views/GoalHub.vue'), meta: { title: '人生目标' } },
  { path: '/goals/dimension-chart', name: 'DimensionChart', component: () => import('@/modules/goals/views/DimensionChart.vue'), meta: { title: '人生维度分布' } },
  { path: '/output', name: 'output', component: () => import('@/modules/output/views/OutputDashboard.vue'), meta: { title: '个人良品率' } },
  {
    path: '/reward',
    redirect: '/reward/pool',
    meta: { title: '快乐银行' },
    children: [
      {
        path: 'pool',
        name: 'reward',
        component: () => import('@/modules/reward/views/RewardPoolView.vue'),
        meta: { title: '奖励池' },
      },
      {
        path: 'gifts',
        name: 'reward-gifts',
        component: () => import('@/modules/reward/views/GiftListView.vue'),
        meta: { title: '礼物清单' },
      },
    ],
  },

  // 身心健康
  {
    path: '/health',
    redirect: '/health/dashboard',
    meta: { title: '健康管理' },
    children: [
      {
        path: 'dashboard',
        name: 'health',
        component: () => import('@/modules/health/views/HealthDashboard.vue'),
        meta: { title: '健康管理' },
      },
      {
        path: 'overview',
        name: 'health-overview',
        component: () => import('@/modules/health/views/overview/HealthOverviewView.vue'),
        meta: { title: '生命步数总览' },
      },
      {
        // 旧的「里程碑地图」页已并入总览页（v3.62.15）—— 留一条软着陆，
        // 免得旧书签 / 历史记录撞 404。内容没丢，只是换了住址。
        path: 'milestones',
        redirect: '/health/overview',
      },
      {
        path: 'weight',
        name: 'health-weight',
        component: () => import('@/modules/health/views/weight/WeightDashboard.vue'),
        meta: { title: '体重管理' },
      },
      {
        path: 'menstrual',
        name: 'health-menstrual',
        component: () => import('@/modules/health/views/MenstrualView.vue'),
        meta: { title: '好朋友跟踪' },
      },
    ],
  },
  { path: '/health/contrib', name: 'health-contrib', component: () => import('@/modules/health/views/contrib/HealthContribView.vue'), meta: { title: '健康贡献图' } },
  { path: '/dance', name: 'dance', component: () => import('@/modules/dance/views/DanceView.vue'), meta: { title: '舞蹈记录' } },

  // 精神滋养
  { path: '/nourishment', name: 'nourishment', component: () => import('@/modules/sugar/views/SugarView.vue'), meta: { title: '精神花园' } },
  { path: '/books', name: 'books', component: BookView, meta: { title: '书籍阅读' } },
  { path: '/books/charts', name: 'books-charts', component: () => import('@/modules/book/views/BookChartView.vue'), meta: { title: '阅读图形分析' } },
  { path: '/sugar', name: 'sugar', component: () => import('@/modules/sugar/views/SugarView.vue'), meta: { title: '小确幸' } },
  { path: '/sugar/joy-types', name: 'sugar-joy-types', component: () => import('@/modules/sugar/views/JoyTypeChart.vue'), meta: { title: '快乐偏好图谱' } },
  { path: '/treasure', name: 'treasure', component: () => import('@/modules/treasure/views/TreasureHub.vue'), meta: { title: '好东西档案馆' } },
  { path: '/lifesample', name: 'lifesample', component: () => import('@/modules/lifesample/views/Index.vue'), meta: { title: '人生样本' } },

  // 财富管理
  {
    path: '/wealth',
    component: () => import('@/modules/wealth/views/WealthHub.vue'),
    meta: { title: '财务管理' },
    children: [
      {
        path: '',
        redirect: { name: 'wealth-heatmap' },
      },
      {
        path: 'heatmap',
        name: 'wealth-heatmap',
        component: () => import('@/modules/wealth/views/WealthView.vue'),
        meta: { title: '现金流热力图' },
      },
      {
        path: 'monthly',
        name: 'wealth-monthly',
        component: () => import('@/modules/wealth/views/MonthlyCalendarView.vue'),
        meta: { title: '月度日历' },
      },
      {
        path: 'review',
        name: 'wealth-review',
        component: () => import('@/modules/wealth/views/MonthlyReviewView.vue'),
        meta: { title: '月度复盘' },
      },
      {
        path: 'regular',
        name: 'wealth-regular',
        component: () => import('@/modules/wealth/views/RegularDeposit.vue'),
        meta: { title: '定期存款' },
      },
      {
        path: 'cashflow',
        name: 'wealth-cashflow',
        component: () => import('@/modules/wealth/views/CashFlowView.vue'),
        meta: { title: '资产盘点' },
      },
      {
        path: 'contrib',
        name: 'wealth-contrib',
        component: () => import('@/modules/wealth/views/contrib/WealthContribView.vue'),
        meta: { title: '贡献图' },
      },
    ],
  },

  // 生存资源盘点（v3.59.0，P3-A）—— 独立菜单，不在 WealthHub 的 tab 里：
  // 它盘的是「物」，与上面 /wealth/cashflow 的「资产盘点」（盘钱）是两件事。
  {
    path: '/wealth/survival',
    name: 'wealth-survival',
    component: () => import('@/modules/wealth/views/survival/SurvivalView.vue'),
    meta: { title: '生存资源盘点' },
  },

  // 物件资产（v3.60.0，P4-A）—— 同样是独立菜单，也不进 WealthHub 的 tab：
  // 它盘的是「耐用品」（会折旧、会报废，答案是「年」与「元」），
  // 与 /wealth/survival 的「消耗物」（会被用完，答案是「天」）是两件事。
  {
    path: '/wealth/property',
    name: 'wealth-property',
    component: () => import('@/modules/wealth/views/property/PropertyView.vue'),
    meta: { title: '物件资产' },
  },

  // 负债明细台账 / 应收借出台账（v3.60.20）—— 从「资产盘点」主区拆出的**页内子页面**：
  // 不在侧边栏（刻意不占菜单项），入口是资产盘点页头右侧那两个按钮。
  // ⚠️ path 挂在 `/wealth/cashflow/` 之下而非 `/wealth/`（§45.1）：
  //    侧边栏高亮用 `route.path.startsWith('/wealth')`，两者都能亮「财务管理」，
  //    但挂父路径之下才表达得出「这是资产盘点的下一层」。
  {
    path: '/wealth/cashflow/liability',
    name: 'wealth-cashflow-liability',
    component: () => import('@/modules/wealth/views/debt/LiabilityDetailView.vue'),
    meta: { title: '负债明细台账' },
  },
  {
    path: '/wealth/cashflow/receivable',
    name: 'wealth-cashflow-receivable',
    component: () => import('@/modules/wealth/views/debt/ReceivableDetailView.vue'),
    meta: { title: '应收借出台账' },
  },

  // 三年赎回期
  {
    path: '/redemption',
    name: 'redemption',
    component: () => import('@/modules/redemption/views/RedemptionHub.vue'),
    meta: { title: '三年赎回期' },
  },
  // 自我运转（v3.61.0，P5-A）—— 独立的**顶级分组**（不挂在「目标与项目」下：
  // 目标量「要到哪里去」，自我运转量「这一阶段里有没有在动」）。
  // 🔴 子页面路由挂在父路径之下（§45）：侧边栏高亮用 `route.path.startsWith(...)`，
  //    每一项各自精确命中、不会互相抢。
  // 🔴 **每一格都是一个独立页面**（页签与路由同源）：从侧边栏点「本月状态」，
  //    落在的是本月那一格 —— 不许三项都渲染成同一屏。
  //    侧边栏只列生命周期里**常用的四项**（制定配置 / 本周 / 本月 / 历史复盘）；
  //    「阶段总结」「设置」是模块内的深层页，只从页签进（刻意不占菜单项）。
  // 🔴 父路由**刻意不给 component**：父与子若指向同一个组件，
  //    组件内的 `<router-view>` 会递归渲染自己（栈溢出）。
  // 🔴 这 8 条子路由指向**同一个组件**：它是一个仪式，切子页只换面板，
  //    不该把页头那两把尺子和阶段信息重建一遍。
  //    （侧边栏 4 条 = 生命周期的四段；「制定配置」下再挂 3 条页内子页面。）
  // ⚠️ 没有进行中的阶段时，**只有「制定配置」渲染向导** ——
  //    其余各页各自说清「这一页为什么还是空的」，并给出「去制定配置」的出口。
  //    （曾经的写法是「无阶段时任一子页整页渲染向导」，结果是三个菜单点下去
  //      一模一样，连标题都被回落成「自我运转」——用户报的就是这个。）
  {
    path: '/selfrun',
    redirect: { name: 'selfrun-week' },
    children: [
      {
        path: 'setup',
        name: 'selfrun-setup',
        component: () => import('@/modules/selfrun/views/SelfRunHub.vue'),
        meta: { title: '制定配置' },
      },
      // 「制定配置」的**三个页内子页面**（v3.61.2）—— 入口是主视图右侧那三个按钮。
      // ⚠️ path 挂在 `/selfrun/setup/` 之下而非 `/selfrun/`（§45）：
      //    侧边栏高亮用 `route.path.startsWith('/selfrun/setup')`，仍精确亮「制定配置」；
      //    而挂父路径之下才表达得出「这是制定配置的下一层」（父子关系写在 path 里）。
      // 🔴 三条都指向**同一个组件**：`SelfRunHub` 按 `route.name` 决定这一格渲染哪一块。
      // ⚠️ 刻意**不占侧边栏菜单项** —— 它们是「制定配置」里的三块，
      //    不是与它并列的第四、五、六页（并列就等于同一件事有两个入口）。
      {
        path: 'setup/templates',
        name: 'selfrun-setup-templates',
        component: () => import('@/modules/selfrun/views/SelfRunHub.vue'),
        meta: { title: 'KPI 模板库' },
      },
      {
        path: 'setup/targets',
        name: 'selfrun-setup-targets',
        component: () => import('@/modules/selfrun/views/SelfRunHub.vue'),
        meta: { title: '按期修订' },
      },
      {
        path: 'setup/logs',
        name: 'selfrun-setup-logs',
        component: () => import('@/modules/selfrun/views/SelfRunHub.vue'),
        meta: { title: '配置变更留痕' },
      },
      {
        path: 'week',
        name: 'selfrun-week',
        component: () => import('@/modules/selfrun/views/SelfRunHub.vue'),
        meta: { title: '本周状态' },
      },
      {
        path: 'month',
        name: 'selfrun-month',
        component: () => import('@/modules/selfrun/views/SelfRunHub.vue'),
        meta: { title: '本月状态' },
      },
      {
        path: 'review',
        name: 'selfrun-review',
        component: () => import('@/modules/selfrun/views/SelfRunHub.vue'),
        meta: { title: '历史复盘' },
      },
      {
        path: 'summary',
        name: 'selfrun-summary',
        component: () => import('@/modules/selfrun/views/SelfRunHub.vue'),
        meta: { title: '阶段总结' },
      },
      // ⚠️ 原第 6 条 `settings`（「设置」）**已删** —— 它与「制定配置」页里的
      //    「本阶段 KPI（即时生效）」是同一张表、同一批按钮，纯重复入口。
      //    两条路由指向同一个 tab 时，用户点进去看到的永远是同一个页面。
    ],
  },

  // 数字资产
  {
    path: '/dams',
    redirect: '/dams/dashboard',
    meta: { title: '数字资产' },
    children: [
      {
        path: 'dashboard',
        name: 'dams',
        component: () => import('@/modules/dams/views/DamsDashboard.vue'),
        meta: { title: '数字资产' },
      },
    ],
  },

  // 工具集
  {
    path: '/toolkit',
    redirect: '/toolkit/dashboard',
    meta: { title: '工具集' },
    children: [
      {
        path: 'dashboard',
        name: 'toolkit',
        component: () => import('@/modules/toolkit/views/ToolkitDashboard.vue'),
        meta: { title: '工具集' },
      },
      {
        path: 'history',
        name: 'toolkit-history',
        component: () => import('@/modules/toolkit/views/TaskHistory.vue'),
        meta: { title: '执行历史' },
      },
      {
        path: 'quotes',
        name: 'toolkit-quotes',
        component: () => import('@/modules/toolkit/views/QuoteManager.vue'),
        meta: { title: '摘录馆' },
      },
      {
        path: 'quote-tool',
        redirect: '/toolkit/quotes',
      },
      {
        path: 'health-self-check',
        name: 'health-self-check',
        component: () => import('@/modules/toolkit/views/tools/HealthSelfCheck.vue'),
        meta: { title: '身体健康自查' },
      },
      {
        path: 'health-self-check-tool',
        redirect: '/toolkit/health-self-check',
      },
      {
        path: 'decision-tracker',
        name: 'decision-tracker',
        component: () => import('@/modules/toolkit/views/tools/DecisionTracker.vue'),
        meta: { title: '决策追踪器' },
      },
      {
        path: 'decision-tracker-tool',
        redirect: '/toolkit/decision-tracker',
      },
      {
        path: 'ask-library',
        name: 'ask-library',
        component: () => import('@/modules/toolkit/views/tools/AskLibrary.vue'),
        meta: { title: 'AI 问答库' },
      },
      {
        path: 'ask-library-tool',
        redirect: '/toolkit/ask-library',
      },
      {
        path: 'free-spending',
        name: 'free-spending',
        component: () => import('@/modules/toolkit/views/tools/FreeSpending.vue'),
        meta: { title: '自由支配额度' },
      },
      {
        path: 'free-spending-tool',
        redirect: '/toolkit/free-spending',
      },
      {
        path: 'hourly-wage',
        name: 'hourly-wage',
        component: () => import('@/modules/toolkit/views/tools/HourlyWage.vue'),
        meta: { title: '时薪计算器' },
      },
      {
        path: 'hourly-wage-tool',
        redirect: '/toolkit/hourly-wage',
      },
      {
        // 用电记录的「月度用电」子页面：路径挂在父级之下 ⇒ 侧边栏「用电记录」保持高亮
        path: 'electricity-record/monthly',
        name: 'electricity-monthly',
        component: () => import('@/modules/toolkit/views/tools/ElectricityMonthly.vue'),
        meta: { title: '月度用电' },
      },
      {
        // AI 问答库的「回顾」子页面：同样挂在父级之下 ⇒ 侧边栏「AI 问答库」保持高亮。
        // 若写成平级的 /toolkit/ask-review，startsWith 匹配不上，侧边栏会整个不亮。
        path: 'ask-library/review',
        name: 'ask-library-review',
        component: () => import('@/modules/toolkit/views/tools/AskReview.vue'),
        meta: { title: '问答回顾' },
      },
      {
        path: ':toolKey',
        name: 'toolkit-detail',
        component: () => import('@/modules/toolkit/views/ToolDetail.vue'),
        meta: { title: '工具详情' },
      },
    ],
  },

  // 系统运维
  {
    path: '/admin/settings',
    name: 'AdminSettings',
    component: () => import('@/core/admin/views/AdminSettings.vue'),
    meta: { title: '系统设置' },
  },
  {
    path: '/admin/presets',
    name: 'AdminPresets',
    component: () => import('@/core/admin/views/PresetManager.vue'),
    meta: { title: '系统预设' },
  },
  {
    path: '/admin/menus',
    name: 'AdminMenus',
    component: () => import('@/core/admin/views/MenuManager.vue'),
    meta: { title: '菜单管理' },
  },

  // 连接与足迹
  { path: '/food', name: 'food', component: () => import('@/modules/food/views/FoodMapView.vue'), meta: { title: '美食地图' } },
  { path: '/travel', name: 'travel', component: () => import('@/modules/travel/views/TravelDashboard.vue'), meta: { title: '旅行记录' } },
  { path: '/travel/wishes', name: 'travel-wishes', component: () => import('@/modules/travel/views/TravelWishView.vue'), meta: { title: '旅行心愿单' } },
  { path: '/travel/plans', name: 'travel-plans', component: () => import('@/modules/travel/views/TravelPlanView.vue'), meta: { title: '旅行计划' } },
  { path: '/travel/route', name: 'travel-route', component: () => import('@/modules/travel/views/TravelRouteView.vue'), meta: { title: '旅行路线推演' } },
  {
    path: '/relation',
    name: 'relation',
    component: () => import('@/modules/relation/views/RelationView.vue'),
    meta: { title: '关系管理' },
  },
  {
    path: '/relation/conflicts',
    name: 'ConflictTracker',
    component: () => import('@/modules/relation/views/ConflictTrackerView.vue'),
    meta: { title: '成长记录' },
  },
  {
    path: '/relation/:id',
    name: 'relation-detail',
    component: () => import('@/modules/relation/views/RelationshipDetail.vue'),
    meta: { title: '关系详情' },
  },

  // 分析统计
  { path: '/analysis/progress', name: 'analysis-progress', component: () => import('@/core/analysis/views/ProgressAnalysis.vue'), meta: { title: '进度分析' } },
  { path: '/analysis/trend', name: 'analysis-trend', component: () => import('@/core/analysis/views/ProgressAnalysis.vue'), meta: { title: '趋势分析' } },
  { path: '/analysis/correlation', name: 'analysis-correlation', component: () => import('@/core/analysis/views/ProgressAnalysis.vue'), meta: { title: '关联分析' } },

  // 认证
  { path: '/login', name: 'login', component: () => import('@/core/auth/views/LoginPage.vue'), meta: { title: '登录' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ============================================
// 懒加载 chunk 失败自愈（点菜单白屏的第二种根因）
// 场景：页面开着不动，前端重新构建后旧 hash 的 chunk 被清掉，
// 此时点菜单动态导入模块失败 → 页面空白；整页刷新拿到新 manifest 即恢复。
// 这里捕获该类错误后自动做一次整页跳转，免手动刷新。
// ============================================
router.onError((error, to) => {
  const msg = error?.message || ''
  const isChunkError =
    msg.includes('Failed to fetch dynamically imported module') ||
    msg.includes('Importing a module script failed') ||
    /Loading( CSS)? chunk .+ failed/i.test(msg)
  if (isChunkError && to?.fullPath && !window.location.pathname.includes(to.path)) {
    window.location.href = to.fullPath
  }
})

export default router
