const http = require('http')

function readJson(request) {
  return new Promise((resolve, reject) => {
    const chunks = []
    let size = 0
    request.on('data', (chunk) => {
      size += chunk.length
      if (size > 1024 * 1024) {
        reject(new Error('请求内容过大'))
        request.destroy()
        return
      }
      chunks.push(chunk)
    })
    request.on('end', () => {
      try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {}) }
      catch (_) { reject(new Error('请求格式无效')) }
    })
    request.on('error', reject)
  })
}

function json(response, status, payload) {
  const body = Buffer.from(JSON.stringify(payload), 'utf8')
  response.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': body.length,
    'cache-control': 'no-store',
  })
  response.end(body)
}

function startBrowserControlServer(manager, token) {
  const server = http.createServer(async (request, response) => {
    if (request.headers['x-szyg-browser-token'] !== token) {
      json(response, 401, { ok: false, error: 'unauthorized' })
      return
    }
    try {
      if (request.method === 'GET' && request.url === '/health') {
        json(response, 200, { ok: true })
        return
      }
      if (request.method === 'GET' && request.url === '/v1/state') {
        json(response, 200, { ok: true, result: manager.state() })
        return
      }
      if (request.method === 'POST' && request.url === '/v1/action') {
        const payload = await readJson(request)
        const result = await manager.action(payload)
        json(response, 200, { ok: true, result })
        return
      }
      json(response, 404, { ok: false, error: 'not_found' })
    } catch (error) {
      json(response, 400, { ok: false, error: String(error?.message || error) })
    }
  })
  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      resolve({ server, url: `http://127.0.0.1:${address.port}` })
    })
  })
}

module.exports = { startBrowserControlServer }
