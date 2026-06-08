# Summary — 综合进度看板

## 换算规则

| 模块 | 公式 | 除数 | 说明 |
|------|------|------|------|
| 财富 | (wageincome + otherincome - outmoney) | 10000 | 净收入每万元=1点 |
| 健康 | SUM(total) | 10000 | 步数每万步=1点 |
| 时间投入 | SUM(duration_hours) | 30 | 时长每30小时=1点 |
| 文字记录 | SUM(total) | 10000 | 字数每万字=1点 |
| 小确幸 | SUM(level_of_happiness) | 10 | 快乐程度每10=1点 |
| 旅行 | COUNT(*) | 1 | 每次旅行=1点 |
| 阅读 | COUNT(*) | 1 | 每本已读书=1点 |

年度目标 400 点，月度目标 33.33 点。

## API Endpoints

前缀 `/api/summary/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /years/ | 有数据的年份列表 |
| GET | /overview/?year= | 年度总览 |
| GET | /monthly_detail/?year=&month= | 月度详情 |
| GET | /trend/?year= | 12个月趋势 |
| GET | /radar/?year= | 雷达图数据 |
| GET | /module_detail/?module=&year=&month= | 模块钻取 |
