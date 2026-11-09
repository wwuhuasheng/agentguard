import http from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const port = Number(process.env.PORT || 4173)
const root = fileURLToPath(new URL('../dist/', import.meta.url))
const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.json': 'application/json',
}
const server = http.createServer(async (req, res) => {
  if (!['GET', 'HEAD'].includes(req.method)) {
    res.writeHead(405)
    return res.end('Method not allowed')
  }
  try {
    const pathname = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname)
    const target = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname))
    const relative = path.relative(root, target)
    if (relative.startsWith('..') || path.isAbsolute(relative)) {
      res.writeHead(403)
      return res.end('Forbidden')
    }
    const info = await stat(target)
    if (!info.isFile()) throw new Error('Not found')
    const content = await readFile(target)
    res.writeHead(200, {
      'Content-Type': types[path.extname(target)] || 'application/octet-stream',
      'Cache-Control': 'no-cache',
      'X-Content-Type-Options': 'nosniff',
    })
    res.end(req.method === 'HEAD' ? undefined : content)
  } catch {
    res.writeHead(404)
    res.end('Not found')
  }
})
server.on('error', (err) => {
  console.error('Cannot start local preview:', err.message)
  process.exitCode = 1
})
server.listen(port, '127.0.0.1', () =>
  console.log(`AgentGuard ready: http://127.0.0.1:${port}  (Ctrl+C to stop)`)
)
