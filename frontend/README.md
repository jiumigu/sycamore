# Sycamore 前端

Sycamore 个人人生管理系统前端，基于 Vue 3 + TypeScript + Vite 7。

## 技术栈

| 层 | 技术 |
|------|---------|
| 框架 | Vue 3 (Composition API, `<script setup>`) |
| 语言 | TypeScript 5.9 |
| 构建 | Vite 7 |
| 状态管理 | Pinia 3 (Setup Store 语法) |
| 路由 | Vue Router 4 |
| UI | Element Plus 2 |
| 图表 | ECharts 6 |
| CSS | SCSS |
| 工具库 | VueUse、dayjs、axios |
| 类型检查 | vue-tsc |
| Lint | oxlint + ESLint |
| 格式化 | Prettier |

## 目录结构

```
frontend/
├── src/
│   ├── modules/          # 业务模块，按生命维度划分
│   │   ├── book/         # 书籍阅读
│   │   ├── dams/         # 数字资产管理
│   │   ├── dance/        # 舞蹈记录（已归档）
│   │   ├── food/         # 美食地图
│   │   ├── goals/        # 目标管理
│   │   ├── health/       # 健康管理（步数、体重、里程碑）
│   │   ├── inbox/        # 收件箱
│   │   ├── nourishment/  # 纯前端聚合模块
│   │   ├── projects/     # 项目管理
│   │   ├── relation/     # 关系管理（含读者群体）
│   │   ├── reward/       # 奖励池 & 礼物清单
│   │   ├── sugar/        # 小确幸
│   │   ├── summary/      # 综合进度看板
│   │   ├── temporal/     # 时间感知（日记 + 时间统计）
│   │   ├── toolkit/      # 工具箱
│   │   ├── travel/       # 旅行记录
│   │   └── wealth/       # 财务管理
│   ├── core/             # 系统基础设施
│   │   ├── analysis/     # 分析统计
│   │   ├── auth/         # 登录认证
│   │   ├── dashboard/    # 仪表盘
│   │   ├── notifications/# 通知
│   │   └── theme/        # 主题
│   ├── shared/           # 跨模块共享
│   │   ├── components/   # 布局/UI/图表/表单组件
│   │   ├── composables/  # 可组合函数
│   │   ├── styles/       # 全局 SCSS 变量与混入
│   │   ├── types/        # 通用类型定义
│   │   └── utils/        # 工具函数（含 axios request）
│   ├── router/           # 路由配置
│   ├── App.vue           # 根组件
│   └── main.ts           # 入口
├── .env.development      # 开发环境变量
├── .env.production       # 生产环境变量
├── vite.config.ts        # Vite 配置（含 @/ 别名、API 代理）
├── tsconfig.json         # TypeScript 配置入口
├── tsconfig.app.json     # 应用 TS 配置
└── tsconfig.node.json    # Node 端 TS 配置
```

### 模块内部结构

每个业务模块遵循统一目录规范：

```
modules/<模块>/
├── api/          # API 请求函数（axios 封装）
├── components/   # 组件
├── stores/       # Pinia Store
├── types/        # TypeScript 类型定义 & 常量
├── views/        # 页面级组件
└── README.md     # 模块文档
```

## 开发命令

```bash
# 启动开发服务器（默认 :5173，自动代理 /api → :8000）
npm run dev

# 类型检查 + 生产构建
npm run build

# 仅类型检查
npm run type-check

# Lint（oxlint + eslint）
npm run lint

# 格式化
npm run format

# E2E 测试（Playwright）
npm run test:e2e

# 预览生产构建
npm run preview
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VITE_API_BASE` | `/api` | API 请求前缀 |
| `VITE_MEDIA_BASE` | `/media` | 静态资源前缀 |

## 开发规范

参见项目根目录 `CLAUDE.md`，关键点：

- 组件使用 `<script setup lang="ts">` + `defineProps<T>()`
- Store 使用 Composition API（`defineStore` setup 函数形式）
- API 统一走 `api/` 模块，组件不直接调 axios
- 导入路径：同模块用 `./`，跨模块用 `@/`
- 模块间不互相引用 store
- CSS 使用 SCSS 变量

## 依赖规则

```
允许: 任何模块 → shared/ | 任何模块 → core/ | core/dashboard → 任意模块
禁止: modules/A/stores → modules/B/stores | 循环依赖
```
