/**
 * Belgian structured payment communication ("gestructureerde mededeling"):
 * 10 base digits + a 2-digit mod-97 check (00 -> 97), formatted +++xxx/xxxx/xxxxx+++.
 */
export function structuredReference(seed: number): string {
  const base = String(Math.abs(Math.trunc(seed)) % 10_000_000_000).padStart(10, '0')
  let check = Number(BigInt(base) % 97n)
  if (check === 0) check = 97
  const digits = base + String(check).padStart(2, '0')
  return `+++${digits.slice(0, 3)}/${digits.slice(3, 7)}/${digits.slice(7, 12)}+++`
}

/** Stable numeric seed from an invoice year + sequence, e.g. 2026 + seq 7 -> 202600007. */
export const referenceSeedFromInvoice = (year: number, seq: number): number => year * 100000 + seq
