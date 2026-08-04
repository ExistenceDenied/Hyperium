import Fastify, { type FastifyInstance } from 'fastify'
import cors from '@fastify/cors'
import { db } from './infra/db.js'
import { registerRoutes } from './routes.js'

/**
 * Build the configured Fastify instance (CORS + loaded db + routes) without
 * binding a port. The HTTP entrypoint (server.ts) listens on it; tests drive it
 * in-process via `app.inject()`.
 */
export async function buildApp(opts: { logger?: boolean } = {}): Promise<FastifyInstance> {
  const app = Fastify({ logger: opts.logger ?? false })
  await app.register(cors, { origin: true })
  await db.ensureLoaded()
  await registerRoutes(app)
  return app
}
