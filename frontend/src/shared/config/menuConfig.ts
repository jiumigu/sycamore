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
  // 「汇总总览」自 v3.63.14 起不占菜单格：入口在仪表盘页头（`📊 汇总总览`），
  // 路由保留。它不常用（年度回顾，不是每天打开的），但删路由会让直达链接变空白页。
  { key: 'inbox', path: '/inbox', label: '收件箱', icon: 'MessageBox', group: 'overview' },
  // 作品（v3.62.0）：一件从经历里长出来、以后还能再用的东西。
  // ⚠️ 与「汇总总览」是同一件事的两面：那边量**做了多少**，这边量**留下了什么**。
  // 🔴 刻意**不新开顶级分组** —— 它先是「总览」里的一个结果页；
  //    半年后它真成了主战场再提级，提级是一分钟的事。
  { key: 'works', path: '/works', label: '作品', icon: 'Notebook', group: 'overview' },

  // ── 时间感知 ──
  { key: 'temporal_daily', path: '/temporal/daily', label: '日记流', icon: 'Calendar', group: 'temporal' },
  // 🔴 v3.63.7：「时间统计」与「映射编辑器」**不再占菜单项**（用户 2026-10-21 拍板）。
  //    任务清单才是这一块的日常主页面，报表是「偶尔打开、看完就关」的按钮页；
  //    映射编辑器更是纯配置页（改了就不动）。三个都摆在侧边栏，等于让低频页抢高频位。
  //    ⚠️ 路由**保留**（`/temporal`、`/temporal/mapping`）—— 它们现在由页内按钮进入：
  //      任务清单 → 📊 时间统计报表 / 🧩 映射编辑器；报表 → 📋 任务清单。
  //    ⚠️ 别顺手把路由删了：删路由＝按钮点开是空白页（本项目的老坑）。
  { key: 'temporal_schedule', path: '/temporal/schedule', label: '日程视图', icon: 'Calendar', group: 'temporal' },
  // 这一块的**主入口**：手工补录、实时计时、时段重叠检查都在这一页。
  { key: 'temporal_tasks', path: '/temporal/tasks', label: '任务清单', icon: 'List', group: 'temporal' },

  // ── 目标与项目 ──
  { key: 'goals', path: '/goals', label: '人生目标', icon: 'Flag', group: 'goals' },
  { key: 'reward', path: '/reward', label: '快乐银行', icon: 'Trophy', group: 'goals' },
  // v3.63.11：「礼物清单」不再占菜单项 —— 它和「快乐银行」是同一件事的两半
  // （余额从哪来 = 流水，余额往哪去 = 礼物），而礼物清单原本还在这页里另有一套抽屉实现。
  // 现在统一成一份（独立页 `/reward/gifts`），入口放在快乐银行页头。
  // ⚠️ 路由保留：删路由＝按钮点开是空白页（本项目的老坑）。
  // ⚠️ v3.64.20：「三年赎回期」菜单项已撤 —— 它不再是独立模块，
  //    而是自我运转下的一个长阶段（入口在页头的「阶段账本」）。
  //    同一件事不再有两个顶级入口，否则用户永远分不清该点哪个。
  // 个人良品率（v3.62.39）：**取消默认归档**。
  // 原先是第一轮「用不起来」时顺手归档的，但归档 = 每次记录前先得多点一次，
  // 而它本身就是「靠频率吃饭」的功能 —— 藏起来等于自我否证，见方案 A 第 1 条。
  { key: 'output', path: '/output', label: '个人良品率', icon: 'Briefcase', group: 'goals' },

  // ── 自我运转（v3.61.0，v3.63.23 起**不占菜单项**）──
  // 🔴 2026-10-26 用户拍板：这一块的四页全部从**页头那个下拉**进
  //    （`LayoutHeader.vue` 的「自我运转」入口：制定配置 / 本周状态 / 本月状态 / 历史复盘，
  //    默认落在「本周状态」），侧边栏不再列 —— 那四行占的是「目标与项目」下面一整块位置，
  //    而它们其实是同一件事的四个时间尺度，进哪个都得先在页内切页签。
  // ⚠️ **路由全部保留**（`/selfrun/setup|week|month|review|summary`）：
  //    删路由＝下拉点开空白页（本项目老坑）。
  // ⚠️ `selfrun` **分组**同样保留（`defaultGroups` + 后端 `DEFAULT_MENU_GROUPS`）：
  //    删分组要动库、还会打乱用户拖过的顺序；而 `LayoutSidebar` 对空分组会自动跳过
  //    （`v-if="groupMenus(g.group_key).length > 0"`），所以侧边栏不会留一个空标题。
  // ⚠️ 别在这里「恢复」这四项 —— 恢复了就等于同一件事有两个入口。

  // ── 身心健康 ──
  { key: 'health', path: '/health', label: '健康管理', icon: 'FirstAidKit', group: 'health' },
  // v3.63.12：「体重管理」「好朋友跟踪」不再占菜单项（用户 2026-10-22 拍板）。
  // 判据：它们和「步数记录」是**同一份身体账本**，日常都是「进来记一笔、看完就回」的同一个动作，
  // 各自占一行只是把「身心健康」撑长（4 项 → 2 项）。入口放在健康管理页头。
  // ⚠️ 路由保留（`/health/weight`、`/health/menstrual`）：删路由＝按钮点开是空白页（老坑）。
  // ⚠️ 体重页的三个子页（月度进度 / BMI / 调整记录）仍从体重页页头进，回程由 WeightSubHeader 负责。
  { key: 'dance', path: '/dance', label: '舞蹈记录', icon: 'Star', group: 'health', defaultArchived: true },

  // ── 精神滋养 ──
  { key: 'books', path: '/books', label: '书籍阅读', icon: 'Reading', group: 'nourishment' },
  { key: 'sugar', path: '/sugar', label: '小确幸', icon: 'Present', group: 'nourishment' },
  { key: 'treasure', path: '/treasure', label: '好恶物档案馆', icon: 'Star', group: 'nourishment' },
  { key: 'lifesample', path: '/lifesample', label: '人生样本', icon: 'Collection', group: 'nourishment' },

  // ── 财富管理 ──
  { key: 'wealth', path: '/wealth', label: '财务管理', icon: 'Money', group: 'wealth' },
  // 生存资源盘点（v3.59.0）：盘的是「物」（吃/穿/用/数字），与「资产盘点」（盘钱）刻意分开
  { key: 'wealth_survival', path: '/wealth/survival', label: '生存资源盘点', icon: 'Box', group: 'wealth' },
  // 物件资产（v3.60.0）：盘的是「耐用品」（会折旧会报废，答案是年与元）。
  // ⚠️ 与「生存资源盘点」（消耗物，答案是天）是两条路径，别合并 ——
  //    判据一句话：纸巾会被用完 → 生存资源；冰箱会被用坏 → 物件资产。
  { key: 'wealth_property', path: '/wealth/property', label: '物件资产', icon: 'Suitcase', group: 'wealth' },

  // ── 连接与足迹 ──
  // 旅行四件套：心愿（想去）→ 路线推演（怎么走）→ 计划（哪天去/预算）→ 足迹（去过并沉淀）
  // v3.63.8：「旅行心愿单」「路线推演」并入「旅行计划」页内按钮，「美食地图」并入
  // 「旅行记录」，「成长记录」并入「关系管理」—— 它们的共同点是**从父页进去、看完就回**，
  // 单独占一行菜单只会把「连接与足迹」撑长（6 项 → 3 项）。
  // ⚠️ 路由全部保留（`/travel/wishes`、`/travel/route`、`/food`、`/relation/conflicts`），
  //    改由父页按钮 + 子页「返回」形成闭环；删路由＝点按钮空白页。
  { key: 'travel', path: '/travel', label: '旅行记录', icon: 'Location', group: 'connection' },
  { key: 'travel_plans', path: '/travel/plans', label: '旅行计划', icon: 'List', group: 'connection' },
  { key: 'relation', path: '/relation', label: '关系管理', icon: 'User', group: 'connection' },

  // ── 工具箱 ──
  { key: 'toolkit', path: '/toolkit', label: '工具箱', icon: 'Tools', group: 'tools' },
  { key: 'toolkit_electricity', path: '/toolkit/electricity-record', label: '用电记录', icon: 'Lightning', group: 'tools' },
  { key: 'toolkit_quotes', path: '/toolkit/quotes', label: '摘录管理', icon: 'Collection', group: 'tools' },
  { key: 'toolkit_ask_library', path: '/toolkit/ask-library', label: 'AI 问答库', icon: 'ChatDotRound', group: 'tools' },
  // v3.63.12：「执行历史」不再占菜单项 —— 它是**结果页**（谁执行过、成没成），
  // 不是一件要主动去用的工具，单独占一行等于让复印件抢原件的位置。
  // 已有两条更贴场景的出口，撤掉不会变成死路：
  //   ① 工具箱首页页头「🕐 执行历史」；
  //   ② 执行型工具详情页返回栏右侧的「执行历史」（只列该工具自己的记录）。
  // ⚠️ 路由保留（`/toolkit/history`）：上面两处按钮都指向它，删路由＝点开空白页。

  // ── 系统运维 ──
  { key: 'admin_settings', path: '/admin/settings', label: '系统设置', icon: 'Setting', group: 'system' },
  { key: 'admin_presets', path: '/admin/presets', label: '系统预设', icon: 'Collection', group: 'system' },
  { key: 'admin_menus', path: '/admin/menus', label: '菜单管理', icon: 'Menu', group: 'system' },

  // ── 展厅 ──
  // 🔴 独立顶级分组：展厅是「对外输出端口」，与所有「对内记录」分组不同质，不该混进任何现有分组。
  //    策展是低频、事件驱动的动作，放最末不抢高频入口。
  // ⚠️ 「策展编辑」必须占一个菜单项：它是展厅还空着时唯一的出口，藏在页里就等于没有入口。
  { key: 'showroom_preview', path: '/showroom/preview', label: '展厅预览', icon: 'House', group: 'showroom' },
  { key: 'showroom_edit', path: '/showroom/edit', label: '策展编辑', icon: 'EditPen', group: 'showroom' },

  // ── 第一轮已归档（默认归档，可在菜单管理里取消归档回到原分组） ──
  // v3.63.8：`food` / `relation_conflicts` 两项已从这里移除 —— 它们不是「归档」而是
  // 「本来就不该是独立菜单」，现由父页按钮进入（见上方连接与足迹的注释）。
  { key: 'dams', path: '/dams', label: '数字资产', icon: 'Cpu', group: 'wealth', defaultArchived: true },
]

/** 默认分组（与后端 ensure_default_menu_groups 保持一致） */
export const defaultGroups: MenuGroupDef[] = [
  { key: 'overview', name: '总览', sort: 1 },
  { key: 'temporal', name: '时间感知', sort: 2 },
  { key: 'goals', name: '目标与项目', sort: 3 },
  { key: 'selfrun', name: '自我运转', sort: 4 },
  { key: 'health', name: '身心健康', sort: 5 },
  { key: 'nourishment', name: '精神滋养', sort: 6 },
  { key: 'wealth', name: '财富管理', sort: 7 },
  { key: 'connection', name: '连接与足迹', sort: 8 },
  { key: 'tools', name: '工具箱', sort: 9 },
  { key: 'system', name: '系统运维', sort: 10 },
  { key: 'showroom', name: '展厅', sort: 11 },
]
