import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type Plugin } from 'vite'

const projectRoot = dirname(fileURLToPath(import.meta.url))

function mswWorkerPlugin(): Plugin {
  return {
    name: 'noeticbraid-serve-msw-worker',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const requestPath = req.url?.split('?')[0]
        if (requestPath !== '/mockServiceWorker.js') {
          next()
          return
        }

        const workerPath = [
          resolve(projectRoot, 'node_modules/msw/lib/mockServiceWorker.js'),
          resolve(projectRoot, 'node_modules/msw/mockServiceWorker.js'),
        ].find((candidate) => existsSync(candidate))

        if (!workerPath) {
          res.statusCode = 404
          res.end('MSW worker script was not found. Run pnpm install first.')
          return
        }

        res.setHeader('Content-Type', 'application/javascript; charset=utf-8')
        res.end(readFileSync(workerPath, 'utf-8'))
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectRoot, '')
  const platformLive = env.VITE_PLATFORM_LIVE === '1'
  const platformBackendOrigin = env.VITE_PLATFORM_BACKEND_ORIGIN || 'http://127.0.0.1:8000'

  return {
    plugins: [react(), mswWorkerPlugin()],
    resolve: {
      alias: {
        '@': resolve(projectRoot, './src'),
      },
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      ...(platformLive
        ? {
            proxy: {
              '/platform': { target: platformBackendOrigin, changeOrigin: true, ws: true },
              '/api/auth/startup_token': { target: platformBackendOrigin, changeOrigin: true },
            },
          }
        : {}),
    },
    test: {
      environment: 'jsdom',
      environmentOptions: {
        jsdom: {
          url: 'http://127.0.0.1:5173/',
        },
      },
      globals: true,
      setupFiles: ['./tests/setup.ts'],
      include: ['tests/**/*.test.{ts,tsx}'],
      exclude: ['tests/e2e/**', 'node_modules/**'],
    },
  }
})
