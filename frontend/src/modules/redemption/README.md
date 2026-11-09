# Redemption — 三年赎回期前端（**已下线，待人工删除**）

> 文档对齐 v3.64.20 ｜ 最后核对 2026-11-02

## 🔴 这个目录已经不可达

v3.64.20 起「三年赎回期」不再是独立页面：

- **路由**：`/redemption` 只剩一条 `redirect → /selfrun/stage`（旧书签软着陆），
  不再 import 本目录任何组件。
- **菜单**：`menuConfig.ts` 里那一项已撤（同一件事不该有两个顶级入口）。
- **读切走**：时间统计页右栏那块「💎 赎回时间面」改成了「🧭 当前阶段时间面」，
  数据来自 `GET /api/selfrun/stages/<pk>/ledger/`。
- **写切走**：本金改 `PATCH /api/selfrun/stages/<pk>/ledger-config/`，暂停改阶段暂停。
- **接口**：`/api/redemption/*` 六条端点全部 404（后端 `urls.py` 已清空）。

所以本目录下的文件**没有任何入口能打开它们**，留着只是死代码。

## 交给人工删除

AI 不动文件删除（项目铁律）。要清干净，删这三处 + 一个目录：

| 路径 | 说明 |
|---|---|
| `views/RedemptionHub.vue` | 页签容器 |
| `views/RedemptionDashboard.vue` | 仪表盘 |
| `views/AttrRuleEditor.vue` | 归因说明（v3.64.16 起只读） |
| `api/` `types/` | 两个目录整体删 |

**删之前先确认**：`types/redemptionTypes.ts` 里有一行
`export { ATTRIBUTION_META } from '@/shared/config/attributionMeta'`（re-export）。
配色表本体 v3.64.19 已搬到 `shared/config/attributionMeta.ts`，
删本目录不会带走它 —— 但别顺手把 `shared/` 那份也删了（temporal / selfrun 还在用）。

删完跑一次 `npm run type-check`：本目录之外的引用应已归零，有报错就说明还漏了一处。

## 保留这份 README 的意义

留作**退役记录**：它记着这些页面原本各是什么、数据从哪来。
真要看现在的赎回期，去 `/selfrun/stage`（阶段账本）。
