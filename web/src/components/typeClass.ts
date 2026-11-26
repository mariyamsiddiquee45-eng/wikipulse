import type { SpikeType } from '../data/types'

export function typeClass(type: SpikeType): string {
  switch (type) {
    case 'Flash':
      return 'type-flash'
    case 'Slow burn':
      return 'type-slow'
    case 'Recurring':
      return 'type-recurring'
    default:
      return 'type-always'
  }
}
