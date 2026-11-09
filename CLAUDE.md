# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## Project Overview

Sycamore —— 个人人生管理系统，为单人使用设计。聚合每日记录、目标、项目、健康、财务、人际关系、旅行日志和数字资产于统一仪表盘。

- 后端: Django 6.0.4 + DRF + django-cors-headers
- 前端: Vue 3 + TypeScript + Vite 7 + Pinia + Vue Router + Element Plus + ECharts
- 数据库: MySQL | Python 3.14 | Node ^20.19.0 || >=22.12.0
- 虚拟环境: `.venv/`（项目根目录）

## Architecture

### Backend (`backend/`)

- App 按生命维度划分，每个 App 自包含（models/services/views/urls）
- 瘦 view，胖 service：业务逻辑放 `services.py`，views 只做路由和参数校验
- ModelViewSet 模式，除非有特殊需求（wealth 既有「按 managed 表走 ModelViewSet」的 CRUD 端点，也有「一次算全」的 APIView 汇总端点，两种并存）
- 序列化器显式声明字段，不用 `__all__`
- 环境配置分离：settings 分 base / development / production

```
backend/
├── sycamore/         # 项目配置（settings/urls/asgi/wsgi）
├── apps/             # 22 个 app（INSTALLED_APPS 为准）
│   ├── core/         # 基础设施（分页 / 用户画像 / 通知）
│   ├── temporal/     # 时间感知（日记 + 时间统计 + 活动追踪）
│   ├── health/       # 健康管理
│   ├── wealth/       # 财务管理
│   ├── relation/     # 关系管理
│   ├── book/         # 书籍阅读
│   ├── sugar/        # 小确幸
│   ├── dance/        # 舞蹈记录
│   ├── travel/       # 旅行记录
│   ├── reward/       # 奖励池
│   ├── goals/        # 目标管理
│   ├── redemption/   # 赎回期**计算库**（2026-11 起无页面/无接口/无表；「三年赎回期」已是自我运转下的长阶段）
│   ├── selfrun/      # 自我运转（KPI 制定→执行→复盘→事后分析）
│   ├── works/        # 作品（「值得留」唯一真源，兼自我运转「留下件数」取数）
│   ├── showroom/     # 展厅（对外输出：引用 works，叙事手写）
│   ├── lifesample/   # 人生样本
│   ├── treasure/     # 好东西
│   ├── food/         # 美食记录
│   ├── inbox/        # 收件箱
│   ├── dams/         # 数字资产
│   ├── toolkit/      # 工具箱
│   └── summary/      # 跨模块聚合
├── manage.py
└── requirements.txt
```

### Frontend (`frontend/`)

- 模块自包含：`modules/<模块>/` 含 views / stores / api / types / components
- 路径别名 `@/` 指向 `src/`
- 模块间不互相引用 store；跨模块数据在 `core/dashboard` 聚合
- core/：admin / analysis / auth / dashboard / notifications / privacy
- shared/：跨模块组件 / composables / utils / styles

```
frontend/src/
├── modules/      # 业务模块（每个模块含 views/stores/api/types/components）
├── core/         # 基础设施（admin/analysis/auth/dashboard/notifications/privacy）
├── shared/       # 共享（components/composables/config/api/styles/utils）
├── router/
├── App.vue
└── main.ts
```

## Common Commands

### Backend
```bash
.venv/bin/python backend/manage.py runserver
.venv/bin/python backend/manage.py makemigrations
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py test apps/wealth
.venv/bin/python backend/manage.py shell
.venv/bin/python backend/manage.py init_week_calendar --user_id=1 --birth_date=1995-01-01
```

### Frontend
```bash
cd frontend && npm run dev          # Vite 开发服务器
cd frontend && npm run build        # 类型检查 + 生产构建
cd frontend && npm run lint         # oxlint + eslint
cd frontend && npm run format       # Prettier
cd frontend && npm run type-check   # vue-tsc
cd frontend && npm run test:e2e     # Playwright
cd frontend && npm run preview      # 预览生产构建
```

### Node version
```
^20.19.0 || >=22.12.0
```

### Docker（整站）
```bash
cp .env.example .env                # 改 SECRET_KEY / DB_PASSWORD
docker compose up -d --build        # db(3307→3306) + backend(8000) + frontend(80)
docker compose logs -f backend
```

