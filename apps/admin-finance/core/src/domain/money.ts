/**
 * Monetary amounts are handled as euros (numbers), rounded to 2 decimals at every calculation
 * boundary via {@link round2}. Rates (day rate, VAT %, €/km) may carry more precision.
 */
export const round2 = (n: number): number => Math.round((n + Number.EPSILON) * 100) / 100
export const round4 = (n: number): number => Math.round((n + Number.EPSILON) * 10000) / 10000

const eurFmt = new Intl.NumberFormat('nl-BE', { style: 'currency', currency: 'EUR' })

/** Belgian-formatted euro amount, e.g. "1.234,56 €". */
export const formatEUR = (n: number): string => eurFmt.format(round2(n))

export const formatNumber = (n: number, digits = 2): string =>
  new Intl.NumberFormat('nl-BE', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n)

export const formatKm = (n: number): string => `${formatNumber(round2(n))} km`

export const sum = (xs: number[]): number => round2(xs.reduce((s, x) => s + x, 0))
