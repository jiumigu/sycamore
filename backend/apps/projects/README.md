# Projects — 项目管理

## Models
| Model | Table | 用途 |
|-------|-------|------|
| Project | projects_project | 项目（主表，含进度百分比） |
| ProjectMilestone | projects_milestone | 项目里程碑 |

## API Endpoints

前缀 `/api/projects/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /projects/ | 列表/创建 |
| GET/PUT/DELETE | /projects/&lt;pk&gt;/ | 详情/更新/删除 |
| GET | /projects/stats/ | 统计总览 |
