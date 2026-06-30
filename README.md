# Sycamore - 个人人生管理系统

一个覆盖人生七大维度的私人管理系统：时间感知、目标达成、财富管理、关系维护、健康追踪、知识沉淀、自我认知。

## 技术栈

| 层 | 技术 |
|------|---------|
| 后端 | Django 6.0 + DRF + django-cors-headers |
| 前端 | Vue 3 + TypeScript + Vite 7 + Pinia + Vue Router + Element Plus + ECharts |
| 数据库 | MySQL |
| Python | 3.14 |
| Node | ^20.19.0 \|\| >=22.12.0 |

## 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/jiumigu/sycamore.git
cd sycamore

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，修改 SECRET_KEY 和 DB_PASSWORD

# 3. 启动
docker compose up -d --build

# 4. 访问
# 前端：http://localhost
# 后端：http://localhost:8000/api/
# 管理后台：http://localhost:8000/admin/
```

### 方式二：本地开发

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# 前端
cd frontend
npm install
npm run dev
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

## 功能模块

| 模块 | 功能 |
|------|------|
| 📅 时间感知 | 日记流、时间统计、活动追踪、日程视图、周度追踪 |
| 🎯 目标管理 | Goal→Milestone→Action 三层模型、良品率、快速创建 |
| 💰 财富管理 | 现金流热力图、月度日历、月度复盘、现金盘点、定期存款 |
| 👥 关系管理 | 联系人、读者群体、成长记录、月末盘点 |
| 🏃 健康管理 | 步数追踪、体重管理、好朋友跟踪、身体健康自查 |
| 📚 知识沉淀 | 书籍管理、摘录馆（名言/典故/故事） |
| 🍰 小确幸 | 快乐记录、偏好图谱、快乐银行联动 |
| 🧭 自我认知 | 个人画像、环境校准、职业能量审计、决策日志 |
| 🛠️ 工具箱 | 时薪计算器、自由支配额度、旅行路线推演、复盘模板 |

## 设计理念

- 单人系统，所有数据本地存储
- 进度自动计算，不给自己骗自己的机会
- 模块间松耦合，通过 summary 聚合
- 支持脱敏开关，安全分享截图

## 开源协议

MIT License
