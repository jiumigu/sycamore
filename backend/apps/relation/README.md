# Relation — 关系管理

## Models
| Model | Table | 用途 |
|-------|-------|------|
| Relationship | relationship | 关系档案（managed=False） |
| Interaction | interaction | 互动记录（managed=False） |
| ReaderGroup | relation_reader_group | 读者群体 |
| ReaderInteraction | relation_reader_interaction | 读者互动记录（含 6 种互动类型 + 能量分 + 互动日期） |
| ConflictEvent | relation_conflict_event | 冲突事件（情绪等级 1-5、解决状态、关联人、备注、事件时间） |
| ReaderMonthlySummary | relation_reader_monthly_summary | 读者月末盘点（总关注数、新增关注、取关、最佳文章、年度月份唯一约束） |

## Services
- `services/quality_service.py`：自动质量诊断（近20次互动平均能量分 → nourishing/neutral/draining/toxic）
- `services/stats_service.py`：5统计方法（overview/quality_distribution/energy_trend/interaction_frequency/due_reminders）

## Signals
Interaction post_save/post_delete → 触发质量更新

## Constants
- ENERGY_THRESHOLDS：nourishing >=5, neutral >=1, draining >=-3, else toxic
- ENERGY_REVIEW_DAYS=20, DUE_REMINDER_DAYS=30
- 读者互动类型：comment/like/share/follow/unfollow/reward

## API Endpoints

前缀 `/api/relation/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /relationships/ | 列表/创建 |
| GET/PUT/DELETE | /relationships/&lt;id&gt;/ | 详情/更新/删除 |
| GET | /interactions/ | 互动列表（?relationship_id=） |
| POST | /interactions/ | 创建互动 |
| GET/PUT/DELETE | /interactions/&lt;id&gt;/ | 详情/更新/删除 |
| GET | /stats/overview/ | 统计总览 |
| GET | /stats/quality_distribution/ | 质量分布 |
| GET | /stats/energy_trend/ | 能量趋势 |
| GET | /stats/interaction_frequency/ | 互动频率 |
| GET | /stats/due_reminders/ | 待跟进提醒 |
| GET/POST | /conflicts/ | 冲突事件列表（?contact=&status=&start_date=&end_date= 筛选）/ 创建 |
| GET/PUT/DELETE | /conflicts/&lt;id&gt;/ | 冲突事件详情/更新/删除 |
| GET | /conflicts/stats/ | 冲突统计（总次数/未解决数/按联系人汇总/情绪平均值/月度趋势） |
| GET/POST | /reader-monthly-summaries/ | 读者月末盘点列表（?year=&month=&reader_group= 筛选）/ 创建 |
| GET/PUT/DELETE | /reader-monthly-summaries/&lt;id&gt;/ | 盘点详情/更新/删除 |
| GET | /reader-monthly-summaries/stats/ | 盘点年度统计（12 个月汇总 + 最佳月份） |
| GET/POST | /reader-groups/ | 读者群体列表/创建 |
| GET/PUT/DELETE | /reader-groups/&lt;id&gt;/ | 群体详情/更新/删除 |
| GET/POST | /reader-interactions/ | 读者互动列表（?group_id=）/ 创建 |
| GET/PUT/DELETE | /reader-interactions/&lt;id&gt;/ | 互动详情/更新/删除 |
| POST | /reader-interactions/quick_record/ | 一键记录（自动分配默认读者群，仅需 content 即可保存） |
| GET | /reader-interactions/recent/ | 最近 5 条读者互动 |
| GET | /reader-interactions/resonance_points/ | 认知共振点（energy_score >= 3） |
