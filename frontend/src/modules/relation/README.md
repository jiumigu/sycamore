# Relation — 关系管理前端

| 文件/组件 | 职责 |
|-----------|------|
| `RelationView.vue` | 关系总览（联系人/读者群体双 TAB，4统计卡+3ECharts+待提醒+卡片网格+CRUD弹窗） |
| `RelationshipDetail.vue` | 关系详情（档案卡片+能量趋势/频率双图+互动时间线+CRUD弹窗） |
| `ReaderView.vue` | 读者群体主页（群体卡片列表+认知共振点+互动记录+筛选+CRUD） |
| `relationshipStore.ts` | 关系档案 Pinia 状态管理 |
| `readerStore.ts` | 读者群体 Pinia 状态管理 |
| `relationshipApi.ts` | API 调用封装（14函数） |
| `readerApi.ts` | 读者群体 API 调用封装（8函数） |
| `relationshipTypes.ts` | 关系档案类型定义 + QUALITY_CONFIG/STATUS_OPTIONS 等 |
| `readerTypes.ts` | 读者群体类型定义 + INTERACTION_TYPE_OPTIONS + ENERGY_COLORS |
| `conflictApi.ts` | 冲突事件 API 调用封装（CRUD + 统计） |
| `conflictTypes.ts` | 冲突事件类型定义（ConflictEvent / ConflictStats） |
| `components/reader/ReaderGroupCard.vue` | 读者群体卡片（含交互数和总能量） |
| `components/reader/InteractionForm.vue` | 新增读者互动表单（含能量滑块 + 互动日期） |
| `components/reader/ResonanceList.vue` | 认知共振点列表 |
| `components/reader/MonthlySummaryTab.vue` | 月末盘点标签页（取关自动计算 + 编辑/删除） |
| `stores/conflictStore.ts` | 冲突事件 Pinia 状态管理（CRUD + 统计 + 事件列表） |
| `views/ConflictTrackerView.vue` | 冲突追踪主页（情绪等级标签/解决状态/关联人搜索/隐私脱敏/统计卡片+趋势图） |
