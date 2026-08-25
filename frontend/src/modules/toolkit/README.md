# Toolkit — 工具集前端

## Views

| 文件 | 职责 |
|------|------|
| `ToolkitDashboard.vue` | 首页（搜索 + 分类标签 + 工具卡片网格，含「执行历史」入口） |
| `ToolDetail.vue` | 工具详情壳（返回栏 + 渲染独立组件或通用执行表单；路由 `/toolkit/:toolKey` 兜底） |
| `TaskHistory.vue` | 执行历史页（分页列表 + 工具/状态筛选 + 错误详情弹窗） |
| `QuoteManager.vue` | 摘录馆 |

## 独立工具组件（`views/tools/`）

### 数据型工具（历史存各自数据表，页面底部展示自己的历史列表）

| 文件 | 工具 |
|------|------|
| `FixedExpense.vue` | 固定开销计算器 |
| `ElectricityRecord.vue` | 用电记录（统计卡 + 趋势图 + 历史表） |
| `EnvironmentAudit.vue` | 环境校准 |
| `CareerEnergyAudit.vue` | 职业能量审计 |
| `TravelRoute.vue` | 旅行路线推演（地图 + 路线抽屉） |
| `HourlyWage.vue` | 时薪计算器 |
| `FreeSpending.vue` | 自由支配额度 |
| `HealthSelfCheck.vue` | 身体健康自查 |
| `ReviewToolbox.vue` | 复盘工具箱 |
| `DecisionLog.vue` | 决策日志 |
| `LanguageTrainer.vue` | 语言训练器 |

### 执行型工具（执行记录进入「执行历史」页）

| 文件 | 工具 |
|------|------|
| `GifCompressor.vue` | GIF 压缩 |
| 通用表单 | 图片转GIF `img2gif` / 繁简转换 `trad2simp`（经 `ToolDetail.vue` 动态表单执行） |

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
