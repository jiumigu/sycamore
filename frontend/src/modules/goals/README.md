# Goals — 目标管理前端

## Views
| 文件 | 职责 |
|------|------|
| `GoalHub.vue` | 目标总览（Tab 切换 + 看板视图 + 筛选 + 快速创建） |

## Components
| 文件 | 职责 |
|------|------|
| `GoalCard.vue` | 目标卡片（进度条 / 里程碑 / 行为追踪 / 操作菜单） |
| `BehaviorTrackCard.vue` | 行为追踪打卡卡（连续天数 / 进度条 / 打卡按钮 / 日历热力图 / 里程碑列表含编辑弹窗） |
| `GoalForm.vue` | 创建/编辑弹窗 |
| `GoalDetail.vue` | 目标详情弹窗（含里程碑网格 + 行为时间线 + 回顾） |
| `MilestoneForm.vue` | 里程碑表单 |
| `ActionList.vue` | 行为列表 |
| `QuickGoalDialog.vue` | 快速创建弹窗（含模板选择） |
| `CloneDialog.vue` | 复制目标弹窗 |
| `OutputForm.vue` | 良品率记录表单弹窗（600px，类别/质量判定/难度各占一行，条件显示失败原因） |
| `outputStore.ts` | 良品率 Pinia 状态管理（CRUD + 按类别/难度/月度统计） |
| `outputApi.ts` | 良品率 API 调用封装（CRUD + stats） |
| `outputTypes.ts` | 良品率类型定义（OutputRecord/OutputStats/CATEGORY_OPTIONS/QUALITY_OPTIONS/FAIL_TYPE_OPTIONS） |

## Views
| 文件 | 职责 |
|------|------|
| `OutputDashboard.vue` | 良品率看板（良品率/容错率/废品率统计卡 + 核心洞察 + 月度趋势 + 分类/难度分析 + 记录表格筛选） |
