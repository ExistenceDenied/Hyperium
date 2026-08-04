import { eachDayOfInterval, endOfMonth, format, getDay, startOfMonth } from 'date-fns'

/** A calendar month. `month` is 1-12. */
export interface Period {
  year: number
  month: number
}

export const periodKey = (p: Period): string => `${p.year}-${String(p.month).padStart(2, '0')}`

export const parsePeriodKey = (key: string): Period => {
  const [y, m] = key.split('-').map(Number)
  return { year: y, month: m }
}

export const currentPeriod = (now: Date): Period => ({ year: now.getFullYear(), month: now.getMonth() + 1 })

export const monthLabel = (p: Period): string =>
  new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' }).format(new Date(p.year, p.month - 1, 1))

/** Every day of the month, as local Dates. */
export function monthDays(p: Period): Date[] {
  const start = startOfMonth(new Date(p.year, p.month - 1, 1))
  return eachDayOfInterval({ start, end: endOfMonth(start) })
}

export const isoDate = (d: Date): string => format(d, 'yyyy-MM-dd')

export const isWeekend = (d: Date): boolean => {
  const g = getDay(d)
  return g === 0 || g === 6
}

/** Monday=1 .. Sunday=7 (ISO), useful for laying out a calendar grid. */
export const isoWeekday = (d: Date): number => {
  const g = getDay(d)
  return g === 0 ? 7 : g
}

export function addDaysISO(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + days)
  return format(d, 'yyyy-MM-dd')
}
