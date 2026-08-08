import { round2 } from './money'

/** Minimal shape needed to compute Belgian forfaitary kilometre reimbursement. */
export interface MileageLike {
  distanceKm: number
  roundTrip: boolean
}

/** Reimbursable kilometres for one trip (round trips count double). */
export const reimbursableKm = (t: MileageLike): number => round2(t.distanceKm * (t.roundTrip ? 2 : 1))

/** Reimbursement for one trip at the configured official €/km rate. */
export const tripReimbursement = (t: MileageLike, ratePerKm: number): number => round2(reimbursableKm(t) * ratePerKm)

export interface MileageTotals {
  totalKm: number
  totalReimbursement: number
}

/** Monthly mileage totals: total reimbursable km and the reimbursement at the official rate. */
export function mileageTotals(trips: readonly MileageLike[], ratePerKm: number): MileageTotals {
  const totalKm = round2(trips.reduce((s, t) => s + reimbursableKm(t), 0))
  return { totalKm, totalReimbursement: round2(totalKm * ratePerKm) }
}
