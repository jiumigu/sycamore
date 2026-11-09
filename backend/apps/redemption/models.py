"""赎回期 · 模型层（2026-11-02 起**已无模型**）

这个 app 现在只剩一层东西：`services.py` 里那几个**纯计算函数**
（区间内六类小时 / 现金池余额 / 归属分档 / 单位成本）。它们被
`selfrun.services.stage_ledger` 直接调用 —— 「三年赎回期」已经变成自我运转下的
一个长阶段，阶段账本才是它的界面与入口。

三个模型在 v3.64.20 退役，理由各不同：

| 表 | 退役原因 |
|---|---|
| `redemption_period` | 窗口 / 本金 / 暂停状态全部搬到 `selfrun_stage`（`start_date`/`end_date`/`ledger_config`）—— 同一件事两处存，改一处另一处就不认 |
| `redemption_week_snapshot` | 从建表起 **0 写入 0 读取**，且加 L1「体验」时没补列（启用必漏数） |
| `redemption_pool_inject` | 搬到 `selfrun_pool_inject`：注入流水属于阶段，留在本 app 会让 selfrun ↔ redemption **双向依赖** |

🔴 迁移 `0010` 是 `DeleteModel × 3`，**只写不跑**：删表不可逆，要用户先备份
`db_backups/` 再手动执行。代码这边已不读不写这三张表，不跑迁移只是表还在。
"""
