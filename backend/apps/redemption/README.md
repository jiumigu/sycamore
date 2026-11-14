# Redemption — 赎回期（**已无页面、无接口、无表**）

> 文档对齐 v3.64.20 ｜ 最后核对 2026-11-02

这个 app 现在只剩一层：`services.py` 里那几个**按区间算数的纯函数**。
「三年赎回期」不再是一个模块，而是**自我运转下的一个长阶段**
（`selfrun_stage` 顶级那一行，`ledger_config.pool_principal` 记本金）——
界面在「阶段账本」（`/selfrun/stage`），读数由
`GET /api/selfrun/stages/<pk>/ledger/` 提供。

## Models

**一张都没有。**

| 表 | 结局 |
|---|---|
| `redemption_period` | 退役（v3.64.20，迁移 `0010`）。窗口→`selfrun_stage.start_date/end_date`；本金→`ledger_config.pool_principal`；暂停→`selfrun_stage.status` |
| `redemption_week_snapshot` | 退役（同批）。从建表起 **0 写入 0 读取**，且加 L1「体验」时没补列 —— 真启用必漏数 |
| `redemption_pool_inject` | **迁走**：→ `selfrun_pool_inject`（v3.64.20，selfrun 迁移 `0009`）。留在原处会让两个 app 双向依赖（selfrun 用它的函数、它用 selfrun 的阶段外键） |

🔴 `0010` 是 `RunPython(搬数据) + DeleteModel × 3`，**只写不跑**。删表不可逆，
执行前必须先备份数据库到 `db_backups/`。反向迁移只重建空表，**数据不回流**。

## Services

`services.py` 是全部口径的唯一实现，**不 import 任何模型**：

| 函数 | 职责 |
|------|------|
| `_window_bounds(start, end)` | 区间 `[start 00:00, end+1天 00:00)` 的 datetime 边界（**半开**） |
| `compute_pool_balance(principal, start, end, injected=0)` | 现金池余额 = 本金 + 注入 − 为自己净消耗 |
| `compute_avg_daily_self_net_detail(start, end)` | 日均的**完整读数** → 均值（分母 = `min(实际天数, 30)`）+ 窗口实际覆盖天数 + `thin`（样本够不够 30 天） |
| `compute_avg_daily_self_net(start, end)` | 近 30 日日均净支出（锚点 `min(今天, 终点)`）；只是上一个的均值那一项，**别在这上面再除一次** |
| `compute_support_until(balance, avg_daily, anchor)` | 能撑到哪天 → `(日期\|None, zero_reason\|None)` |
| `compute_tier_stats(start, end)` | 各档笔数（`Count`，**不是** `Sum('id')`）与发生额 |
| `compute_time_attribution(start, end)` | 六类归因小时（**除睡眠外的全部记录**；睡眠单列 `excluded_sleep_hours`，键集由 `ATTRIBUTION_CHOICES_LIST` 派生） |
| `compute_unit_cost(start, end, net_self)` | 单位赎回成本（净消耗 ÷ 赎回小时）。⚠️ 2026-11-05 起**阶段账本不再展示**：它除「已过小时」、`unit_cost_floor` 除「全期小时」，并排看必然读出假结论（见 `CHANGELOG` v3.64.24）。函数保留给 `ledger_crosscheck.py` 对账 |

🔴 **两个「由调用方给」的参数，别改回查表**：
`principal` 与 `injected`。阶段账本按 `ledger_config` 与 `selfrun_pool_inject.stage`
算好传进来 —— 一旦函数自己查表，它就只能服务某一个 app，而「同一件事两份实现」
迟早分叉。

🔴 **计算函数一律吃显式区间 `(start, end)`，不吃对象**（v3.64.17 起）。
留一个「还能吃 period」的兼容分支 = 同一个量两个入口，半年后没人知道该用哪个。

🔴 **`avg_daily` 的分母 = `min(区间实际天数, 30)`**（v3.64.39 定口径，用户认可）。
满 30 天后与旧口径**一字不差**；阶段头 29 天不再被摊薄。
旧口径固定除 30，阶段刚开始时日均会被摊薄到只剩实际速度的三分之一左右，
「撑到哪天」因此被读成晚两年多，**差 3.3 倍且页面上看不出来**。

🔴 **短样本仍要自曝**：`compute_avg_daily_self_net_detail()` 把 `sample_days` 与 `thin`
一起交出去。分母改成实际天数之后，`thin` 的含义从「这个数被稀释了」变成
「样本不足 30 天，速度可能还没经历月末大额，外推仍可能偏乐观」。
⚠️ 不要恢复 `net_per_day` 这个键 —— 分母改成实际天数后它与 `avg_daily` 恒等，
两个名字同一把尺子，半年后必然有人以为它们是两件事。

