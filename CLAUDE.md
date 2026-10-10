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
├── apps/             # 19 个 app（INSTALLED_APPS 为准）
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
│   ├── redemption/   # 三年赎回期
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

- **temporal** 合并了三个旧应用：oneday(日记) + times(时间统计) + atracker(活动追踪)
- **nourishment** 只是**菜单分组名**（「精神滋养」：书籍 / 小确幸 / 好东西 / 人生样本），**不是前端模块** —— `modules/nourishment/` 不存在，`/nourishment` 路由是直接指向 `sugar/views/SugarView.vue` 的历史别名
- **wealth 热力图**：数据层 61年×52周 = 3172 单元格（`wealth_life_week_calendar`，18~78 岁，`global_week_index` 原点锚定 18 岁），复用 `wealth_bill_list`，支持历史(红绿) + 推演(蓝) 双层叠加。**计量窗口 = 19~60 岁**（`wealth/constants.py` 的 `WINDOW_START_AGE / WINDOW_END_AGE / WINDOW_WEEKS=2184`）：展示（热力图行）、统计（`summary` 的已度过/收支）、推演（`calculate_coverage(max_age=WINDOW_END_AGE)`，含赎回期 `sync_to_scenario`）统一按此窗口；**数据层与索引原点不动**（18 岁是 `global_week_index` 原点，改则全表错位）
- **wealth 月度日历**：6×7 CSS Grid + 农历/节气 + 7级颜色编码
- **wealth 生存资源盘点**：盘的是**物**（吃/穿/用/数字），与「资产盘点」（盘钱）刻意分开命名 —— 钱 = `WealthAsset*`，物 = `Survival*`。配餐按**餐位**建模：同主食位可替代**求和**、跨必配位**取最小**（木桶效应只在必配位成立）；PERT 三档由**每日消耗量**派生（省 2 / 常 3 / 放 4 餐，按基准刻度等比缩放），派生值一律运行时算、**不落库**；算不出来返回 `null` + `issues`、**绝不返回 0**；删除一律不级联（有引用返回 400 + 提示）
- **wealth 现金流推演**：核心问题是「钱还能撑多久」而不是「钱怎么分配」——正算「给每日预算 → 算能撑多久」与反算「给本金 + 目标时长 → 算每日可提取额」共用同一套现金流假设（每日先扣款、再按日利率对余额复利），可闭环互验；输入即算、**零写库**（纯试算）
- **reward 奖励池**：单例模式，通过 `RewardPoolService` 统一管理加减
- **sugar→reward 同步**：sugar service 层直接调用 `RewardPoolService`，不经过 signal
- **礼物自动检测**：`_check_gift_availability()` 在每次池变动后扫描 pending/waiting 状态切换
- **dams** 只有 CRUD + 注意力分区（`files/attention_map/`）与人工整理标记，**没有扫描 / 定时任务**；项目未引入 Celery，任何「后台自动扫描」都不存在
- **goals** 进度始终计算得出(editable=False)
- **Notification** 无 user 外键（单用户系统）

## Module Details

各模块详细文档见后端 `backend/apps/<模块>/README.md`。