### 数据迁移
```bash
.venv/bin/python backend/manage.py migrate_dance   # 舞蹈
.venv/bin/python backend/manage.py migrate_health   # 健康
.venv/bin/python backend/manage.py migrate_atracker # 活动追踪
```

## Coding Standards

### Python
- 所有函数参数和返回值必须有类型注解，使用 `|` 语法
- Docstring：中文，一行概述 + Args/Returns
- 模型字段加 `verbose_name`（中文），必要时加 `help_text`
- Services：`@staticmethod`，纯函数风格
- 导入顺序：标准库 → Django → 第三方 → 本地应用

### TypeScript / Vue
- 组件：`<script setup lang="ts">` + `defineProps<T>()`
- Store：Composition API（`defineStore` setup 函数形式）
- API：统一走 `api/` 模块，组件不直接调 axios
- 导入路径：同模块 `./`，跨模块 `@/`
- SCSS：使用 `_variables.scss` 中的 CSS 变量

### 命名规范
| 类型 | Python | TypeScript |
|------|--------|------------|
| 文件 | snake_case | camelCase / PascalCase.vue |
| 类/组件 | PascalCase | PascalCase |
| 函数/方法 | snake_case | camelCase |
| 常量 | UPPER_SNAKE | UPPER_SNAKE |

### 依赖规则
- 允许：任何模块 → shared/ | 任何模块 → core/ | core/dashboard/analysis → 任意模块
- 禁止：modules/A/stores → modules/B/stores | modules/A/views → modules/B/components | 循环依赖

### 提交信息
中文，格式：`模块名: 简要说明`

## 重要设计决策

