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
- ModelViewSet 模式，除非有特殊需求（wealth 模块使用 APIView）
- 序列化器显式声明字段，不用 `__all__`
- 环境配置分离：settings 分 base / development / production

```
backend/
├── sycamore/         # 项目配置（settings/urls/asgi/celery）
├── apps/
│   ├── core/         # 基础设施
│   ├── temporal/     # 时间感知
│   ├── health/       # 健康管理
│   ├── wealth/       # 财务管理
│   ├── relation/     # 关系管理
│   ├── book/         # 书籍阅读
│   ├── sugar/        # 小确幸
│   ├── dance/        # 舞蹈记录
│   ├── travel/       # 旅行记录
│   ├── reward/       # 奖励池
│   ├── goals/        # 目标管理
│   ├── projects/     # 项目管理
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
- core/：dashboard / auth / notifications / theme / analysis
- shared/：跨模块组件 / composables / utils / styles

```
frontend/src/
├── modules/      # 业务模块（每个模块含 views/stores/api/types/components）
├── core/         # 基础设施（dashboard/auth/theme/analysis/notifications）
├── shared/       # 共享组件（layout/ui/charts/forms）+ composables/utils/styles
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
- **nourishment** 是纯前端模块，聚合 book/dance/sugar 后端
- **wealth 热力图**：61年×52周 = 3172 单元格，复用 `wealth_bill_list`，支持历史(红绿) + 推演(蓝) 双层叠加
- **wealth 月度日历**：6×7 CSS Grid + 农历/节气 + 7级颜色编码
- **reward 奖励池**：单例模式，通过 `RewardPoolService` 统一管理加减
- **sugar→reward 同步**：sugar service 层直接调用 `RewardPoolService`，不经过 signal
- **礼物自动检测**：`_check_gift_availability()` 在每次池变动后扫描 pending/waiting 状态切换
- **dams 自动化**是后端子包 `apps/dams/automation/`，由 Celery 触发
- **goals/projects** 是平级关系，进度始终计算得出(editable=False)
- **Notification** 无 user 外键（单用户系统）

## Module Details

各模块详细文档见后端 `backend/apps/<模块>/README.md`。
