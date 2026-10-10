# Treasure — 好东西

「好恶物双面档案」：记录你**亲自验证过**的好东西，和踩过的坑。
同一张表按 `record_type` 分成两副面孔 —— 好物写「为什么好 / 在哪能找到」，歹物写「踩坑原因 / 实际后果」。

## Models
| Model | Table | 用途 |
|-------|-------|------|
| GoodThing | treasure_good_thing | 双面档案（`record_type` 好 / 歹；六类目：吃 / 穿 / 用 / 店 / 地方 / 方法） |

字段随 `record_type` 分化：

| `record_type` | 用到的字段 |
|---|---|
| `好` | `why_good`、`still_available`（还能找到吗）、`where_to_find` |
| `歹` | `avoid_reason`（踩坑原因）、`consequence`（实际后果） |

两侧都有的字段：`name` / `category` / `scene`（什么场景遇到的）/ `tags` / `rating`。

## API Endpoints

前缀 `/api/treasure/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /things/ | 列表（?record_type=&category= 筛选）/ 创建 |
| GET/PUT/DELETE | /things/&lt;id&gt;/ | 详情 / 更新 / 删除 |

## 边界

- `user_id` 字段存在但**只是预留**，视图不读写、不做多用户隔离（单用户系统）。
- 侧边栏入口在「精神滋养」分组的「好东西」（`/treasure`）。
