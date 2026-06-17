/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://127.0.0.1:8000/api/:path*' },
      { source: '/v1/:path*', destination: 'http://127.0.0.1:8000/v1/:path*' },
      { source: '/health', destination: 'http://127.0.0.1:8000/health' },
    ]
  },
}

module.exports = nextConfig
