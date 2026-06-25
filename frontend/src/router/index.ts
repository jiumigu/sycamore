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
  { path: '/summary/quarterly', name: 'summary-quarterly', component: () => import('@/modules/summary/views/QuarterlyWorkbench.vue'), meta: { title: '季度决策' } },

  // 收件箱
  { path: '/inbox', name: 'inbox', component: () => import('@/modules/inbox/views/InboxDashboard.vue'), meta: { title: '收件箱' } },

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
    path: '/temporal/weekly-tracking',
    name: 'WeeklyTracking',
    component: () => import('@/modules/temporal/views/WeeklyTrackingView.vue'),
    meta: { title: '年度周度追踪' },
  },
  {
    path: '/temporal/schedule',
    name: 'schedule',
    component: () => import('@/modules/temporal/views/ScheduleView.vue'),
    meta: { title: '日程视图' },
  },

  // 目标与项目
  { path: '/goals', name: 'goals', component: () => import('@/modules/goals/views/GoalHub.vue'), meta: { title: '人生目标' } },
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
  { path: '/projects', name: 'projects', component: () => import('@/modules/projects/views/ProjectOverview.vue'), meta: { title: '项目管理' } },

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
        path: 'milestones',
        name: 'health-milestones',
        component: () => import('@/modules/health/views/MilestoneMap.vue'),
        meta: { title: '里程碑地图' },
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
  { path: '/dance', name: 'dance', component: () => import('@/modules/dance/views/DanceView.vue'), meta: { title: '舞蹈记录' } },

  // 精神滋养
  { path: '/nourishment', name: 'nourishment', component: () => import('@/modules/sugar/views/SugarView.vue'), meta: { title: '精神花园' } },
  { path: '/books', name: 'books', component: BookView, meta: { title: '书籍阅读' } },
  { path: '/sugar', name: 'sugar', component: () => import('@/modules/sugar/views/SugarView.vue'), meta: { title: '小确幸' } },
  { path: '/sugar/joy-types', name: 'sugar-joy-types', component: () => import('@/modules/sugar/views/JoyTypeChart.vue'), meta: { title: '快乐偏好图谱' } },
  { path: '/treasure', name: 'treasure', component: () => import('@/modules/treasure/views/TreasureHub.vue'), meta: { title: '好东西档案馆' } },

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
        meta: { title: '现金盘点' },
      },
    ],
  },
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
        path: 'decision-log',
        name: 'decision-log',
        component: () => import('@/modules/toolkit/views/tools/DecisionLog.vue'),
        meta: { title: '决策日志' },
      },
      {
        path: 'decision-log-tool',
        redirect: '/toolkit/decision-log',
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
        path: 'review-toolbox',
        name: 'review-toolbox',
        component: () => import('@/modules/toolkit/views/tools/ReviewToolbox.vue'),
        meta: { title: '复盘工具箱' },
      },
      {
        path: 'review-toolbox-tool',
        redirect: '/toolkit/review-toolbox',
      },
      {
        path: ':toolKey',
        name: 'toolkit-detail',
        component: () => import('@/modules/toolkit/views/ToolDetail.vue'),
        meta: { title: '工具详情' },
      },
    ],
  },

  // 连接与足迹
  { path: '/food', name: 'food', component: () => import('@/modules/food/views/FoodMapView.vue'), meta: { title: '美食地图' } },
  { path: '/travel', name: 'travel', component: () => import('@/modules/travel/views/TravelDashboard.vue'), meta: { title: '旅行记录' } },
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

export default router
