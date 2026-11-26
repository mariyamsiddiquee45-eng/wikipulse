export type {
  WikiPulseArticle as Article,
  WikiPulseDay as Day,
  WikiPulseManifest as Manifest,
  WikiPulseMethods as Methods,
  WikiPulseSearchShard as SearchShard,
  WikiPulseStatus as Status,
} from '../types/generated'

import type { WikiPulseDay } from '../types/generated'

export type SpikeType = 'Flash' | 'Slow burn' | 'Recurring' | 'Always-on'
export type Event = WikiPulseDay['events'][number]
export type EventMember = Event['members'][number]
