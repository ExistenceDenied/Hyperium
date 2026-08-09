import { readFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import JSZip from 'jszip'

const FONTS = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', 'assets', 'fonts')

type Style = 'Regular' | 'Bold' | 'Italic' | 'BoldItalic'
const EMBED_TAG: Record<Style, string> = {
  Regular: 'w:embedRegular',
  Bold: 'w:embedBold',
  Italic: 'w:embedItalic',
  BoldItalic: 'w:embedBoldItalic',
}

interface Family {
  name: string
  family: 'swiss' | 'roman'
  files: { file: string; style: Style }[]
}

// The faces the documents actually use (keeps each .docx to ~0.8 MB rather than embedding all weights).
const FAMILIES: Family[] = [
  {
    name: 'Inter',
    family: 'swiss',
    files: [
      { file: 'Inter-Regular.ttf', style: 'Regular' },
      { file: 'Inter-SemiBold.ttf', style: 'Bold' },
      { file: 'Inter-Italic.ttf', style: 'Italic' },
    ],
  },
  {
    name: 'Inter Medium',
    family: 'swiss',
    files: [
      { file: 'Inter-Medium.ttf', style: 'Regular' },
      { file: 'Inter-SemiBold.ttf', style: 'Bold' },
    ],
  },
]

/**
 * ODTTF obfuscation (ISO/IEC 29500-1 §17.8.1): XOR the first 32 bytes of the font
 * with the fontKey GUID's 16 bytes, applied in reverse index order. Symmetric.
 */
function obfuscate(data: Buffer, guid: string): Buffer {
  const key = Buffer.from(guid.replace(/[{}-]/g, ''), 'hex') // 16 bytes, key[0] = first hex pair
  const out = Buffer.from(data)
  for (let i = 0; i < 32 && i < out.length; i++) out[i] ^= key[15 - (i % 16)]
  return out
}

const NS_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
const NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

/** Embed the Inter faces into a .docx so it renders without the fonts installed. */
export async function embedFonts(docxBytes: Uint8Array): Promise<Uint8Array> {
  const zip = await JSZip.loadAsync(docxBytes)

  let n = 0
  const rels: string[] = []
  const familyXml: string[] = []
  for (const fam of FAMILIES) {
    const embeds: string[] = []
    for (const f of fam.files) {
      n += 1
      const partName = `font${n}.odttf`
      const rid = `rId${n}`
      const guid = `{${randomUUID().toUpperCase()}}`
      const ttf = await readFile(resolve(FONTS, f.file))
      zip.file(`word/fonts/${partName}`, obfuscate(ttf, guid))
      rels.push(
        `<Relationship Id="${rid}" Type="${NS_R}/font" Target="fonts/${partName}"/>`,
      )
      embeds.push(`<${EMBED_TAG[f.style]} r:id="${rid}" w:fontKey="${guid}"/>`)
    }
    familyXml.push(
      `<w:font w:name="${fam.name}"><w:charset w:val="00"/><w:family w:val="${fam.family}"/><w:pitch w:val="variable"/>${embeds.join('')}</w:font>`,
    )
  }

  zip.file(
    'word/fontTable.xml',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:fonts xmlns:w="${NS_W}" xmlns:r="${NS_R}">${familyXml.join('')}</w:fonts>`,
  )
  zip.file(
    'word/_rels/fontTable.xml.rels',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${rels.join('')}</Relationships>`,
  )

  // Relate fontTable.xml to the main document.
  await patch(zip, 'word/_rels/document.xml.rels', (xml) =>
    xml.includes('relationships/fontTable')
      ? xml
      : xml.replace(
          '</Relationships>',
          `<Relationship Id="rIdFontTable" Type="${NS_R}/fontTable" Target="fontTable.xml"/></Relationships>`,
        ),
  )

  // Declare the obfuscated-font and fontTable content types.
  await patch(zip, '[Content_Types].xml', (xml) =>
    xml.includes('Extension="odttf"')
      ? xml
      : xml.replace(
          '</Types>',
          `<Default Extension="odttf" ContentType="application/vnd.openxmlformats-officedocument.obfuscatedFont"/>` +
            `<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/></Types>`,
        ),
  )

  // Turn on font embedding in settings.xml. CT_Settings is an ordered sequence:
  // <w:embedTrueTypeFonts/> must follow displayBackgroundShape / the print* elements
  // and precede evenAndOddHeaders, compat, etc. — insert it in a schema-valid slot.
  await patch(zip, 'word/settings.xml', (xml) => {
    if (xml.includes('embedTrueTypeFonts')) return xml
    const tag = '<w:embedTrueTypeFonts/>'
    if (xml.includes('<w:displayBackgroundShape/>'))
      return xml.replace('<w:displayBackgroundShape/>', `<w:displayBackgroundShape/>${tag}`)
    const after = xml.search(/<w:(embedSystemFonts|saveSubsetFonts|evenAndOddHeaders|defaultTabStop|compat|rsids)\b/)
    if (after !== -1) return xml.slice(0, after) + tag + xml.slice(after)
    return xml.replace(/(<w:settings\b[^>]*>)/, `$1${tag}`)
  })

  return zip.generateAsync({ type: 'uint8array', compression: 'DEFLATE' })
}

async function patch(zip: JSZip, path: string, fn: (xml: string) => string): Promise<void> {
  const file = zip.file(path)
  if (!file) return
  const xml = await file.async('string')
  zip.file(path, fn(xml))
}