🔴 **`covered_hours` = `hours` 六格（已四舍五入到两位）之和**，不是原始和的取整（v3.64.19）。
屏幕上那六个格子是会被加起来的；总数若按原始值取整，两者会差 0.0x
（示意：六格 1.11 + 2.22 + 0 + 3.33 + 0 + 0.44 = 7.10，而原始和报 7.06）——
读起来像「有一类没算进去」，而「有一类没算进去」正是本函数上一版真正的病。
`toward_ratio` / `fallback_hours` 仍按原始值算（比值与分项不该被显示精度污染）。

### 归因只有一把尺子（v3.64.16 归并）

`compute_time_attribution` 调 `temporal.services.resolve_attribution_detail`，
与时间统计页 / 贡献图 / 仪表盘护栏卡 / 周复盘读**同一列**。
`source` 只有两档：`default`（映射表那列写着的值）/ `fallback`（没设 ⇒ 兜底「成长」）。

🔴 **为什么删掉自管的那套规则**：它是 `default_attribution` 的影子副本
（映射表改 L1 时顺带写一条 `priority=100` 的 `task_name` 规则），
却只覆盖被改过的那几个任务名；而本页当时拿「命中规则」当统计口径 ⇒
未覆盖的记录**静默不计**。一个两天窗口里，「成长」只被算进去一小部分、「谋生」恒为 0，
覆盖率却仍显示八成多 —— 少算掉的部分没有任何提示。

⚠️ 回归红线：`hours` 之和必须等于 `covered_hours`（该窗口**除睡眠外**的记录时长）。
`fallback_hours` 单独报出来，让页面能说清「其中多少是按兜底归的」——
但**不能**把它排除在六类之外（那就回到了「命中才算」的老毛病）。

### 睡眠两边都不计（v3.64.22）

覆盖率的分母是「天数 × 每天可支配小时」（`THEORETICAL_DAILY_HOURS`，2026-11-05 由 12h 调到 14h），
睡眠本来就不在这段时间内。旧版分子却把睡眠算进去 ⇒ 记录越全、覆盖率越高：两天就能冲到一百四十以上。
那不是「记得比可支配的多」，是同一屏上下两个数用了两把尺子；旧版只好在界面上
写一句「记录含睡眠，可能超过 100%」—— 那是给口径错配写的说明书。

🔴 这个常量**只在这里定义一次**，页面文案的「按每天 Nh」由 `theoretical_daily_hours` 下发；
   前端写死 12 / 14 就等于复制了一份阈值（v3.64.25 之前账本页就是这么硬写的）。

现在睡眠在**摊进六类之前**就被跳过（名单取 `temporal.services.contrib_excluded_names()`
= 常量名单 ∪ 角色为睡眠类，与贡献图同一份）：

- `covered_hours` / `coverage_rate` / `toward_ratio` 的分子分母都不含睡眠
- 剔除量单列 `excluded_sleep_hours`，且 `covered_hours + excluded_sleep_hours`
  == 区间内全部记录时长（两个数在屏幕上是相邻的，用户真的会加）
- 🔴 **必须可见**：页面印「睡眠 12.2h 已剔除（夜间 + 午睡）」。删掉这一句，
  「维持」会凭空少 12h 而屏幕上没有任何线索

⚠️ 名单含**午睡**，而午睡其实落在醒来那 16h 内 —— 严格说可支配，剔掉略保守。
选择与贡献图同一份名单，而不是在账本里另立一套「只剔夜间」的判据：
同一件事两把尺子，迟早出现「账本维持 15.8h、贡献图维持 3.6h」两页都看着合理的局面。

### 归因词表

单一真源是 `apps.temporal.constants.ATTRIBUTION_CHOICES`，**本模块不自存副本**
（v3.58.10 前存过一份，改词必漂移）。「任务名 → 归因」的匹配只有 temporal 一处实现
（`resolve_attribution_detail`）。

## API Endpoints

**一条都没有。** `urls.py` 里是空 `urlpatterns`（六条旧端点自然 404）。

| 旧端点 | 现在怎么办 |
|---|---|
| `GET/PUT /api/redemption/` | 窗口改阶段起止；本金走 `PATCH /api/selfrun/stages/<pk>/ledger-config/` |
| `POST pause/` `resume/` | `POST /api/selfrun/stages/<pk>/pause/`（阶段暂停，语义更完整） |
| `GET/POST injects/` | 表已搬到 `selfrun_pool_inject`，随阶段走（本期未开界面） |
| `GET stats/` | `GET /api/selfrun/stages/<pk>/ledger/` |
| `POST sync-scenario/` | 删除。它把赎回池实算值写进 `WealthCurrentScenario` 单例 —— 一个动作改了另一个模块的单例，且没有回滚路径 |
| `GET attr-rules/` | v3.64.16 已下线 |

## 边界

- 窗口**之前**的 `period_tag` 全为 `NULL` 是**正确结果、不是 bug**。
- 本模块**只读**归因；改归因的唯一入口是 temporal 的映射表。
- 生存资源页的覆盖率分母借的是「当前长阶段」的窗口
  （`wealth.services.survival_service._stage_window`），本模块不参与。
