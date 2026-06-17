// Re-export from stores — single source of truth for auth and brand state.
// Components should import from here for convenience; the actual state lives in stores/index.ts.
export { useAuth, useBrand } from '@/stores'
