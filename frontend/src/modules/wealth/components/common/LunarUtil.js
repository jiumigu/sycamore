/**
 * 农历/节气/节日工具函数
 *
 * 基于 lunar-javascript 库 (https://www.npmjs.com/package/lunar-javascript)
 */

import { Solar, SolarUtil } from 'lunar-javascript'

/**
 * 获取某日的农历显示信息
 * @param {Date} date
 * @returns {{ lunarMonth: string, lunarDay: string, display: string, festivals: string[] }}
 */
export function getLunarInfo(date) {
  const solar = Solar.fromDate(date)
  const lunar = solar.getLunar()

  const lunarMonth = lunar.getMonthInChinese()
  const lunarDay = lunar.getDayInChinese()
  const lunarMonthNum = lunar.getMonth()
  const lunarDayNum = lunar.getDay()
  const lunarYear = lunar.getYearInChinese()

  // 收集显示内容，按优先级
  const displays = []

  // 1. 传统节日（农历）
  const lunarFestivals = lunar.getFestivals()
  for (const f of lunarFestivals) {
    displays.push(f)
  }

  // 2. 节气
  const jie = lunar.getJie()
  const qi = lunar.getQi()
  if (jie) displays.push(jie)
  if (qi) displays.push(qi)

  // 3. 公历节日
  const solarFestivals = solar.getFestivals()
  for (const f of solarFestivals) {
    displays.push(f)
  }
  const otherFestivals = lunar.getOtherFestivals()
  for (const f of otherFestivals) {
    // 过滤掉 generate 方法
    if (typeof f !== 'function') displays.push(f)
  }

  // 4. 农历日期
  let lunarDateDisplay = ''
  if (lunarDayNum === 1) {
    lunarDateDisplay = `${lunarMonth}月`
  } else {
    lunarDateDisplay = `${lunarMonth}月${lunarDay}`
  }

  return {
    lunarYear,
    lunarMonth,
    lunarDay,
    lunarMonthNum,
    lunarDayNum,
    display: displays[0] || lunarDateDisplay,
    displays,
    lunarDateDisplay,
    hasFestival: displays.length > 0,
  }
}

/**
 * 获取月份的天数
 */
export function getDaysInMonth(year, month) {
  return SolarUtil.getDaysOfMonth(year, month)
}

/**
 * 获取某月1号是周几 (0=周日, 1=周一, ..., 6=周六)
 */
export function getFirstDayOfWeek(year, month) {
  const d = new Date(year, month - 1, 1)
  return d.getDay()
}

/**
 * 将日期格式化为 YYYY-MM-DD
 */
export function formatDate(year, month, day) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

/**
 * 判断两个日期是否同一天
 */
export function isSameDay(d1, d2) {
  return d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
}

/**
 * 判断某天是否为周一（周起始标记）
 */
export function isWeekStart(year, month, day) {
  const d = new Date(year, month - 1, day)
  return d.getDay() === 1
}

/**
 * 获取当日应收到的公历节日
 */
export function getSolarFestivals(date) {
  const solar = Solar.fromDate(date)
  return solar.getFestivals()
}

/**
 * 颜色等级 → CSS 背景色
 */
export const COLOR_BG_MAP = {
  income_high: '#b7eb8f',
  income_mid: '#d9f7be',
  income_light: '#f0f5e5',
  neutral: '#fafafa',
  expense_light: '#fff0f0',
  expense_mid: '#ffd9d9',
  expense_high: '#ffb3b3',
}

/**
 * 颜色等级 → 金额文字色
 */
export const COLOR_TEXT_MAP = {
  income_high: '#135200',
  income_mid: '#237804',
  income_light: '#389e0d',
  neutral: '#595959',
  expense_light: '#cf1322',
  expense_mid: '#a8071a',
  expense_high: '#820014',
}
