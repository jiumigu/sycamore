# Temporal — 时间感知前端

> 文档对齐 v3.64.34 ｜ 最后核对 2026-11-07

## 入口（v3.63.7 起）

侧边栏「时间感知」只留三项：**日记流 / 日程视图 / 任务清单**。任务清单是主页面；
时间统计报表与映射编辑器**降为任务清单页头按钮**（路由保留，不占菜单项 —— 见 §130）。

| 页面 | 路由 | 职责 |
|------|------|------|
| `views/TemporalView.vue` | `/temporal/daily` | 日记流主页 |
| `views/ScheduleView.vue` | `/temporal/schedule` | 日程视图 |

## 日程视图的数据口径

两个来源：`/inbox/items/calendar/`（收件箱待办）+ `/goals/milestones/`（里程碑）。

🔴 里程碑请求带 `exclude_abandoned_goals=1`（2026-10-26）：**已放弃目标 + 还没完成的里程碑不进日历**。
理由：放弃目标时里程碑**不级联删**（项目铁律），一批 `pending` 会一直排在日历上，
十月看起来像还有 24 件事要做 —— 一件也不会做了。
**已完成的留着**，翻历史日程时「那天做过什么」还得在。
过滤由后端解释（`goals/views.py::MilestoneViewSet`），前端只传开关、不自己筛。
| `views/TaskListView.vue` | `/temporal/tasks` | **主页面**：任务清单 + 页头六入口（贡献图 / 手工新增 / 实时计时 / 映射编辑器 / 来源批次 / 时间统计报表） |
| `views/TimeStatsView.vue` | `/temporal` | 时间统计报表（从任务清单按钮进；页头「← 任务清单」） |

## Components

| 文件 | 职责 |
|------|------|
| `components/MappingEditor.vue` | 任务名 → L2 类型的分类台账（返回目标 `/temporal/tasks`）。含 **「成长计时」开关列**（v3.64.11）：勾上 ⇒ 该任务名计入每周状态的成长小时数，这是**唯一依据**，改 L2 不会连带改它 |
| `components/TimerPanel.vue` | 实时计时抽屉（开始 / 停止 / 丢弃） |
| `components/TimerTaskPicker.vue` | 计时任务选择（复用「最近常用」候选） |
| `components/Weekly168Chart.vue` | 168h 周结构图 |
| `components/SunburstChart.vue` | 三层同心结构图 |
| `components/LogseqViewer.vue` | Logseq 日记预览 |
| `components/contrib/` | 贡献图相关子组件 |

## Shared（顶栏计时器）

- `shared/components/TimerWidget.vue`：顶栏常驻计时壳
- `shared/components/TimerStopDialog.vue`：停止确认**唯一实现**（超长确认由后端 409 驱动，前端不写 4h 常量）
- `shared/composables/useTimer.ts`：模块级单例；已流逝 = 后端值 + 本地增量，窗口 focus / visibilitychange 对一次后端
- `shared/api/timerApi.ts`：running / start / stop / discard

## Store / API / Types

- `stores/temporalStore.ts`：Pinia 状态管理
- `api/temporalApi.ts`：任务 / 日记 / 统计 / 常用任务名 / 重叠检查 / 来源总览封装
- `types/temporalTypes.ts`：类型定义

## 注意

- **任务清单是主页**：它不再有「← 返回」；报表、映射编辑器与贡献图都从它的页头按钮进（贡献图带 `?from=tasks`，返回落回任务清单）。
- **时段重叠只提示不阻断**：保存前调 `check_overlap`，命中弹确认；查询失败只 warning，不挡保存（§129）。
- 🔴 **CSV 导入是两步**（v3.64.32）：`previewCsv()` 只读预演 → 展示分类清单 → 勾掉不要的 →
  `importCsv(file, skipRows)` 落库。四条铁律：
  ① 勾掉的 `row_no` **原样回传**，前端不得按数组下标重算（解析失败的行占掉一个行号，差一行就跳错记录）；
  ② 换文件必须清空 `preview` 与 `skippedRows`（否则拿旧行号跳新文件）；
  ③ 只列 `review` / `likely_dup` —— `contained`（大段里的细分）与 `edge`（跨整点摩擦）只计数，
     文案说「没列出来」与清单必须同源，否则用户以为「上班时段里记代码」也要裁决；
  ④ **不说「将新增 N 条」**：预演不判更新还是新增，编个数就是假精确。
- **导入入口在「时间统计」页**（不在任务清单）：这轮没搬，属于已知的交互问题 —— 导入是录入动作却藏在报表页。
- 🔴 **来源词全部来自后端**（v3.64.33）：表格「来源」列显示 `source_label`，来源下拉的选项来自
  `/tasks/sources/` 的 `kinds[]` —— 前端**不写**「CSV 导入 / 未标注」这类映射，否则改词要改两处，
  不一致时页面不报错、只说出两种来源名。
  - `unlabeled`（灰，早期没留标记）与 `other`（橙，有批次号但没认出来）**分开显示**，别合成「来源不明」。
  - 「来源批次」弹窗的数字必须走接口：任务列表是分页的，前端自己数只会数出当前页。
  - 批次钻取（「看这 N 条」）会**清掉日期范围**并挂一枚可清除的「只看批次 xxx」标签；
    换来源时同一枚标签自动清空 —— 否则「来源=CSV + 批次=worklog」组合出空交集，只看到「暂无数据」。
- **常用任务名**：只在新增态显示，标签与手输共用 `editForm.task_name`；取消选中恢复选前手输值。
- **手工新增弹窗末尾那行灰字**（v3.64.34）：「保存后来源记为『手工录入』」，`v-if="!editingId"`。
  写它的理由是**录入时就说清，而不是事后翻来源列猜**；编辑态不出现 —— 改备注不换来源。
- `WeeklyTrackingView.vue` 已于 v3.60.34 移除；后端 `/weekly-tracking/` 按设计稿保留，**别接回前端**。
- **成长计时开关是受控的**（`:model-value` + `:key` 带 `rev`）：请求失败时 prop 没变，
  但 el-switch 内部可能已翻过去 ⇒ 失败分支必须 `rev += 1` 并重新 `load()`，
  否则界面显示的状态和库里不一致（看着像「点了没保存」，其实存的是另一个值）。
- 🔴 **L1 归因下拉绑 `default_attribution`，不绑 `effective_attribution`**（v3.64.28）。
  绑定后者会把兜底值（「成长」）渲染成已选中的项 ⇒ 没配的行看起来跟配好的一模一样，
  用户从账本「去归好」点进来只能得出「明明都配好了」，而且无处可改。
  没配的行显示 placeholder「未配 · 现按成长」+ `.is-attr-unset` 琥珀描边。
- **三个 chip 互斥**（某个归因 / 未归类 / 未配归因）：统一走 `clearChipFilters()`。
  从前只清 `attribution`，「未归类 + 未配归因」能同时为真 ⇒ 组合出空列表，看着像「没有这类任务」。
- **支持 `?unset_attr_only=1`**：阶段账本的「去归好」带着它跳过来，落地即筛出待配的行。
  新增「去修一下」类链接时沿用这个做法 —— 裸跳转让用户自己在几十行里找。
