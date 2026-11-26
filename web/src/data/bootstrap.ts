import type { Day, Manifest } from './types'

export type Bootstrap = {
  manifest: Manifest | null
  latestDay: Day | null
}

declare global {
  interface Window {
    __WIKIPULSE_BOOTSTRAP__?: Bootstrap | null
  }
}

export function bootstrapData(): Bootstrap | null {
  return window.__WIKIPULSE_BOOTSTRAP__ ?? null
}
