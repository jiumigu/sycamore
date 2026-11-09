# 展厅（Showroom）

> 文档对齐 v3.64.5 ｜ 最后核对 2026-10-29

Sycamore 的**对外输出端口**——一个可被潜在客户走进去看的「策展空间」。

## 定位

- 不是仪表盘（给自己看）、不是简历（只有证据层）、不是个人主页（只有一面）。
- 核心叙事：**能力 → 案例 → 产品**（一个品牌、两个馆）。
- 核心边界：**数据引用、叙事手写**——数据从 Sycamore 里「选」，叙事在策展层「写」。

## 表

| 表 | 作用 | 数据来源 |
|---|---|---|
| showroom_profile | 品牌层（单例） | 纯手写 |
| showroom_case | 能力馆案例 | 手写为主，预留引用 |
| showroom_skill | 能力馆技能 | 纯手写 |
| showroom_work | 作品馆作品 | 引用 works.Work + 手写导语 |

## 端点

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/PUT | /api/showroom/profile/ | 品牌单例（无行时 GET 返回空骨架） |
| GET/POST | /api/showroom/cases/ | 案例列表 / 新建（裸数组，不分页） |
| GET/PUT/PATCH/DELETE | /api/showroom/cases/&lt;pk&gt;/ | 案例 CRUD |
| GET/POST | /api/showroom/skills/ | 技能列表 / 新建（裸数组，不分页） |
| GET/PUT/PATCH/DELETE | /api/showroom/skills/&lt;pk&gt;/ | 技能 CRUD |
| GET/POST | /api/showroom/works/ | 馆藏作品列表 / 新建（裸数组，不分页） |
| GET/PUT/PATCH/DELETE | /api/showroom/works/&lt;pk&gt;/ | 馆藏作品 CRUD（引用 `works.Work`） |
| GET | /api/showroom/meta/ | 界面枚举（技能熟练度三级，随接口下发） |
| POST | /api/showroom/media/ | 媒体上传（multipart 字段 `file`） |
| GET | /api/showroom/preview/ | 预览聚合（只读，**只下发 `is_visible` 项**） |

## 边界

- 作品馆的 `ShowroomWork` 只是**引用** `works.Work` + 手写导语 / 快照；媒体真源在作品库，**不重复上传**。
- 端点与全项目一致（单用户系统，无认证）；对外分享时靠 `is_visible` 控制可见项。
- 技能熟练度只有三级（精通 / 熟练 / 了解），文案由 `constants.SKILL_LEVEL_OPTIONS` 下发，前端不另抄。
