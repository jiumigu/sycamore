/**
 * 判定级别的展示映射（P2-A）
 *
 * 为什么单独一份：`ratio` 面板与 `HealthMetrics` 卡片共用同一套
 * `good / warn / danger / normal` 语义 —— 若各写一份色表，迟早出现
 * 「同一个 danger 在两张卡上不是一个红」。
 *
 * 🔴 本文件**不含任何阈值**。它只回答「这个级别画什么颜色」，
 *   不回答「多少算这个级别」—— 后者只在后端 `constants.RATIO_BANDS`。
 */

import type { RatioLevel } from '../types/wealthTypes'

/** 级别 → 颜色。键与后端 level 取值一一对应 */
export const LEVEL_COLOR: Record<string, string> = {
  good: '#52c41a',
  warn: '#e6a23c',
  danger: '#f5222d',
  // normal 是「无需判定 / 两端都不算坏」的中性档，不是「正常」的绿
  normal: '#909399',
}

/** 级别 → 浅色底（刻度条、档位标签底色） */
export const LEVEL_BG: Record<string, string> = {
  good: '#e8f7e0',
  warn: '#fdf3e3',
  danger: '#fdeaea',
  normal: '#f0f0f2',
}

/** 级别 → 颜色。**level 为空时退中性灰**，绝不退成绿 —— 无判定 ≠ 健康 */
export function levelColor(level: RatioLevel): string {
  return LEVEL_COLOR[level ?? ''] ?? LEVEL_COLOR.normal
}

export function levelBg(level: RatioLevel): string {
  return LEVEL_BG[level ?? ''] ?? LEVEL_BG.normal
}

/** level 为空时退回 'normal'，用于 CSS class（对齐后端取值） */
export function levelClass(level: RatioLevel): string {
  return level ?? 'normal'
}
