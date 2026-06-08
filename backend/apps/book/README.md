# Book — 书籍阅读

## Models
| Model | Table | 用途 |
|-------|-------|------|
| Book | book_read_list | 书籍阅读记录（含 11 种分类、8 种状态、5 级阅读深度） |

## API Endpoints

前缀 `/api/books/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /books/ | 列表（?type=&status=&year= 筛选） |
| POST | /books/ | 创建 |
| GET/PUT/DELETE | /books/&lt;pk&gt;/ | 详情/更新/删除 |
| GET | /books/stats/ | 年度/月度阅读统计 |
| GET | /books/recommendations/ | 推荐书单 |
