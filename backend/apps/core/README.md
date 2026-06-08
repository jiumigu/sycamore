# Core — 系统基础设施

## 职责
Django 项目通用基础设施，不归属任何业务模块。

## 包含

| 文件 | 用途 |
|------|------|
| `pagination.py` | `StandardPagination` — 默认 10 条/页，支持 page_size 参数 |
| `models.py` | 全局共享模型 + UserProfile |
| `admin.py` | 系统管理后台配置 |
| `views.py` | 通用视图 + ProfileView |

## Pagination

所有 ModelViewSet 默认使用 `StandardPagination`，返回格式：
```json
{
  "count": 总条数,
  "next": 下一页URL,
  "previous": 上一页URL,
  "results": [...]
}
```

## Privacy Mode

单人系统的隐私脱敏体系，通过 `UserProfile` 模型控制全局开关。

### Backend

| 文件 | 用途 |
|------|------|
| `models.py:UserProfile` | `user_id`(PK) + `privacy_mode`(BooleanField)，单例模式 |
| `views.py:ProfileView` | `GET /api/core/profile/` 获取配置，`PATCH /api/core/profile/` 更新开关 |
| `urls.py` | `path('profile/', ProfileView.as_view())` |

### Frontend

| 文件 | 用途 |
|------|------|
| `core/privacy/api/privacyApi.ts` | `getProfile()` / `updateProfile(data)` |
| `core/privacy/stores/privacyStore.ts` | Pinia store: `privacyMode` ref, `fetchProfile()`, `togglePrivacyMode()` |
| `shared/utils/privacy.ts` | 纯函数脱敏工具：`maskName`、`maskAmount`、`maskAmountByType`、`maskLocation`、`maskText`、`maskTags` |
| `shared/components/layout/LayoutHeader.vue` | 隐私开关按钮（Lock/Unlock 图标） |
| `shared/components/layout/AppLayout.vue` | 隐私模式蓝色横幅提示 |

### 脱敏规则

| 函数 | 规则 | 示例 |
|------|------|------|
| `maskName` | 首字 + `*` | 吴琦 → 吴\* |
| `maskAmount` | 固定掩码 | ¥50,000 → ¥\*,***.** |
| `maskAmountByType` | 仅收入脱敏，支出不脱敏 | 收入→¥\*,***.** / 支出→¥50,000.00 |
| `maskLocation` | 前2字 + `***` | 福州鼓楼区 → 福州\*\*\* |
| `maskText` | 前2字 + `***` | 大学社团活动认识 → 大学\*\*\* |
| `maskTags` | 固定 `***` | 朋友, 同事 → \*\*\* |

### 已覆盖模块

关系（姓名/标签/地点/场景/备注）、旅行（目的地/花费）、目标（里程碑金额）、理财（月度日历收支汇总/日明细/周明细/定期存款）
