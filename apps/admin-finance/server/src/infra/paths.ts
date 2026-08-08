import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
// server/src/infra -> admin-finance
export const ROOT = resolve(here, '..', '..', '..')
// Records live in <root>/data by default; AF_DATA_DIR overrides it so tests (and
// alternate deployments) can point at an isolated store without touching real data.
export const DATA_DIR = resolve(process.env.AF_DATA_DIR ?? resolve(ROOT, 'data'))
export const DB_FILE = resolve(DATA_DIR, 'db.json')
export const dataSubdir = (name: string): string => resolve(DATA_DIR, name)
