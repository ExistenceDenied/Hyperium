# Hyperium Enterprise Style Guide

The single source of truth for Hyperium's corporate identity across every
surface — PDF, Word, PowerPoint, web and Hyperium OS. The goal is one
**reproducible** identity: the same type, colour and hierarchy everywhere, with
fonts embedded wherever the format allows so output is identical on any machine
and in CI.

## Typography — Inter

**Inter** (SIL Open Font License) is the official Hyperium corporate typeface.
It is bundled in the project and embedded into generated documents.

| Role | Weight |
|------|--------|
| Document titles, headings, KPIs | **Inter SemiBold** |
| Labels & UI elements | **Inter Medium** |
| Body text | **Inter Regular** |
| Fallback (technical only, non-embedded) | Arial, sans-serif |

IBM Plex and Aptos are **retired** — Inter replaces both. Aptos (the previous
brand font) is a Microsoft cloud font that cannot be freely embedded; Inter is
OFL, so it can be bundled and redistributed with the project.

### Type scale (from the brand guide)

| Level | Size |
|-------|------|
| Title / H1 | 28–36 pt |
| H2 | 18–24 pt |
| H3 | 13–16 pt |
| Body | 10–11 pt |
| Caption | 8–9 pt |

## Colour palette

| Name | Hex | Use |
|------|-----|-----|
| Midnight Navy | `#101828` | Wordmark, table headers, totals bar, primary text |
| Electric Blue | `#2563EB` | The signature **H-Line** accent, key figures (e.g. structured reference) |
| Slate | `#475467` | Secondary text |
| Light Grey | `#F8FAFC` | Backgrounds, zebra table rows |
| White | `#FFFFFF` | Reversed text on navy |

## Signature element — the H-Line

A short Electric-Blue horizontal rule used to introduce sections and highlight
hierarchy. Keep the brand's spacing and hierarchy intact.

## Logo

"HYPERIUM" wordmark, letter-spaced, Midnight Navy on light / white on dark;
tagline "STRATEGY • TECHNOLOGY • EXECUTION" with Electric-Blue dot separators.
Compact mark: "H." (navy tile, white H, blue dot). Do not stretch, rotate,
recolour, or add effects/shadows.

## Where it's implemented

| Surface | Fonts | Where |
|---------|-------|-------|
| **PDF** (invoices, timesheets, expenses) | Inter **embedded** (subset) | `apps/admin-finance/server/src/infra/pdf.ts` + `server/assets/fonts/Inter-*.ttf` |
| **Word (.docx)** | Inter **embedded** (ODTTF) | `server/src/infra/word.ts` + `server/src/infra/embedFonts.ts` |
| **Web** (React/Vite) | Inter via `@fontsource/inter`; Tailwind `font-sans: Inter, Arial, sans-serif` | `apps/admin-finance/web/src/main.tsx`, `web/tailwind.config.js` |
| **PowerPoint & Word (Hyperium OS / hyperium-ai)** | Inter **embedded** (docx ODTTF, pptx fntdata) + Midnight-Navy for **untemplated** decks/docs; a supplied template keeps its own theme | `apps/hyperium-ai/infrastructure/documents.py` + `font_embed.py` |

The font files live once in `server/assets/fonts/` (Inter-Regular / Medium /
SemiBold + italics, latin subset) and are converted from the OFL `@fontsource`
distribution. Changing a colour or weight is a token edit at the top of each
generator (`pdf.ts` / `word.ts`).

## Governance & ownership (where this fits)

This standard is a component — **Brand & Corporate Identity** (band ENABLE) — of
**Capability 07 · Platform, Knowledge & Trust** in Hyperium's operating model. It's
the *Trust* leg made concrete on the *Platform* leg's rendering infrastructure, and
it's consumed horizontally by every output-producing capability (01–06).

The operating-model registration (component charter + this standard as a data
contract) lives at `Hyperium IP/Intelligence Engine/brand-identity/`. This code
repo holds the **implementation**; that folder is the **paper-twin anchor** so the
two stay in sync. Changes are **owner-approved** — the identity reaches
client-facing surfaces, so it inherits the firm rule *client-facing content is
capped at L1*.

