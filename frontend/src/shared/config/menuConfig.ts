/**
 * 全量菜单定义（权威清单）
 * - group: 菜单所属分组 key（取消归档后自动回到该分组）
 * - defaultArchived: 无偏好记录时的默认态（true=默认归档，如第一轮已归档模块）
 * 注意：保持与 router/index.ts 的 path 一一对应，防止悬空链接
 */

export interface MenuItem {
  key: string
  path: string
  label: string
  icon: string
  group: string
  defaultArchived?: boolean
}

export interface MenuGroupDef {
  key: string
  name: string
  sort: number
}

export const allMenuItems: MenuItem[] = [
  // ── 总览 ──
  { key: 'dashboard', path: '/dashboard', label: '仪表盘', icon: 'DataAnalysis', group: 'overview' },
  { key: 'summary', path: '/summary', label: '汇总总览', icon: 'PieChart', group: 'overview' },
  { key: 'personal_profile', path: '/summary/profile', label: '个人画像', icon: 'User', group: 'overview' },
  { key: 'inbox', path: '/inbox', label: '收件箱', icon: 'MessageBox', group: 'overview' },

  // ── 时间感知 ──
  { key: 'temporal_daily', path: '/temporal/daily', label: '日记流', icon: 'Calendar', group: 'temporal' },
  { key: 'temporal_stats', path: '/temporal', label: '时间统计', icon: 'Timer', group: 'temporal' },
  { key: 'temporal_schedule', path: '/temporal/schedule', label: '日程视图', icon: 'Calendar', group: 'temporal' },

  // ── 目标与项目 ──
  { key: 'goals', path: '/goals', label: '人生目标', icon: 'Flag', group: 'goals' },
  { key: 'reward', path: '/reward', label: '快乐银行', icon: 'Trophy', group: 'goals' },
  { key: 'reward_gifts', path: '/reward/gifts', label: '礼物清单', icon: 'Present', group: 'goals' },

  // ── 身心健康 ──
  { key: 'health', path: '/health', label: '健康管理', icon: 'FirstAidKit', group: 'health' },
  { key: 'health_weight', path: '/health/weight', label: '体重管理', icon: 'TrendCharts', group: 'health' },
  { key: 'health_menstrual', path: '/health/menstrual', label: '好朋友跟踪', icon: 'FirstAidKit', group: 'health' },
  { key: 'dance', path: '/dance', label: '舞蹈记录', icon: 'Star', group: 'health', defaultArchived: true },

  // ── 精神滋养 ──
  { key: 'books', path: '/books', label: '书籍阅读', icon: 'Reading', group: 'nourishment' },
  { key: 'sugar', path: '/sugar', label: '小确幸', icon: 'Present', group: 'nourishment' },
  { key: 'treasure', path: '/treasure', label: '好东西', icon: 'Star', group: 'nourishment' },
  { key: 'lifesample', path: '/lifesample', label: '人生样本', icon: 'Collection', group: 'nourishment' },

  // ── 财富管理 ──
  { key: 'wealth', path: '/wealth', label: '财务管理', icon: 'Money', group: 'wealth' },

  // ── 连接与足迹 ──
  { key: 'travel', path: '/travel', label: '旅行记录', icon: 'Location', group: 'connection' },
  { key: 'relation', path: '/relation', label: '关系管理', icon: 'User', group: 'connection' },

  // ── 工具箱 ──
  { key: 'toolkit', path: '/toolkit', label: '工具箱', icon: 'Tools', group: 'tools' },
  { key: 'toolkit_history', path: '/toolkit/history', label: '执行历史', icon: 'Timer', group: 'tools' },

  // ── 系统运维 ──
  { key: 'admin_tags', path: '/admin/tag-manager', label: '标签管理器', icon: 'PriceTag', group: 'system' },
  { key: 'admin_settings', path: '/admin/settings', label: '系统设置', icon: 'Setting', group: 'system' },
  { key: 'admin_presets', path: '/admin/presets', label: '系统预设', icon: 'Collection', group: 'system' },
  { key: 'admin_menus', path: '/admin/menus', label: '菜单管理', icon: 'Menu', group: 'system' },

  // ── 第一轮已归档（默认归档，可在菜单管理里取消归档回到原分组） ──
  { key: 'output', path: '/output', label: '个人良品率', icon: 'Briefcase', group: 'goals', defaultArchived: true },
  { key: 'dams', path: '/dams', label: '数字资产', icon: 'Cpu', group: 'wealth', defaultArchived: true },
  { key: 'food', path: '/food', label: '美食地图', icon: 'Food', group: 'connection', defaultArchived: true },
  { key: 'travel_plans', path: '/travel/plans', label: '旅行计划', icon: 'List', group: 'connection', defaultArchived: true },
  { key: 'relation_conflicts', path: '/relation/conflicts', label: '成长记录', icon: 'Sunny', group: 'connection', defaultArchived: true },
]

/** 默认分组（与后端 ensure_default_menu_groups 保持一致） */
export const defaultGroups: MenuGroupDef[] = [
  { key: 'overview', name: '总览', sort: 1 },
  { key: 'temporal', name: '时间感知', sort: 2 },
  { key: 'goals', name: '目标与项目', sort: 3 },
  { key: 'health', name: '身心健康', sort: 4 },
  { key: 'nourishment', name: '精神滋养', sort: 5 },
  { key: 'wealth', name: '财富管理', sort: 6 },
  { key: 'connection', name: '连接与足迹', sort: 7 },
  { key: 'tools', name: '工具箱', sort: 8 },
  { key: 'system', name: '系统运维', sort: 9 },
]
