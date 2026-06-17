'use client'

import { findFeatureByPath } from '@/lib/feature-tree'
import PlaceholderPage from '@/components/PlaceholderPage'

export default function Page() {
  const feature = findFeatureByPath('/insight/asset-dashboard')
  if (!feature) return null
  return <PlaceholderPage feature={feature} />
}
