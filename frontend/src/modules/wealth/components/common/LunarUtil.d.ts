export function getLunarInfo(date: Date): {
  lunarYear: string
  lunarMonth: string
  lunarDay: string
  lunarMonthNum: number
  lunarDayNum: number
  display: string
  displays: string[]
  lunarDateDisplay: string
  hasFestival: boolean
}

export function getDaysInMonth(year: number, month: number): number
export function getFirstDayOfWeek(year: number, month: number): number
export function formatDate(year: number, month: number, day: number): string
export function isSameDay(d1: Date, d2: Date): boolean
export function isWeekStart(year: number, month: number, day: number): boolean
export function getSolarFestivals(date: Date): string[]

export const COLOR_BG_MAP: Record<string, string>
export const COLOR_TEXT_MAP: Record<string, string>
