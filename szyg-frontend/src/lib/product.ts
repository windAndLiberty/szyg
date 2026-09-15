import privateLogoUrl from '@/assets/products/private-logo.png'
import publicLogoUrl from '@/assets/products/public-logo.png'
import privateLoginBackgroundUrl from '@/assets/products/private-login-background.png'
import publicLoginBackgroundUrl from '@/assets/products/public-login-background.png'

export type ProductEdition = 'private' | 'public'

const edition: ProductEdition = import.meta.env.VITE_PRODUCT_EDITION === 'public' ? 'public' : 'private'

export const product = edition === 'public'
  ? {
      edition,
      id: 'xiaoyu_public',
      name: '小妤AI',
      logoUrl: publicLogoUrl,
      loginBackgroundUrl: publicLoginBackgroundUrl,
      allowSelfRegistration: true,
      termsUrl: 'https://qdtracing.com/xiaoyu/terms',
      privacyUrl: 'https://qdtracing.com/xiaoyu/privacy',
    }
  : {
      edition,
      id: 'szyg_private',
      name: '数字员工',
      logoUrl: privateLogoUrl,
      loginBackgroundUrl: privateLoginBackgroundUrl,
      allowSelfRegistration: false,
      termsUrl: '',
      privacyUrl: '',
    }
