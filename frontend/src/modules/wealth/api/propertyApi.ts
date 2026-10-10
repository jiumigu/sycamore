/**
 * 物件资产（v3.60.0，P4-A）接口封装
 *
 * ⚠️ 列表端点全是**裸数组**（后端显式 `pagination_class = None`）。
 *    如果哪天被 DRF 全局分页包成 `{count, results}`，前端按数组消费会**静默变空** ——
 *    看起来像「一件家当都没有」，实际是格式变了。store 里对每个数组都做了兜底。
 *
 * ⚠️ 刻意**不提供** `?ordering=`：排序在前端做（见 store 的 `sortItems`）。
 *    一旦开到后端，`current_value`（派生值、不落库）就会被逼着落库。
 */

import request from '@/shared/utils/request'
import type {
  PropertyCategory,
  PropertyCategoryFormData,
  PropertyCondition,
  PropertyIssue,
  PropertyItem,
  PropertyItemFormData,
  PropertyMeta,
  PropertyMetricMeta,
  PropertyNetValueBlock,
  PropertyOption,
  PropertySeedResult,
  PropertyStatus,
  PropertySummary,
  PropertyTotalBlock,
  PropertyZeroReason,
} from '../types/propertyTypes'

// ── 类别（轻量主数据） ──

/** 类别列表 —— 后端返回**裸数组** */
export function getPropertyCategories() {
  return request({ url: '/wealth/property/categories/', method: 'get' })
}

export function createPropertyCategory(data: PropertyCategoryFormData) {
  return request({ url: '/wealth/property/categories/', method: 'post', data })
}

export function updatePropertyCategory(id: number, data: Partial<PropertyCategoryFormData>) {
  return request({ url: `/wealth/property/categories/${id}/`, method: 'patch', data })
}

/**
 * 删一个类别 —— 其下还有物件时后端返回 **400 + 可照做的提示**
 *
 * 🔴 **不级联删除**：删掉一个建错的空类别，与删掉整柜家当，不该走同一个按钮。
 *    调用方要把 400 的 `detail` 原样弹给用户（那句话里带着「还有 N 件」）。
 */
export function deletePropertyCategory(id: number) {
  return request({ url: `/wealth/property/categories/${id}/`, method: 'delete' })
}

/**
 * 初始化默认类别（幂等）—— **只建类别，不预设任何物件**
 *
 * ⚠️ 类别上**没有**默认使用年限：那是用户自己的判断，系统不发明。
 * ⚠️ `overwrite: true` 会覆盖已有类别的图标与说明，调用前必须先问一句。
 */
export function seedPropertyCategories(data?: { overwrite?: boolean }) {
  return request({ url: '/wealth/property/categories/seed/', method: 'post', data: data ?? {} })
}

// ── 物件 ──

/** 物件列表 —— 后端返回**裸数组**；筛选在服务端、排序在前端 */
export function getPropertyItems(params?: {
  category?: number
  status?: string
  condition?: string
  search?: string
}) {
  return request({ url: '/wealth/property/items/', method: 'get', params })
}

export function createPropertyItem(data: PropertyItemFormData) {
  return request({ url: '/wealth/property/items/', method: 'post', data })
}

export function updatePropertyItem(id: number, data: Partial<PropertyItemFormData>) {
  return request({ url: `/wealth/property/items/${id}/`, method: 'patch', data })
}

/** 删除一件物件 —— **物理删除**（报废已经承担了「不用了」的语义，不再叠软删开关） */
export function deletePropertyItem(id: number) {
  return request({ url: `/wealth/property/items/${id}/`, method: 'delete' })
}

/**
 * 保存前试算（**不写库**）—— 返回与保存后**同形**的一行
 *
 * 🔴 刻意走后端而不是前端自己把「金额 ÷ 年限」除一遍：
 *    那份公式与 `property_calc` 迟早会分叉，而**分叉是静默的** ——
 *    试算说 ¥1,520、保存后明细表里写着 ¥1,480，两边都像一个正常的数。
 *    这里拿到的净值与保存后看到的是同一行代码算出来的。
 * ⚠️ 校验也复用保存那一个表单序列化器：试算放行、一保存报 400 比没有试算更误导。
 * ⚠️ 试算是**护栏、不是闸门** —— 它自己失败只降级成不显示，绝不阻断保存。
 */
export function previewPropertyItem(data: PropertyItemFormData) {
  return request({ url: '/wealth/property/items/preview/', method: 'post', data })
}

// ── 汇总与口径 ──

/** 首屏四卡（含「未计入件数」）—— 只读、实时算 */
export function getPropertySummary() {
  return request({ url: '/wealth/property/summary/', method: 'get' })
}

/** 枚举与口径的单一出口 —— 前端不硬编码任何选项文案或阈值 */
export function getPropertyMeta() {
  return request({ url: '/wealth/property/meta/', method: 'get' })
}

// ── 类型再导出：组件按需取用，避免各处重复 import 两个文件 ──

export type {
  PropertyCategory,
  PropertyCategoryFormData,
  PropertyItem,
  PropertyItemFormData,
  PropertyMeta,
  PropertyMetricMeta,
  PropertyNetValueBlock,
  PropertyOption,
  PropertySeedResult,
  PropertyStatus,
  PropertyCondition,
  PropertySummary,
  PropertyTotalBlock,
  PropertyZeroReason,
  PropertyIssue,
}