- **temporal** 合并了三个旧应用：oneday(日记) + times(时间统计) + atracker(活动追踪)。**时间记录的来源只有一列依据** `import_batch`（外部表加不了列），分类只在后端做一次（`classify_source` / `list_record_sources`），前端不写中文映射；`unlabeled`（早期没留标记）与 `other`（有批次号但没认出来）**分开显示**，筛错来源词 ⇒ 400 不返回空列表。**CSV 导入是两步**（v3.64.32）：`previewCsv()` 不写库 → 勾掉不要的行 → `importCsv(file, skipRows)` 落库，勾掉的 `row_no` 原样回传；重叠分 `review` / `likely_dup`（列出）与 `contained` / `edge`（只计数）。**成长计时是映射编辑器上的显式开关**（v3.64.11，`temporal_task_meta.counts_growth`，`None ≠ False`），改 L2 不连带改它；仪表盘「今天的三条线」由 `/api/temporal/tasks/daily_guards/` 给睡眠 / 午睡 / 流失的实测值与阈值（流失 ≤ 4h，v3.64.13–14）。
- **nourishment** 只是**菜单分组名**（「精神滋养」：书籍 / 小确幸 / 好东西 / 人生样本），**不是前端模块** —— `modules/nourishment/` 不存在，`/nourishment` 路由是直接指向 `sugar/views/SugarView.vue` 的历史别名
- **wealth 热力图**：数据层 61年×52周 = 3172 单元格（`wealth_life_week_calendar`，18~78 岁，`global_week_index` 原点锚定 18 岁），复用 `wealth_bill_list`，支持历史(红绿) + 推演(蓝) 双层叠加。**计量窗口 = 19~60 岁**（`wealth/constants.py` 的 `WINDOW_START_AGE / WINDOW_END_AGE / WINDOW_WEEKS=2184`）：展示（热力图行）、统计（`summary` 的已度过/收支）、推演（`calculate_coverage(max_age=WINDOW_END_AGE)`）统一按此窗口；**数据层与索引原点不动**（18 岁是 `global_week_index` 原点，改则全表错位）
- **wealth 月度日历**：6×7 CSS Grid + 农历/节气 + 7级颜色编码
- **wealth 生存资源盘点**：盘的是**物**（吃/穿/用/数字），与「资产盘点」（盘钱）刻意分开命名 —— 钱 = `WealthAsset*`，物 = `Survival*`。配餐按**餐位**建模：同主食位可替代**求和**、跨必配位**取最小**（木桶效应只在必配位成立）；PERT 三档由**每日消耗量**派生（省 2 / 常 3 / 放 4 餐，按基准刻度等比缩放），派生值一律运行时算、**不落库**；算不出来返回 `null` + `issues`、**绝不返回 0**；删除一律不级联（有引用返回 400 + 提示）。**生存覆盖率的分母窗口读当前长阶段**（`survival_service._stage_window()`，v3.64.20，「三年赎回期」即该长阶段），取不到 = 窗口未配置，**不兜默认窗口**。
- **wealth 现金流推演**：核心问题是「钱还能撑多久」而不是「钱怎么分配」——正算「给每日预算 → 算能撑多久」与反算「给本金 + 目标时长 → 算每日可提取额」共用同一套现金流假设（每日先扣款、再按日利率对余额复利），可闭环互验；输入即算、**零写库**（纯试算）
- **reward 奖励池**：单例模式，通过 `RewardPoolService` 统一管理加减；**余额 / 累计获得 / 累计提取 / 四源合计全部由流水聚合派生**（不再读池表累加字段），删除流水按方向回退；金额出参统一 `core.fields.AmountNumberField`（出参 number / 入参 Decimal）。
- **sugar→reward 同步**：sugar service 层直接调用 `RewardPoolService`，不经过 signal；**奖励金额 = 快乐程度（5–20）唯一刻度**，没有独立金额入口，`perform_create` 事务包裹，`perform_update` 三级判断（显式金额 → 程度真变才重算 → 否则不动），`_calculate_reward_amount` 是死代码。
- **礼物自动检测**：`_check_gift_availability()` 在每次池变动后扫描 pending/waiting 状态切换
- **dams** 只有 CRUD + 注意力分区（`files/attention_map/`）与人工整理标记，**没有扫描 / 定时任务**；项目未引入 Celery，任何「后台自动扫描」都不存在
- **goals** 进度始终计算得出(editable=False)；日历接口 `exclude_abandoned_goals=1` 只隐藏**已放弃且未完成**的里程碑，已完成的保留（历史日程可回看），默认不过滤（详情页要看得见全部子项）。
- **selfrun 自我运转**：8 张 managed 表，生命周期 = 制定 → 执行 → 复盘 → 事后分析。**入口在顶栏右上角下拉，侧边栏不列**（路由全保留、空分组保留）。**阶段分两层**（v3.64.17）：`is_long_stage` 长阶段只汇总、零 KPI，其下才挂小阶段；「同一时间只允许一个 active」改为**同一 `parent` 下**唯一；KPI 只挂叶子，`get_open_stage()` 只返回叶子（判据是「有 active KPI」），长阶段另给 `get_open_long_stage()`；`POST /stages/` 的 `shape=leaf|long` 必须显式声明（metrics 空又没声明 ⇒ 400）。**阶段账本**（v3.64.18–19）`GET /stages/<pk>/ledger/` 只读现算、零写库，`PATCH .../ledger-config/` 只改本金；生存资源覆盖率的分母窗口读当前长阶段（v3.64.20，「三年赎回期」即该长阶段）。周（有没有在动）与月（动出结果没有）是**两把正交的尺子**；判定阈值只在 `constants.PERIOD_VERDICT_BANDS`（≥80 / 60 / 40，`<40` 兜底「活着」），前端 0 个阈值数字；阶段天数用后端 `days_label`（`min(today, end_date)`）、阶段区间用 `range_label`（`起 ~ 止（N 天）`，起止日期只此一份），前端零计算。**派生值不落库**，例外只有快照（`Period.readings` / `Stage.summary_snapshot`）；**目标值是输入** ⇒ 按期修订落 `selfrun_metric_plan`（同期的 `single` 压过 `from`），**不许改 `metric.goal_value` 代替**。归档 = 定格，写入门一起关（补记 / 冲销 / 改目标返回 409）；重开是改历史判定的唯一出口且必须写原因。`template_key` 是字符标记不是 FK；取数器只许命中 `READER_KEYS` 白名单（不做任意查询构建器）；`empty`（真没做）进分母，`unknown` / `skipped` 不进。**成长小时数只认映射编辑器的「成长计时」开关**（v3.64.11，取数器 `growth_hours` 读 `temporal_task_meta.counts_growth`）：`where` 一概不读，改 L2 不连带改它；`counts_growth` 不传 = 不动（`None ≠ False`）。**月度档位只来自三问**（v3.64.6）：三问没答完 = 未判定（`value=''` + `basis='pending'`，界面「待答三问」），**不拿 KPI 顶档**；月度归档必须三问全答（否则 400 不落行），归档后补答不改档（要改走重开）—— 页头/历史行的分数必须与本行档位同源（周 `达标 x/y`、月 `三问 x/3`）。**账本口径**（v3.64.22–27）：覆盖率分子分母都**不含睡眠**（`excluded_sleep_hours` 单列，六格之和 == `covered_hours`），分母 `redemption.services.THEORETICAL_DAILY_HOURS = 14`；「每天可提取」只用 `daily_allowance`（余额 ÷ 剩余天数，不印 ¥/h）；池注入 = 给账单打标（`selfrun_pool_inject.bill_id`），钱只录一次；表缺失返 **503 + `detail`**，不兜成「注入 0 / 没有长阶段」。
- **summary 综合进度看板**：一次请求只取一份事实 —— `ProgressAggregator.request_scope()` 在 `dispatch` 开请求级作用域，**禁用进程级缓存**（归因规则用户可改，缓存会让新口径不生效且看不出来）；月度过滤按 `mon` 字符串比较，不改成 `date.month`。
- **works 作品**：「值得留」的唯一真源是 `WorkCapture`，七个入口（里程碑 / 收件箱 / 读书 / 日记 / 摘录 / AI 问答 / 档案馆）共用一张表，**绝不给源表加列或另开清单**。身份键必须是 `(source_type, source_id)` 复合（裸 id 会跨表撞号）。捕获存快照（`title` / `excerpt`），源记录改名或删除后仍可读；打勾幂等、合成可逆（删作品 ⇒ 来源回待提炼）。作品媒体是媒体真源，展厅只引用不重复上传。自我运转「留下件数」直接数本模块（`selfrun.readers.works_count`），不另做手工计数。作品类型九类（`WORK_KIND_CHOICES`，v3.64.30 起含绘画 / 刺绣、`craft` 改为「其他手作」），月度 KPI 可 `where.work_kind` 按类型自动数；类型写错 ⇒ `ValueError`，**绝不返回 0**。
- **showroom 展厅**：对外输出端口，4 张表（`profile` 单例 / `case` / `skill` / `work`），口径是**数据引用、叙事手写**；`ShowroomWork` 引用 `works.Work`，靠 `title_snapshot` + 手写导语策展。预览只下发 `is_visible` 项；端点与全项目一致无认证（单用户系统）。
- **前端错误提示统一走 `apiErrorText(err, fallback)`**（v3.64.8）：4xx 的字段级原因照实显示，只有 5xx / 无响应才用兜底话术；各处不手写「保存失败」，也不让 `apiErrorText` 盖掉后端 `detail`（该原话优先）。**注意它会把所有 5xx 换成兜底** —— 需要透传 503 的「请先执行 migrate」时先取 `detail`。
- **Notification** 无 user 外键（单用户系统）

## Module Details

各模块详细文档见后端 `backend/apps/<模块>/README.md`（前端 `frontend/src/modules/<模块>/README.md`）。

**文档版本标注（统一约定，v3.64.5 起）**

每份模块 README 的 **H1 之后第一个非空行**必须有一行元信息，所有模块逐字同格式（当前 44 份：后端 22 + 前端 22；新增模块照抄）：

```
> 文档对齐 vX.Y.Z ｜ 最后核对 YYYY-MM-DD
```

- **「对齐」** = 本文档按哪个项目版本核对过（取核对当时 `CHANGELOG.md` 最新一条），**不是**「本模块最后一次改动的版本」——后者查不到明确归属，硬写等于编造。
- **「最后核对」** = 最近一次逐条比对代码的日期。只改错字不必动；**判据变了必须两个一起更新**。
- 🔴 正文里的 `（v3.60.20）` / `（v3.62.43 起）` 是**判据溯源**（这条规则从哪版开始这样），与头部文档版本是**两件事**，不许互相替代、也不许因为写了头部就把正文溯源删掉。
- 自查一条命令（有输出 = 这些文件还缺标注）：

```bash
grep -rL "^> 文档对齐 v" backend/apps/*/README.md frontend/src/modules/*/README.md
```
