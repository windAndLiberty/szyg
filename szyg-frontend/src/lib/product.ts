import privateLogoUrl from '@/assets/products/private-logo.png'
import privateLoginBackgroundUrl from '@/assets/products/private-login-background.png'

export type ProductEdition = 'private'

const edition: ProductEdition = 'private'

export const product = {
  edition,
  id: 'szyg_private',
  name: '数字员工',
  logoUrl: privateLogoUrl,
  loginBackgroundUrl: privateLoginBackgroundUrl,
  allowSelfRegistration: false,
  termsUrl: '',
  privacyUrl: '',
}
