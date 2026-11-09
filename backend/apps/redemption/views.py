"""赎回期 · 视图层（2026-11-02 起**已无端点**）

## 为什么空了

「三年赎回期」不再是一个模块，而是自我运转下的一个**长阶段**。它的界面
（仪表盘 / 归因说明 / 配置）在 v3.64.20 整体下线，读数改由
`GET /api/selfrun/stages/<pk>/ledger/` 提供 —— 那一份是**按任意阶段**算的，
赎回期只是其中一个阶段，不该再有自己的仪表盘。

六条旧端点全部失效（`/api/redemption/`、`pause/`、`resume/`、`injects/`、
`stats/`、`sync-scenario/`）。它们各自的去向：

| 旧端点 | 现在怎么办 |
|---|---|
| `GET/PUT /api/redemption/` | 窗口改阶段起止；本金改 `PATCH /api/selfrun/stages/<pk>/ledger-config/` |
| `POST pause/` `resume/` | 用 `POST /api/selfrun/stages/<pk>/pause/`（阶段暂停，语义更完整） |
| `GET/POST injects/` | 表格已搬到 `selfrun_pool_inject`，随阶段走（本期未开界面） |
| `GET stats/` | 改 `GET /api/selfrun/stages/<pk>/ledger/` |
| `POST sync-scenario/` | 已删。它把赎回池实算值写进 `WealthCurrentScenario` 单例 —— 一个动作改了另一个模块的单例，且没有回滚路径 |

⚠️ 本文件**保留为空壳**：`config/urls.py` 仍 `include('apps.redemption.urls')`，
删空 `urlpatterns` 即可让六条路由 404，不必动工程级路由表。
"""
