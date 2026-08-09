import type { Company, Customer, Invoice, InvoiceLine } from './entities'
import type { VatTreatment } from './vat'
import { invoiceTotals, lineAmount } from './calculators'

// ---------------------------------------------------------------------------
// UBL 2.1 invoice (Peppol BIS Billing 3.0 shape) — a structured e-invoice XML
// the owner can upload into Billit's "Snelle invoer" (which accepts XML). This
// only PREPARES the file locally; sending happens in Billit, never here.
//
// Peppol is strict (Schematron); this covers the mandatory core fields and is
// meant to be validated against Billit's import, then adjusted if needed.
// ---------------------------------------------------------------------------

const x = (s: unknown): string =>
  String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')

const money = (n: number): string => n.toFixed(2)
const normVat = (v?: string): string => (v ?? '').replace(/[^A-Za-z0-9]/g, '').toUpperCase()
const countryOf = (vat?: string): string => {
  const c = (vat ?? '').replace(/[^A-Za-z]/g, '').slice(0, 2).toUpperCase()
  return /^[A-Z]{2}$/.test(c) ? c : 'BE'
}
const unitCode = (u: string): string => ({ day: 'DAY', hour: 'HUR', item: 'C62' })[u.toLowerCase()] ?? 'C62'

function taxCategory(t: VatTreatment, standardPct: number): { id: string; percent: number; reason?: string } {
  switch (t) {
    case 'standard':
      return { id: 'S', percent: standardPct }
    case 'reverse_charge_eu':
      return { id: 'AE', percent: 0, reason: 'Reverse charge' }
    case 'exempt':
      return { id: 'E', percent: 0, reason: 'Exempt' }
    default:
      return { id: 'Z', percent: 0 }
  }
}

function splitAddress(lines: string[]): { street: string; city: string; zip: string } {
  const street = lines[0] ?? ''
  let city = ''
  let zip = ''
  for (const l of lines.slice(1)) {
    const m = /^\s*(\d{4})\s+(.+)$/.exec(l) // Belgian "1000 Brussel"
    if (m) {
      zip = m[1]!
      city = m[2]!.trim()
      break
    }
  }
  if (!city && lines[1]) city = lines[1]!
  return { street, city, zip }
}

function party(name: string, vat: string | undefined, lines: string[]): string {
  const a = splitAddress(lines)
  const country = countryOf(vat)
  const v = normVat(vat)
  const endpoint = v && country === 'BE' ? `\n      <cbc:EndpointID schemeID="9925">${x(v)}</cbc:EndpointID>` : ''
  const taxScheme = v
    ? `\n      <cac:PartyTaxScheme><cbc:CompanyID>${x(v)}</cbc:CompanyID><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>`
    : ''
  const legalId = v ? `<cbc:CompanyID>${x(v)}</cbc:CompanyID>` : ''
  return `
    <cac:Party>${endpoint}
      <cac:PartyName><cbc:Name>${x(name)}</cbc:Name></cac:PartyName>
      <cac:PostalAddress>
        <cbc:StreetName>${x(a.street)}</cbc:StreetName>
        <cbc:CityName>${x(a.city)}</cbc:CityName>
        <cbc:PostalZone>${x(a.zip)}</cbc:PostalZone>
        <cac:Country><cbc:IdentificationCode>${x(country)}</cbc:IdentificationCode></cac:Country>
      </cac:PostalAddress>${taxScheme}
      <cac:PartyLegalEntity><cbc:RegistrationName>${x(name)}</cbc:RegistrationName>${legalId}</cac:PartyLegalEntity>
    </cac:Party>`
}

function invoiceLineXml(line: InvoiceLine, index: number, cat: { id: string; percent: number }): string {
  return `
  <cac:InvoiceLine>
    <cbc:ID>${index + 1}</cbc:ID>
    <cbc:InvoicedQuantity unitCode="${unitCode(line.unit)}">${line.quantity}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="EUR">${money(lineAmount(line))}</cbc:LineExtensionAmount>
    <cac:Item>
      <cbc:Name>${x(line.description)}</cbc:Name>
      <cac:ClassifiedTaxCategory>
        <cbc:ID>${cat.id}</cbc:ID>
        <cbc:Percent>${cat.percent}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:ClassifiedTaxCategory>
    </cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="EUR">${money(line.unitPrice)}</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>`
}

export function ublInvoice(invoice: Invoice, customer: Customer, company: Company): string {
  const totals = invoiceTotals(invoice)
  const cat = taxCategory(invoice.vatTreatment, invoice.standardVatRatePct)
  const exemption = cat.reason ? `\n        <cbc:TaxExemptionReason>${x(cat.reason)}</cbc:TaxExemptionReason>` : ''
  const buyerRef = invoice.reference || invoice.number

  const lines = invoice.lines.map((l, i) => invoiceLineXml(l, i, cat)).join('')

  return `<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
  <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
  <cbc:ID>${x(invoice.number)}</cbc:ID>
  <cbc:IssueDate>${x(invoice.date)}</cbc:IssueDate>
  <cbc:DueDate>${x(invoice.dueDate)}</cbc:DueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  ${invoice.notes ? `<cbc:Note>${x(invoice.notes)}</cbc:Note>\n  ` : ''}<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cbc:BuyerReference>${x(buyerRef)}</cbc:BuyerReference>
  <cac:AccountingSupplierParty>${party(company.name, company.vatNumber, company.addressLines)}
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>${party(customer.company, customer.vatNumber, customer.addressLines)}
  </cac:AccountingCustomerParty>
  <cac:Delivery>
    <cbc:ActualDeliveryDate>${x(invoice.date)}</cbc:ActualDeliveryDate>
  </cac:Delivery>
  <cac:PaymentMeans>
    <cbc:PaymentMeansCode>30</cbc:PaymentMeansCode>
    <cbc:PaymentID>${x(invoice.structuredReference)}</cbc:PaymentID>
    <cac:PayeeFinancialAccount>
      <cbc:ID>${x(normVat(company.iban))}</cbc:ID>${
        normVat(company.bic)
          ? `\n      <cac:FinancialInstitutionBranch><cbc:ID>${x(normVat(company.bic))}</cbc:ID></cac:FinancialInstitutionBranch>`
          : ''
      }
    </cac:PayeeFinancialAccount>
  </cac:PaymentMeans>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="EUR">${money(totals.vatAmount)}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="EUR">${money(totals.subtotal)}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="EUR">${money(totals.vatAmount)}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>${cat.id}</cbc:ID>
        <cbc:Percent>${cat.percent}</cbc:Percent>${exemption}
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="EUR">${money(totals.subtotal)}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="EUR">${money(totals.subtotal)}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="EUR">${money(totals.total)}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="EUR">${money(totals.total)}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>${lines}
</Invoice>
`
}
