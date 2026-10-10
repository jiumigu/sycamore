# Toolkit — 工具集

## Models

| Model | Table | 用途 |
|-------|-------|------|
| ToolkitDefinition | toolkit_definition | 工具定义 |
| ToolkitExecution | toolkit_execution | 执行记录 |
| CityCoordinate | toolkit_city_coordinate | 全国行政区划坐标（省/市/区县三级全覆盖，GCJ-02 坐标） |
| TravelRoutePreset | toolkit_travel_route_preset | 旅行路线预设 |
| CareerEnergyAudit | toolkit_career_energy_audit | 职业能量审计（26项指标 + 自动判定 + 建议 + 下次审计提醒） |
| Quote | toolkit_quote | 摘录库（名言 / 典故 / 故事） |
| HealthSelfCheck | toolkit_health_self_check | 身体健康自查 |
| FreeSpendingCalculator | toolkit_free_spending | 自由支配额度计算 |
| FixedExpense | toolkit_fixed_expense | 固定开销计算记录（自定义项目 + 按日/月/年周期统一换算日/月/年开销） |
| HourlyWageRecord | toolkit_hourly_wage | 时薪计算记录（正式/自由职业双模式 + `extra_incomes` 附加收入（名称/金额/日·月·年周期）） |
| ElectricityRecord | toolkit_electricity_record | 用电记录（电表读数 + 自动计算间隔用电量/间隔天数/日均用电量/本月累计，删除后自动重算后续记录；**月度电量与 PERT 估算实时算、不落库**） |
| DecisionTracker | toolkit_decision_tracker | 决策追踪（待决事项） |
| DecisionRecord | toolkit_decision_record | 决策记录（已决结论与回顾） |
| AskScene | toolkit_ask_scene | AI 问答场景 |
| AskTopic | toolkit_ask_topic | AI 问答主题 |
| AskAnswer | toolkit_ask_answer | AI 回答记录 |

## Architecture

```
BaseTool + ToolRegistry（工具定义层）
    ↓ auto_discover
execute() + progress_callback（工具执行层）
    ↓ 同步
ToolkitExecution（任务记录层）
    ↓
前端展示（ToolkitDashboard → ToolDetail → 结果）
```

## 扩展新工具
在 `tools/` 目录下新建文件，继承 `BaseTool`，实现 `get_input_schema()` 和 `execute()`，启动时自动注册。

## API Endpoints

