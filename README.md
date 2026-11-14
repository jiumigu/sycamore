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
│   ├── apps/              # 所有 Django App，按生命维度划分（22 个）
│   │   ├── temporal/      # 时间感知（日记 + 时间统计 + 活动追踪）
│   │   ├── health/        # 健康管理（步数 + 体重 + 身体自查）
│   │   ├── wealth/        # 财务管理（热力图 + 月度日历 + 资产负债/比率/物耗盘点）
│   │   ├── relation/      # 关系管理（能量分 + 质量诊断）
│   │   ├── book/          # 书籍阅读
│   │   ├── sugar/         # 小确幸（自动同步奖励池）
│   │   ├── dance/         # 舞蹈记录
│   │   ├── travel/        # 旅行记录
│   │   ├── reward/        # 奖励池（单例模式）
│   │   ├── goals/         # 目标管理（Goal → Milestone → Action）
│   │   ├── redemption/    # 赎回期计算库（已并入自我运转的长阶段）
│   │   ├── selfrun/       # 自我运转（KPI 制定→执行→复盘→事后分析）
│   │   ├── works/         # 作品（把散落的复盘打勾收口成一件东西，并给出出口）
│   │   ├── showroom/      # 展厅（对外输出的策展空间：能力 → 案例 → 产品）
│   │   ├── lifesample/    # 人生样本
│   │   ├── treasure/      # 好东西
│   │   ├── food/          # 美食记录
│   │   ├── dams/          # 数字资产管理
│   │   ├── inbox/         # 收件箱（大脑的缓冲区，支持转为目标/能量）
│   │   ├── toolkit/       # 工具集（可扩展工具箱）
│   │   ├── summary/       # 跨模块进度聚合
│   │   └── core/          # 系统基础设施
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── modules/       # 业务模块（含 views, stores, api, types, components）
│       ├── core/          # 系统基础设施（admin, analysis, auth, dashboard, notifications, privacy）
│       ├── shared/        # 跨模块共享组件/composables/utils
│       └── router/        # 路由配置
└── CLAUDE.md              # AI 协作说明
```

## 功能模块

| 模块 | 功能 |
|------|------|
| 📅 时间感知 | 日记流；任务清单（实时计时 / CSV 两步导入并预演 / 每条记录可追溯到来源批次）；时间统计报表；活动追踪与日程视图；仪表盘「今天的三条线」——睡眠、午睡、流失，各给实测值与阈值 |
| 🎯 目标管理 | Goal → Milestone → Action 三层模型、良品率、快速创建 |
| 💰 财富管理 | 现金流热力图、月度日历、月度复盘、定期存款；资产盘点（科目主数据 / 资产负债表快照 / 负债与应收台账 / 分类规则 / 六项规划比率）；生存资源盘点（吃穿用还能撑多久） |
| 👥 关系管理 | 联系人、读者群体、成长记录、月末盘点 |
| 🏃 健康管理 | 步数追踪、体重管理、身体指标跟踪、身体健康自查 |
| 📚 知识沉淀 | 书籍管理、摘录馆（名言 / 典故 / 故事） |
| 🍰 小确幸 | 快乐记录（5–20 分，分数即奖励金额，单一刻度）、偏好图谱、奖励池联动 |
| 🧭 自我认知 | 职业能量审计 |
| 🌱 自我运转 | KPI 的「制定 → 执行 → 复盘 → 事后分析」全生命周期；阶段分两层——长阶段只做汇总，小阶段才跑 KPI；阶段账本把一段长路的钱、时间、作品与小阶段放在一屏；KPI 模板库可自定义（模板是拷贝不是引用，改删都不影响已建阶段）；每周 / 每月可修订下一期目标（「只这一期」或「从这一期起」）；周与月两把正交的尺子（月判定只看三问，未答即待答，不拿 KPI 顶档）；手工补记与撤销冲销；手动归档定格；阶段总结与配置变更留痕 |
| 🛠️ 工具箱 | 时薪计算器、自由支配额度、用电记录、摘录管理、AI 问答库、决策追踪 |
| 🏛️ 展厅 | 对外输出的策展空间：品牌信息 + 能力馆（案例 / 技能）+ 作品馆。数据从系统里「选」，叙事在策展层「写」，媒体不重复上传 |
| 📦 作品 | 一件从经历里长出来、以后还能再用的东西。七个「值得留下」的入口（里程碑完成 / 收件箱完成 / 读完一本书 / 日记标签「值得留」/ 摘录 / AI 问答 / 档案馆评价）汇到「本周状态」页的收口台合成一件，再标出口状态（只给自己 / 准备发 / 已发）；作品类型九类，月度 KPI 按类型自动计数 |

## 菜单与归档

侧边栏支持「常用 / 已归档」两种状态：长期不看的模块可以收进底部的弱化分组，页面顶部会说明它随时可以重新启用。

归档只收敛入口，数据、接口、路由一律保留，因此重新启用不需要改代码、不需要迁移，也可以随时逆操作。想调整的话，在「菜单管理」页把模块勾回常用即可，设置会覆盖代码里的默认值。

## 设计理念

- 单人系统，数据全部存在自己的机器上
- 进度自动计算，不给自己骗自己的机会
- 模块间松耦合，跨模块汇总走 summary 聚合
- 支持脱敏开关，安全分享截图

## 测试

```bash
cd backend && python -m pytest apps
```

## 开源协议

MIT License
