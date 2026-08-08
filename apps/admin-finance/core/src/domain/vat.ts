import { round2 } from './money'

/** VAT treatment applied to an invoice / customer. */
export type VatTreatment = 'standard' | 'reverse_charge_eu' | 'exempt' | 'zero'

export const VAT_TREATMENTS: readonly VatTreatment[] = ['standard', 'reverse_charge_eu', 'exempt', 'zero'] as const

export const vatTreatmentLabel: Record<VatTreatment, string> = {
  standard: 'Standard (Belgian VAT)',
  reverse_charge_eu: 'Intra-EU reverse charge',
  exempt: 'Exempt',
  zero: 'Zero-rated',
}

/** Mandatory legal mention printed on the invoice for the given treatment (Dutch + English). */
export const vatMention: Record<VatTreatment, string> = {
  standard: '',
  reverse_charge_eu:
    'BTW verlegd — Reverse charge (art. 21 §2 W.BTW / art. 196 Directive 2006/112/EC): VAT to be accounted for by the recipient.',
  exempt: 'Vrijgesteld van BTW / VAT exempt.',
  zero: '0% BTW / zero-rated.',
}

export interface VatResult {
  ratePct: number
  amount: number
}

/** Compute VAT for a base amount given the treatment and the configured standard rate. */
export function computeVat(base: number, treatment: VatTreatment, standardRatePct: number): VatResult {
  const ratePct = treatment === 'standard' ? standardRatePct : 0
  return { ratePct, amount: round2((base * ratePct) / 100) }
}
