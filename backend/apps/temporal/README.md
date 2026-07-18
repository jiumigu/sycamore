# Temporal — 时间感知

## Models
| Model | Table | 用途 |
|-------|-------|------|
| TemporalTask | temporal_time_atracker_tasks_list | 活动追踪任务（managed=False） |
| OneDayPage | temporal_oneday_page_list | 日记记录（managed=False） |

## Services
- TemporalStatsService：分类统计 / 平衡轮 / 排名
- CSVImportService：CSV 导入
- OneDayPageService：日记统计服务
- DailyLogAutoService：每日自动生成默认日记（当天无任何日记时创建"幸福未被发现，就叫做普通的一天"），兜底入口在 OneDayPageViewSet.list()，管理命令为 `generate_daily_log`

## Constants
4 类任务分类：生产与创造 / 维护与秩序 / 滋养与成长 / 连接与记录，含颜色和图标

## API Endpoints

前缀 `/api/temporal/`

### Tasks
| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /tasks/ | 任务列表 |
| GET | /tasks/task_names/ | 所有任务名称 |
| GET | /tasks/stats/ | 统计总览 |
| GET | /tasks/trend/ | 趋势数据 |
| GET | /tasks/balance/ | 平衡轮 |
| GET | /tasks/ranking/ | 任务排行 |
| GET | /tasks/calendar/ | 日历热力图 |
| POST | /tasks/import_csv/ | CSV 导入 |

### OneDay
| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /oneday/ | 日记列表/创建 |
| GET/PUT/DELETE | /oneday/&lt;id&gt;/ | 详情/更新/删除 |
| GET | /oneday/stats/ | 统计信息 |
| GET | /oneday/yearly_heatmap/ | 年度热力图 |
| GET | /oneday/week_count/ | 本周日记篇数 |
| DELETE | /oneday/bulk_delete/ | 批量删除 |
