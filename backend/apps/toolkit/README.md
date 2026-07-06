# Toolkit — 工具集

## Models

| Model | Table | 用途 |
|-------|-------|------|
| ToolkitDefinition | toolkit_definition | 工具定义 |
| ToolkitExecution | toolkit_execution | 执行记录 |
| CityCoordinate | toolkit_city_coordinate | 全国城市坐标（718+ 条，含省市三级） |
| TravelRoutePreset | toolkit_travel_route_preset | 旅行路线预设 |
| EnvironmentAudit | toolkit_environment_audit | 环境校准记录（6维度评分 + 总分/判定/备注） |
| CareerEnergyAudit | toolkit_career_energy_audit | 职业能量审计（26项指标 + 自动判定 + 建议 + 下次审计提醒） |
| LanguageTraining | toolkit_language_training | 语言训练记录（4种训练类型：词汇颗粒度/场景描述/语言素材/逼近修订） |

## Architecture

```
BaseTool + ToolRegistry（工具定义层）
    ↓ auto_discover
execute() + progress_callback（工具执行层）
    ↓ 同步
ToolkitExecution（任务记录层）
    ↓
前端展示（ToolkitDashboard → ToolDetail → 结果）
```

## 扩展新工具
在 `tools/` 目录下新建文件，继承 `BaseTool`，实现 `get_input_schema()` 和 `execute()`，启动时自动注册。

## API Endpoints

前缀 `/api/toolkit/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /tools/ | 工具列表（含分类聚合） |
| GET | /tools/&lt;tool_key&gt;/ | 工具详情（含 input_schema） |
| POST | /execute/ | 执行工具 |
| GET | /task/&lt;execution_id&gt;/ | 任务状态 |
| GET | /history/ | 执行历史（分页+筛选） |
| POST | /register/ | 注册工具到数据库 |
| POST | /convert_file/ | 文件转换上传操作 |
| GET | /cities/ | 城市坐标列表 |
| GET | /cities/search/ | 城市搜索（?q= 模糊匹配） |
| GET | /cities/provinces/ | 省份列表 |
| GET | /cities/cities/ | 地级市列表（?province=） |
| GET | /cities/districts/ | 区县列表（?city=） |
| GET | /travel-routes/ | 旅行路线预设列表 |
| POST | /travel-routes/ | 创建路线预设 |
| PUT | /travel-routes/&lt;id&gt;/ | 更新路线预设 |
| DELETE | /travel-routes/&lt;id&gt;/ | 删除路线预设 |
| GET | /environment-audits/ | 环境校准历史列表（?page_size= 分页） |
| POST | /environment-audits/ | 创建校准记录（自动计算总分/判定） |
| DELETE | /environment-audits/&lt;id&gt;/ | 删除校准记录 |
| GET | /career-energy-audits/ | 职业能量审计列表（DRF 分页） |
| POST | /career-energy-audits/ | 创建审计记录（自动计算总分/判定） |
| DELETE | /career-energy-audits/&lt;id&gt;/ | 删除审计记录 |
| GET | /language-training/ | 语言训练列表（?train_type= 筛选） |
| POST | /language-training/ | 创建训练记录 |
| PATCH | /language-training/&lt;id&gt;/ | 更新训练记录 |
| DELETE | /language-training/&lt;id&gt;/ | 删除训练记录 |

## 内置工具

| tool_key | 名称 | 用途 |
|----------|------|------|
| trad2simp | 繁简转换 | 繁体/简体文本互转 |
| img2gif | 动图合成 | 多张图片合成 GIF |
| travel_route | 旅行路线推演 | 地图可视化路线推演 |
| environment_audit | 环境校准 | 六维度环境健康评分 + 判定
| career_energy_audit | 职业能量审计 | 26项指标职业能量评估 + 自动判定 |
| language_trainer | 语言训练器 | 4种训练类型（词汇颗粒度/场景描述/语言素材/逼近修订），CRUD 历史记录 |