前缀 `/api/toolkit/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /tools/ | 工具列表（含分类聚合） |
| GET | /tools/&lt;tool_key&gt;/ | 工具详情（含 input_schema） |
| POST | /execute/ | 执行工具 |
| GET | /task/&lt;execution_id&gt;/ | 任务状态 |
| GET | /history/ | 执行历史（分页+筛选） |
| POST | /register/ | 注册工具到数据库 |
| POST | /convert_file/ | 文件转换上传操作 |
| GET | /files/&lt;path&gt;/ | 工具产物下载 |
| GET | /cities/ | 城市坐标列表 |
| GET | /cities/search/ | 城市搜索（?q= 模糊匹配） |
| GET | /cities/provinces/ | 省份列表 |
| GET | /cities/cities/ | 地级市列表（?province=） |
| GET | /cities/districts/ | 区县列表（?city=） |
| GET | /travel-routes/ | 旅行路线预设列表 |
| POST | /travel-routes/ | 创建路线预设 |
| PUT | /travel-routes/&lt;id&gt;/ | 更新路线预设 |
| DELETE | /travel-routes/&lt;id&gt;/ | 删除路线预设 |
| GET | /career-energy-audits/ | 职业能量审计列表（DRF 分页） |
| POST | /career-energy-audits/ | 创建审计记录（自动计算总分/判定） |
| DELETE | /career-energy-audits/&lt;id&gt;/ | 删除审计记录 |
| GET | /fixed-expenses/ | 固定开销计算历史列表 |
| POST | /fixed-expenses/ | 创建固定开销记录（按周期统一换算日/月/年开销） |
| DELETE | /fixed-expenses/&lt;id&gt;/ | 删除固定开销记录 |
| GET | /hourly-wage/ | 时薪计算历史列表 |
| POST | /hourly-wage/ | 创建时薪记录（工资 + extra_incomes 附加收入 → 月总收入 ÷ 投入小时） |
| GET/PUT/PATCH/DELETE | /hourly-wage/&lt;id&gt;/ | 时薪记录详情/更新/删除 |
| GET | /electricity-records/ | 用电记录列表（按日期倒序，分页；支持 `?month=YYYY-MM` 筛选，半开区间） |
| GET | /electricity-records/overview/ | 月度用电量（最近 12 个自然月）+ PERT 估算 + 统计卡数据（`?months=3~36`；**不分页，返回对象**） |
| POST | /electricity-records/ | 新增用电记录（自动计算间隔用电/日均/本月累计） |
| DELETE | /electricity-records/&lt;id&gt;/ | 删除用电记录（删除后自动重算后续记录） |
| GET/POST | /quotes/ | 摘录库列表/创建（支持 `?tags=` / `?language=` / `?is_paragraph=` / **`?pool=in\|out`** 按金句池内外筛选） |
| GET | /quotes/stats/ | 摘录统计（`total` / `paragraphs` / `shorts` / `total_reviews` + 金句池分布 `pool_max_len` / `in_pool` / `out_pool`） |
| GET/PUT/DELETE | /quotes/&lt;id&gt;/ | 摘录详情/更新/删除 |
| GET | /quotes/next/ | 金句池取一条（**长度不超上限**，被推得最少的先推 + 同档内收藏优先；首页金句卡用）。上限 = `UserProfile.quote_pool_max_len` |
| GET | /quotes/random/ | 全池等概率随机（长文也在池里）—— **向后兼容保留**，首页已不再使用 |
| GET/POST | /health-self-checks/ | 身体健康自查列表/创建 |
| GET/PUT/DELETE | /health-self-checks/&lt;id&gt;/ | 自查详情/更新/删除 |
| GET/POST | /free-spending/ | 自由支配额度列表/创建 |
| GET/PUT/DELETE | /free-spending/&lt;id&gt;/ | 额度记录详情/更新/删除 |
| GET/POST | /decision-trackers/ | 决策追踪列表/创建 |
| GET/PUT/DELETE | /decision-trackers/&lt;id&gt;/ | 待决事项详情/更新/删除 |
| GET/POST | /decision-records/ | 决策记录列表/创建 |
| GET/PUT/DELETE | /decision-records/&lt;id&gt;/ | 决策记录详情/更新/删除 |
| GET/POST | /ask-topics/ | AI 问答主题列表/创建 |
| GET/PUT/DELETE | /ask-topics/&lt;id&gt;/ | 主题详情/更新/删除 |
| GET/POST | /ask-answers/ | AI 回答列表/创建 |
| GET/PUT/DELETE | /ask-answers/&lt;id&gt;/ | 回答详情/更新/删除 |
| GET/POST | /ask-scenes/ | AI 问答场景列表/创建 |
| GET/PUT/DELETE | /ask-scenes/&lt;id&gt;/ | 场景详情/更新/删除 |
| GET | /ask-topics/summary/ | 采纳结论汇总（**导出用**：只吐采纳回答，产出 .md 文件） |
| GET | /ask-topics/review/ | 回顾视图（**浏览用**：按场景分组 + 冷落天数 + 标记统计，含尚未标结论的主题） |
| GET | /ask-topics/next-conclusion/ | 取一条「有结论的」问答（汇总总览「一条旧结论」卡；库里无结论时返回 `null`）。带 `scene_name`/`topic_title` 出处、`ai_excerpt` 回答摘要与 `ai_excerpt_truncated`/`answer_len` 截断语义、`pool_size` 池子条数 |

## 内置工具

| tool_key | 名称 | 用途 |
|----------|------|------|
| trad2simp | 繁简转换 | 繁体/简体文本互转 |
| gif-compressor | GIF压缩 | 抽帧/缩放/减色/质量压缩 GIF |
| travel-route | 旅行路线推演 | 地图可视化路线推演（**前端主入口已于 2026-09-11 迁入旅行模块 `/travel/route`**，工具箱内为跳转卡片；本 app 的 `TravelRoutePreset` 表与 `/travel-routes/` 接口保持不变） |
| career-energy-audit | 职业能量审计 | 26项指标职业能量评估 + 自动判定 |
| quote-tool | 摘录馆 | 收录名言 / 典故 / 故事 / 好段，区分语言，支持随机回顾 |
| health-self-check | 身体健康自查 | 8 大系统 31 项指标，自动评分 + 趋势对比 + 异常汇总 |
| free-spending | 自由支配额度 | 计算每次消费无需纠结的自由额度，减少日常消费内耗 |
| fixed-expense | 固定开销计算器 | 自定义开销项目，按日/月/年周期统一换算每天/每月/每年开销 |
| hourly-wage | 时薪计算器 | 计算真实时薪，看清时间价值 |
| electricity-record | 用电记录 | 记录电表读数，自动计算间隔/日均/本月累计用电，删除自动重算；月度电量与 PERT 估算在**独立子页面** `/toolkit/electricity-record/monthly`（主页面标题右侧按钮进入，统计卡第 5 张即估算期望值） |
| decision-tracker | 决策追踪器 | 决策前长期观察：日常记录倾向与理由，到期自动汇总分析 |
| ask-library | AI 问答库 | 完整记录 AI 问答（问题原文 + 各 AI 回答 + 会话背景），可检索/打标/导出 md |

⚠️ `tool_key` 一律用**连字符**（`career-energy-audit`），不是下划线 —— 写错会导致 `/execute/` 找不到工具。
