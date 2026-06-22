# Sycamore

个人人生管理系统 —— 聚合每日记录、目标、项目、健康、财务、人际关系、旅行和数字资产的统一仪表盘。

## 技术栈

| 层 | 技术 |
|------|---------|
| 后端 | Django 6.0 + DRF + django-cors-headers |
| 前端 | Vue 3 + TypeScript + Vite 7 + Pinia + Vue Router + Element Plus + ECharts |
| 数据库 | MySQL |
| Python | 3.14 |
| Node | ^20.19.0 \|\| >=22.12.0 |

## 快速开始

```bash
# 后端
.venv/bin/python backend/manage.py runserver

# 前端
cd frontend && npm run dev
```

## 项目结构

```
sycamore/
├── backend/
│   ├── sycamore/          # Django 项目配置（settings, urls）
│   ├── apps/              # 所有 Django App，按生命维度划分
│   │   ├── temporal/      # 时间感知（日记 + 时间统计 + 活动追踪）
│   │   ├── health/        # 健康管理（1亿步目标）
│   │   ├── wealth/        # 财务管理（热力图 + 月度日历）
│   │   ├── relation/      # 关系管理（能量分 + 质量诊断）
│   │   ├── book/          # 书籍阅读
│   │   ├── sugar/         # 小确幸（自动同步奖励池）
│   │   ├── dance/         # 舞蹈记录
│   │   ├── travel/        # 旅行记录
│   │   ├── reward/        # 奖励池（单例模式）
│   │   ├── goals/         # 目标管理（Goal → Milestone → Action）
│   │   ├── projects/      # 项目管理
│   │   ├── dams/          # 数字资产管理（Celery 自动化）
│   │   ├── toolkit/       # 工具集（可扩展工具箱）
│   │   ├── summary/       # 跨模块进度聚合
│   │   ├── inbox/         # 收件箱（大脑的缓冲区，支持转为目标/能量）
│   │   └── core/          # 系统基础设施
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── modules/       # 业务模块（含 views, stores, api, types, components）
│       ├── core/          # 系统基础设施（dashboard, auth, theme, analysis）
│       ├── shared/        # 跨模块共享组件/composables/utils
│       └── router/        # 路由配置
├── .venv/                 # Python 虚拟环境
└── CLAUDE.md              # Claude Code 操作指南
```

各模块详细文档见各目录下的 README.md。
