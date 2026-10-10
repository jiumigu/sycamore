# Redemption — 三年赎回期

「用 10 万买回 3 年自由」的判定层。窗口 **2026-10-01 → 2029-09-30**，回答两件事：
这笔钱够撑多久、以及这段时间里时间到底花到哪去了（成长 / 关系 / 维持 / 谋生 / 流失）。

完整设计见 `docs/三年赎回期-功能设计-v0.4-落地命令清单.md`（v0.1–v0.3 为历次迭代稿）。

## Models

四张 **managed 表**，不污染财富 / 时间模块：

| Model | Table | 用途 |
|-------|-------|------|
| RedemptionPeriod | redemption_period | **单例（pk=1）**：窗口起止、现金池本金、暂停状态、阶段一基线 |
| RedemptionPoolInject | redemption_pool_inject | 现金池中途注入流水（赔偿 / 借款 / 额外收入 / 其他） |
| RedemptionAttrRule | redemption_attr_rule | **时间归因外挂规则**：ATracker 任务属性 → L1 归因五词 |
| RedemptionWeekSnapshot | redemption_week_snapshot | 周归因快照（五类小时 + 覆盖率 + 成长占比 + 单位赎回成本），`unique_together(year, week)` |

⚠️ **绝不向 ATracker 的 `managed=False` 外部表加列** —— 归因只能靠 `RedemptionAttrRule` 外挂映射。

## Services

`services.py` 是全部口径的唯一实现：

| 函数 | 职责 |
|------|------|
| `get_or_create_period` / `_window_bounds` / `_today_clamped` | 单例读写与窗口边界（日期一律夹在窗口内） |
| `compute_pool_balance` | 现金池余额 |
| `compute_avg_daily_self_net` | 近 30 日日均净支出 |
| `compute_support_until` | 按当前支出速度能撑到哪天 |
| `match_attribution_rule` | **归因匹配唯一实现**（全项目共用，见下） |
| `compute_time_attribution` | 五类归因小时 |
| `compute_unit_cost` | 单位赎回成本 |
| `compute_redemption_stats` | 汇总（`include_time=False` 时不查时间侧） |
| `sync_to_scenario` | 把结果同步进 wealth 的推演场景（`mode='preview'` 为试算） |

### 归因匹配是单一真源

`match_attribution_rule(...)` 是**全项目唯一**的维度匹配实现。
`match_field` 目前只认三项：`task_name` / `activity_type` / `task_type`。

⚠️ **加维度必须同时改三处**：`MATCH_FIELD_CHOICES` + `match_attribution_rule` 分支 + 前端 `AttrField` / `AttrRuleEditor.vue`。
**漏前端 = 选不到，漏后端 = 静默不生效。**

⚠️ 判新维度前先问「它在不在 ATracker 外部表」：`activity_type` 住在 `temporal_task_meta`，须按 `task_name` 反查后传入，**别在循环里 N+1**。

⚠️ `RedemptionAttrRule` **绝不能删** —— 它是归因覆盖的真身，也是唯一的管理入口（台账改 L1 会同步 `update_or_create` 一条 `priority=100` 的 `task_name` 规则）。

⚠️ 归因词表的单一真源是 `apps.temporal.constants.ATTRIBUTION_CHOICES`，**本模块不再自存副本**（v3.58.10 前存过一份，改词必漂移）。

## 暂停追踪

`tracking_status = paused` 时**只停止计算与展示指标，不停止记录、不发提醒**；
`paused_since` / `resume_at` 记录区间。

## API Endpoints

前缀 `/api/redemption/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/PUT | / | 窗口配置读取 / 更新（单例） |
| POST | /pause/ | 暂停追踪 |
| POST | /resume/ | 恢复追踪 |
| GET/POST | /injects/ | 现金池注入流水 |
| GET/POST | /attr-rules/ | 归因规则列表 / 新增 |
| PUT/DELETE | /attr-rules/&lt;pk&gt;/ | 规则更新 / 删除 |
| GET | /stats/ | 赎回期汇总指标 |
| POST | /sync-scenario/ | 同步到 wealth 推演场景 |

## 边界

- 窗口**之前**的 `period_tag` 全为 `NULL` 是**正确结果、不是 bug**。
- 撤销归因覆盖时：只有 `task_name` 能单行撤销，`activity_type` / `task_type` 会**连坐**。
