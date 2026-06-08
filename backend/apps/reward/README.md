# Reward — 奖励池

## Models
| Model | Table | 用途 |
|-------|-------|------|
| RewardPool | reward_pool | 单例奖励池 |
| RewardTransaction | reward_transaction | 奖励流水 |
| GiftList | gift_list | 礼物清单 |

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
