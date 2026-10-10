# Toolkit — 工具集前端

## Views

| 文件 | 职责 |
|------|------|
| `ToolkitDashboard.vue` | 首页（搜索 + 分类标签 + 工具卡片网格，含「执行历史」入口） |
| `ToolDetail.vue` | 工具详情壳（返回栏 + 渲染独立组件或通用执行表单；路由 `/toolkit/:toolKey` 兜底） |
| `TaskHistory.vue` | 执行历史页（分页列表 + 工具/状态筛选 + 错误详情弹窗） |
| `QuoteManager.vue` | 摘录馆（统计卡讲清「几条会进金句池 / 几条超长不上卡」；每条带池状态标签与字数；筛选区可按池内外筛 —— 池外条目必须筛得出来，否则等于没有出口） |

## 独立工具组件（`views/tools/`）

### 数据型工具（历史存各自数据表，页面底部展示自己的历史列表）

| 文件 | 工具 |
|------|------|
| `AskLibrary.vue` | AI 问答库（场景容器 + 主题列表 + 抽屉详情 + 导出 md；标题右侧「回顾」按钮 → 回顾页） |
| `AskReview.vue` | AI 问答库 · 回顾页（路由 `/toolkit/ask-library/review`：按场景分组的主题清单 + 冷落天数 + 点主题开抽屉标记采纳/备注） |
| `FixedExpense.vue` | 固定开销计算器 |
| `ElectricityRecord.vue` | 用电记录（5 张统计卡 + 录入表单 + 趋势图 + 历史表；标题右侧按钮 → 月度页） |
| `ElectricityMonthly.vue` | 用电记录 · 月度页（路由 `/toolkit/electricity-record/monthly`：月度柱状图 + 12 月明细 + 点月看该月明细 + PERT 估算详情） |
| `CareerEnergyAudit.vue` | 职业能量审计 |
| `HourlyWage.vue` | 时薪计算器 |
| `FreeSpending.vue` | 自由支配额度 |
| `HealthSelfCheck.vue` | 身体健康自查 |

> `TravelRoute.vue`（旅行路线推演）已于 2026-09-11 **迁出工具箱** → `modules/travel/views/TravelRouteView.vue`（路由 `/travel/route`）。它本质是旅行计划的编排器，与 `TravelPlan` 强耦合，放在通用工具箱里用户找不到。工具箱侧保留工具卡片，进入 `/toolkit/travel-route` 时由 `ToolDetail.vue` 渲染一张「已迁入旅行模块」的跳转卡片（后端 `toolkit_travel_route_preset` 表与 `/api/toolkit/travel-routes/` 接口未动）。

### 执行型工具（执行记录进入「执行历史」页）

| 文件 | 工具 |
|------|------|
| `GifCompressor.vue` | GIF 压缩 |
| 通用表单 | 繁简转换 `trad2simp`（经 `ToolDetail.vue` 动态表单执行） |

## 共享组件（`components/`）

| 文件 | 职责 |
|------|------|
| `QuoteForm.vue` | 摘录新增 / 编辑表单（内容框下**实时显示字数与是否在金句池取句范围内**；超限只提醒、**不阻止保存** —— 上限读自系统设置） |
| `QuoteDetailDialog.vue` | 金句详情弹窗。⚠️ **v3.60.11 起暂无调用方**（原因见下） |

`QuoteDetailDialog.vue` 的取舍：

- 宽度 `min(880px, 92vw)` —— 880px 让中文正文落到约 50 字/行的舒适区，`92vw` 保证窄屏不溢出。此前两处各写一份、分别 `500px` / `600px`。
- 正文 `max-height: 68vh` 独立滚动，标题与落款固定，长文不撑出屏幕。
- 🔴 **2026-09-30 起暂无调用方**：金句取数改走 `quotes/next/`，且首页卡片改为**显示全文**（长度上限可配、默认 500 字，超出者根本不上卡）⇒ 「点击看全文」失去意义；汇总总览与仪表盘两处的段落分支、`is_paragraph` 判断与弹窗引用已一并撤掉。组件保留（将来若要恢复长文展示可直接接回），但**别再写「汇总总览与仪表盘共用」—— 那句已经假了**。
- **段落型**金句走 Markdown 渲染（`@/shared/utils/markdown` 的 `renderMarkdown()`），**短句型**走 `pre-wrap` 纯文本 —— 一句「3 * 5 = 15」不该被当成斜体。
- 正文节点由 `v-html` 注入，样式必须写 `:deep()`；scoped 打不进去。

## 页面结构约定

- **数据型**：返回按钮 + 工具内容 + 页面底部自己的历史列表；无描述卡片、无「执行历史」跳转
- **执行型**：返回按钮 + 工具内容 + 返回栏右侧「执行历史」入口
- **不允许独立描述卡片**：工具名称/描述由各页面自身的 `page-title` 提供，`ToolDetail.vue` 不渲染共享描述卡片

## Store / API / Types

| 文件 | 职责 |
|------|------|
| `toolkitStore.ts` | Pinia 状态管理（工具列表 / 执行 / 进度 / 结果） |
| `toolkitApi.ts` | 全部 toolkit API 封装（工具 / 城市 / 路线 / 各类审计 / 数据型工具 CRUD / 用电记录等） |
| `toolkitTypes.ts` | 类型定义 + CATEGORY_LABELS + STATUS_CONFIG |
