# Reward — 奖励池

## Models
| Model | Table | 用途 |
|-------|-------|------|
| RewardPool | reward_pool | 单例奖励池 |
| RewardTransaction | reward_transaction | 奖励流水 |
| GiftList | gift_list | 礼物清单 |

## 交易类型 (TRANSACTION_TYPES)

| 类型 | 用途 |
|------|------|
| milestone_complete | 里程碑完成 |
| milestone_update | 里程碑修改 |
| milestone_delete | 里程碑删除 |
| sugar_create | 小确幸新增 |
| sugar_update | 小确幸修改（快乐程度变化） |
| sugar_delete | 小确幸删除 |
| gift_exchange | 礼物兑换 |
| withdraw | 提取 |
| inbox_complete | 收件箱完成 |
| goal_complete | 目标完成 |

## 核心逻辑（services.py）
- 奖励池是单例模式：`_get_or_create_pool()` 自动创建
- 所有奖励变动（add/adjust/deduct）自动调用 `_check_gift_availability()`
- `_check_gift_availability()` 扫描全部 pending/waiting 礼物，余额≥预期价则切为 waiting
- `exchange_gift()` 校验 waiting 状态 + 余额充足，扣池后记流水

## 礼物状态流
`pending(余额不足) ↔ waiting(可兑换) → redeemed/cancelled(终态)`

## API Endpoints

前缀 `/api/reward/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /pool/ | 奖励池概览 |
| GET | /transactions/ | 流水列表（分页+筛选） |
| GET | /stats/sources/ | 奖励来源统计 |
| GET/POST | /gifts/ | 礼物列表/新建 |
| GET | /gifts/stats/ | 礼物统计 |
| GET/PUT/DELETE | /gifts/<id>/ | 礼物详情/更新/删除 |
| POST | /gifts/<id>/redeem/ | 兑换礼物 |
| POST | /gifts/<id>/cancel/ | 取消礼物 |
