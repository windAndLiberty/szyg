import type { Metadata } from 'next'
import { AppProviders } from '@/stores'
import './globals.css'

export const metadata: Metadata = {
  title: '智能矩阵运营系统',
  description: '一站式AI工具平台',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>
        <AppProviders>
          {children}
        </AppProviders>
      </body>
    </html>
  )
}
