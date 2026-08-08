import { mkdir, readFile, unlink, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import type { DocKind, DocumentStore } from '@af/core'
import { DATA_DIR } from './paths.js'

const subdirFor: Record<DocKind, string> = {
  timesheet: 'timesheets',
  invoice: 'invoices',
  expense: 'expenses',
}

/** Stores generated documents under data/{timesheets,invoices,expenses}/… */
export const documentStore: DocumentStore = {
  async save(kind, filename, bytes) {
    const relPath = join(subdirFor[kind], filename)
    const abs = resolve(DATA_DIR, relPath)
    await mkdir(dirname(abs), { recursive: true })
    await writeFile(abs, bytes)
    return { relPath: relPath.split('\\').join('/'), sizeBytes: bytes.byteLength }
  },
  async read(relPath) {
    return readFile(this.absolutePath(relPath))
  },
  async remove(relPath) {
    await unlink(this.absolutePath(relPath)).catch(() => {
      /* already gone */
    })
  },
  absolutePath(relPath) {
    return resolve(DATA_DIR, relPath)
  },
}
