import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { LayoutProvider } from './lib/layout'
import { ThemeProvider } from './lib/theme'
import AppErrorBoundary from './components/AppErrorBoundary'
import { I18nProvider } from './lib/i18n'
import { product } from './lib/product'
import App from './App'
import './index.css'

// Keep the native Electron title aligned with the product branding.
document.title = `${product.name} - 超级数字员工`

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <I18nProvider>
        <ThemeProvider>
          <AppErrorBoundary>
            <LayoutProvider>
              <App />
            </LayoutProvider>
          </AppErrorBoundary>
        </ThemeProvider>
      </I18nProvider>
    </BrowserRouter>
  </StrictMode>,
)
