'use client'

import { findFeatureByPath } from '@/lib/feature-tree'
import PlaceholderPage from '@/components/PlaceholderPage'

export default function Page() {
  const feature = findFeatureByPath('/tools/format-convert')
  if (!feature) return null
  return <PlaceholderPage feature={feature} />
}
